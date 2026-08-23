from __future__ import annotations

import concurrent.futures
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from vss_capabilities import (
    CapabilityExecutionContext,
    CapabilityResult,
    SDKValidationError,
    freeze_configuration,
    validate_input,
    validate_output,
)
from vss_commands.exit_codes import ExitCode
from vss_providers import (
    LOCAL_CLOCK_IDENTITY,
    LOCAL_PICTORIAL_FRAME_IDENTITY,
    LOCAL_STORYBOARD_RENDER_IDENTITY,
    ProviderAccess,
    ProviderFailure,
    ProviderRegistry,
    ProviderSelector,
)
from .audit import AuditLogger
from .errors import (
    CapabilityExecutionFailure,
    InvalidCapabilityInput,
    PermissionDenied,
    RuntimeFailure,
    RuntimeInternalFailure,
    RuntimeTimeout,
)
from .external_preflight import ExternalExecutionPreflight, ExternalExecutionPreflightSpec
from .loader import CapabilityLoader
from .host_inspection import HostInspector
from .models import ExecutionContext
from .policy import RuntimePolicy
from .registry import CapabilityRegistry
from .artifacts import PictorialArtifactPublisher, StoryboardArtifactPublisher


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class RuntimeController:
    def __init__(
        self,
        root: Path | None = None,
        policy: RuntimePolicy | None = None,
        audit_logger: AuditLogger | None = None,
        provider_registry: ProviderRegistry | None = None,
        host_inspector: HostInspector | None = None,
        creative_smoke_transport=None,
        creative_smoke_secret_reader=None,
        external_execution_preflight: ExternalExecutionPreflight | None = None,
    ) -> None:
        self.root = (root or repository_root()).resolve()
        builtins_root = self.root / "capabilities"
        self.registry = CapabilityRegistry(builtins_root, self.root / "schemas/capability-manifest-v1.schema.json")
        self.loader = CapabilityLoader(builtins_root)
        self.policy = policy or RuntimePolicy(
            allowed_builtin_permissions=("provider_access",),
            allowed_provider_identities=(LOCAL_CLOCK_IDENTITY, LOCAL_STORYBOARD_RENDER_IDENTITY, LOCAL_PICTORIAL_FRAME_IDENTITY),
            allowed_capability_permissions={
                "bootstrap.check": ("filesystem_read", "subprocess"),
                "movie.storyboard-render": ("provider_access", "filesystem_write"),
                "movie.pictorial-frame-generation": ("provider_access", "filesystem_write"),
                "movie.m8-3-real-provider-smoke-2": ("filesystem_write", "network", "secrets"),
            },
        )
        self.provider_registry = provider_registry or ProviderRegistry(
            self.root / "providers/builtin", self.root / "schemas/provider-v1.schema.json"
        )
        self.provider_selector = ProviderSelector(self.provider_registry)
        self.host_inspector = host_inspector or HostInspector()
        self.audit = audit_logger or AuditLogger(self.root / ".local/runtime/audit", trusted_root=self.root)
        self.creative_smoke_transport = creative_smoke_transport
        self.creative_smoke_secret_reader = creative_smoke_secret_reader
        self.external_execution_preflight = external_execution_preflight or ExternalExecutionPreflight()

    def _source_commit(self) -> str | None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=self.root, text=True, capture_output=True, check=False, timeout=2
            )
        except (OSError, subprocess.SubprocessError):
            return None
        value = result.stdout.strip()
        return value if result.returncode == 0 and len(value) == 40 else None

    def run(
        self,
        command: str,
        environment: str,
        configuration: dict[str, Any],
        input_data: dict[str, Any],
        correlation_id: str,
        started_at: str,
        started_clock: float,
        dry_run: bool = False,
        timeout_seconds: float | None = None,
        verbose: bool = False,
        ask_become_pass: bool = False,
        admitted_request: object | None = None,
    ) -> tuple[dict[str, Any], int]:
        capability_identity = command
        permissions: tuple[str, ...] = ()
        authorization = "not_evaluated"
        manifest_digest: str | None = None
        source_commit = self._source_commit()
        provider_audit: list[dict[str, Any]] = []
        execution_id = uuid.uuid4().hex
        output: dict[str, Any] = {}
        errors: list[str] = []
        status = "error"
        artifact_publisher: StoryboardArtifactPublisher | None = None
        pictorial_artifact_publisher: PictorialArtifactPublisher | None = None
        creative_smoke_artifact_publisher = None
        provider_diagnostic: dict[str, Any] | None = None
        preflight_diagnostic: dict[str, Any] | None = None
        exit_code: ExitCode = ExitCode.INTERNAL_ERROR
        try:
            capability = self.registry.resolve_command(command)
            capability_identity = capability.manifest.identity
            manifest_digest = capability.manifest_sha256
            command_record = capability.manifest.command(command)
            if command_record is None:
                raise RuntimeInternalFailure("capability command resolution failed")
            validation_errors = sorted(
                Draft202012Validator(command_record["input_schema"]).iter_errors(input_data),
                key=lambda error: list(error.path),
            )
            if validation_errors:
                raise InvalidCapabilityInput(f"invalid input: {validation_errors[0].message}")
            if dry_run and not command_record["supports_dry_run"]:
                raise InvalidCapabilityInput("command does not support dry-run")
            registrations = []
            for requirement in capability.manifest.required_providers:
                provider_record = {
                    "type": requirement["type"],
                    "identity": requirement["identity"],
                    "version": None,
                    "authorization": "not_evaluated",
                }
                provider_audit.append(provider_record)
                registration = self.provider_selector.registration(requirement)
                provider_record["version"] = registration.metadata.version
                registrations.append(registration)
            permissions = capability.manifest.permissions
            authorized = self.policy.authorize(permissions, capability.manifest.identity)
            self.policy.authorize_providers(
                requirement["identity"] for requirement in capability.manifest.required_providers
            )
            for provider_record in provider_audit:
                provider_record["authorization"] = "approved"
            authorization = "approved"
            if command == "movie.storyboard-render":
                from vss_movie_storyboard_render import AdmittedStoryboardRender
                if type(admitted_request) is not AdmittedStoryboardRender:
                    raise InvalidCapabilityInput("storyboard render requires authoritative movie admission")
            elif command == "movie.pictorial-frame-generate":
                from vss_movie_pictorial import AdmittedPictorialFrame
                if environment != "development" or type(admitted_request) is not AdmittedPictorialFrame:
                    raise InvalidCapabilityInput("pictorial frame generation requires authoritative movie admission")
            elif command == "movie.m8-3-real-provider-smoke-2-generate":
                from vss_movie_creative_smoke import AdmittedCreativeSmoke
                if environment != "development" or type(admitted_request) is not AdmittedCreativeSmoke:
                    raise InvalidCapabilityInput("creative smoke generation requires authoritative movie admission")
            elif admitted_request is not None:
                raise InvalidCapabilityInput("admitted request is not valid for this capability")
            provider_access = ProviderAccess()
            for registration in registrations:
                if registration.metadata.provider_type == "clock":
                    provider_access = ProviderAccess(
                        clock=self.provider_registry.initialize(registration),
                    )
                elif registration.metadata.provider_type == "storyboard_render":
                    provider_access = ProviderAccess(storyboard=self.provider_registry.initialize(registration))
                elif registration.metadata.provider_type == "storyboard_image_generation":
                    provider_access = ProviderAccess(pictorial=self.provider_registry.initialize(registration))
            if capability.manifest.identity == "movie.storyboard-render" and "filesystem_write" in authorized:
                artifact_publisher = StoryboardArtifactPublisher(self.root)
            if capability.manifest.identity == "movie.pictorial-frame-generation" and "filesystem_write" in authorized:
                pictorial_artifact_publisher = PictorialArtifactPublisher(self.root)
            creative_smoke_access = None
            if capability.manifest.identity == "movie.m8-3-real-provider-smoke-2":
                if set(authorized) != {"filesystem_write", "network", "secrets"}:
                    raise PermissionDenied("creative smoke requires exact Runtime permissions")
                from vss_movie_creative_smoke import (
                    AUTHORIZED_COST_CEILING_USD,
                    ENDPOINT,
                    MAXIMUM_ESTIMATED_COST_USD,
                    MODEL_IDENTITY,
                    OpenAIImageSmokeAccess,
                    SECRET_NAME,
                    SmokeExperimentArtifactPublisher,
                    SmokeProviderRequest,
                )
                from vss_movie_creative_smoke.provider import _https_post
                import os

                provider_audit.append({
                    "type": "experimental_image_generation",
                    "identity": "openai",
                    "version": MODEL_IDENTITY,
                    "authorization": "approved",
                })
                creative_smoke_access = OpenAIImageSmokeAccess(
                    transport=self.creative_smoke_transport or _https_post,
                    secret_reader=self.creative_smoke_secret_reader or os.environ.get,
                )
                smoke_request = SmokeProviderRequest(
                    prompt=admitted_request.prompt,
                    provider_request_digest=admitted_request.provider_request_digest,
                    depiction_projection_digest=admitted_request.depiction_projection_digest,
                )
                authoritative_request_digest = creative_smoke_access.prepare(smoke_request)
                if "filesystem_write" in authorized:
                    creative_smoke_artifact_publisher = SmokeExperimentArtifactPublisher(self.root)
                    if not dry_run:
                        creative_smoke_artifact_publisher.check_readiness(admitted_request)
                        self.external_execution_preflight.run(ExternalExecutionPreflightSpec(
                            endpoint=ENDPOINT,
                            credential_environment_variable=SECRET_NAME,
                            provider_request_digest=admitted_request.provider_request_digest,
                            authoritative_provider_request_digest=authoritative_request_digest,
                            maximum_provider_attempts=1,
                            maximum_estimated_cost_usd=MAXIMUM_ESTIMATED_COST_USD,
                            authorized_cost_ceiling_usd=AUTHORIZED_COST_CEILING_USD,
                        ))
            if capability.manifest.sdk_api_version is not None:
                try:
                    validate_input(input_data, command_record["input_schema"])
                except SDKValidationError as exc:
                    raise InvalidCapabilityInput(str(exc)) from exc
                context = CapabilityExecutionContext(
                    environment=environment,
                    correlation_id=correlation_id,
                    execution_id=execution_id,
                    capability_identity=capability.manifest.identity,
                    command_identity=command,
                    authorized_permissions=authorized,
                    # M2.3 exposes no configuration keys until an explicit safe
                    # configuration contract is admitted for a capability.
                    safe_configuration=freeze_configuration({}),
                    providers=provider_access,
                    host_inspection=(
                        self.host_inspector
                        if capability.manifest.identity == "bootstrap.check"
                        and set(authorized) == {"filesystem_read", "subprocess"}
                        else None
                    ),
                    artifact_publisher=artifact_publisher,
                    pictorial_artifact_publisher=pictorial_artifact_publisher,
                    creative_smoke_access=creative_smoke_access,
                    creative_smoke_artifact_publisher=creative_smoke_artifact_publisher,
                    admitted_request=admitted_request,
                )
            else:
                context = ExecutionContext(
                    environment=environment,
                    configuration=configuration,
                    correlation_id=correlation_id,
                    declared_permissions=permissions,
                    authorized_permissions=authorized,
                    source_commit=source_commit,
                    verbose=verbose,
                    ask_become_pass=ask_become_pass,
                )
            handler = self.loader.load(capability)
            if creative_smoke_artifact_publisher is not None and not dry_run:
                creative_smoke_artifact_publisher.reserve(admitted_request, execution_id)
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = executor.submit(handler, context, input_data, dry_run)
            try:
                result = future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError as exc:
                future.cancel()
                raise RuntimeTimeout("command timed out") from exc
            except ProviderFailure:
                raise
            except Exception as exc:
                raise CapabilityExecutionFailure("capability execution failed") from exc
            finally:
                executor.shutdown(wait=False, cancel_futures=True)
            if capability.manifest.sdk_api_version is not None:
                if not isinstance(result, CapabilityResult):
                    raise CapabilityExecutionFailure("capability returned an invalid SDK result")
                if result.error is not None:
                    output = {}
                    errors = [result.error.message]
                    status = "error"
                    exit_code = result.error.exit_code
                    result = None
                else:
                    try:
                        result = validate_output(result.output, command_record["output_schema"])
                    except SDKValidationError as exc:
                        raise CapabilityExecutionFailure("capability returned an invalid result") from exc
            elif not isinstance(result, dict):
                raise CapabilityExecutionFailure("capability returned an invalid result")
            else:
                try:
                    result = validate_output(result, command_record["output_schema"])
                except SDKValidationError as exc:
                    raise CapabilityExecutionFailure("capability returned an invalid result") from exc
            if result is None:
                pass
            else:
                output_errors = sorted(
                    Draft202012Validator(command_record["output_schema"]).iter_errors(result),
                    key=lambda error: list(error.path),
                )
                if output_errors:
                    raise CapabilityExecutionFailure("capability returned an invalid result")
                output = result
                status = "success"
                exit_code = ExitCode.SUCCESS
        except (RuntimeFailure, ProviderFailure) as exc:
            exit_code = exc.exit_code
            errors = [str(exc)]
            diagnostic = getattr(exc, "diagnostic", None)
            if capability_identity == "movie.m8-3-real-provider-smoke-2" and diagnostic is not None:
                provider_diagnostic = diagnostic.as_dict()
            bounded_preflight = getattr(exc, "preflight_diagnostic", None)
            if isinstance(bounded_preflight, dict):
                preflight_diagnostic = dict(bounded_preflight)
            if exc.category in ("permission_denied", "provider_access_denied"):
                authorization = "denied"
                for provider_record in provider_audit:
                    provider_record["authorization"] = "denied"
        except Exception:
            exit_code = ExitCode.INTERNAL_ERROR
            errors = ["runtime internal failure"]

        completed_at = utc_now()
        duration_ms = int((time.monotonic() - started_clock) * 1000)
        response = {
            "schema_version": "1",
            "command": command,
            "correlation_id": correlation_id,
            "started_at": started_at,
            "status": status,
            "exit_code": int(exit_code),
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "output": output,
            "errors": errors,
        }
        audit_record = {
            "schema_version": "1",
            "timestamp": completed_at,
            "correlation_id": correlation_id,
            "execution_id": execution_id,
            "capability": capability_identity,
            "command": command,
            "status": status,
            "exit_code": int(exit_code),
            "duration_ms": duration_ms,
            "declared_permissions": list(permissions),
            "authorization": authorization,
            "manifest_sha256": manifest_digest,
            "source_commit": source_commit,
        }
        if provider_audit:
            audit_record["providers"] = provider_audit
        if provider_diagnostic is not None:
            audit_record["provider_diagnostic"] = provider_diagnostic
        if preflight_diagnostic is not None:
            audit_record["external_execution_preflight"] = preflight_diagnostic
        try:
            self.audit.append(audit_record)
        except RuntimeInternalFailure as exc:
            publisher = artifact_publisher or pictorial_artifact_publisher or creative_smoke_artifact_publisher
            if publisher is not None:
                publisher.abort()
            response["status"] = "error"
            response["exit_code"] = int(ExitCode.INTERNAL_ERROR)
            response["output"] = {}
            response["errors"] = [str(exc)]
            return response, int(ExitCode.INTERNAL_ERROR)
        publisher = artifact_publisher or pictorial_artifact_publisher or creative_smoke_artifact_publisher
        if status == "success" and publisher is not None and not dry_run:
            try:
                publisher.publish()
            except RuntimeInternalFailure as exc:
                response["status"] = "error"
                response["exit_code"] = int(ExitCode.INTERNAL_ERROR)
                response["output"] = {}
                response["errors"] = [str(exc)]
                return response, int(ExitCode.INTERNAL_ERROR)
        elif publisher is not None:
            publisher.abort()
        return response, int(exit_code)
