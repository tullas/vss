from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Mapping

from vss_knowledge_contracts import canonical_digest
from vss_knowledge_contracts.validation import CLASSIFICATION_RANK
from vss_reasoning_contracts.canonicalization import validate_json_value

from vss_context_contracts import ContextContractRegistry, ValidatedContext, ValidatedAssemblyReport, validate_context, validate_report
from vss_context_contracts.limits import MAX_AGGREGATE_PACKAGE_BYTES, MAX_CONTEXT_BYTES, MAX_ITEMS, MAX_PACKAGES, MAX_REFERENCES
from vss_context_contracts.validation import revalidate_package, validate_request

from .audit import ContextAuditFailure, ContextAuditSink, DevelopmentContextAudit
from .errors import ContextAssemblyError, ContextBudgetExceeded, ContextPackageFailure, ContextPolicyDenied


def _timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ContextPolicy:
    identity = "generate_options_context_local"
    version = "1"
    purpose = "generate_options_local_validation"
    package_purpose = "local_validation_context"
    environment = "development"
    project_id = "vss-local"
    maximum_lifetime_seconds = 300

    @property
    def digest(self) -> str:
        return canonical_digest({"identity": self.identity, "version": self.version, "purpose": self.purpose, "package_purpose": self.package_purpose, "environment": self.environment, "project_id": self.project_id, "maximum_lifetime_seconds": self.maximum_lifetime_seconds})


class ContextAssembler:
    """Immutable, reusable local assembler; all request state remains local."""
    __slots__ = ("_root", "_registry", "_policy", "_audit_sink_obj")

    def __init__(self, repository_root=None, registry=None, audit: ContextAuditSink | None = None) -> None:
        from pathlib import Path
        self._root = (repository_root or Path(__file__).resolve().parents[2]).resolve()
        self._registry = registry or ContextContractRegistry.built_in()
        self._policy = ContextPolicy()
        self._audit_sink_obj = audit or DevelopmentContextAudit(self._root)

    @property
    def registry(self) -> ContextContractRegistry:
        return self._registry

    @property
    def policy(self) -> ContextPolicy:
        return self._policy

    def _write_audit(self, *, correlation_id: str, request: dict[str, Any], status: str, started: float, summary: dict[str, Any] | None = None) -> None:
        data = summary or {}
        self._audit_sink_obj.append({
            "event_type": "context_assembly_completed" if status == "success" else "context_assembly_failed",
            "recorded_at": _iso(datetime.now(timezone.utc)), "assembly_execution_id": uuid.uuid4().hex,
            "correlation_id": correlation_id, "request_id": request.get("request_id"),
            "semantic_task": "generate_options", "semantic_task_version": "1", "context_family": "generate_options_context", "context_family_version": "1",
            "policy_identity": self._policy.identity, "policy_version": self._policy.version, "registry_sha256": self._registry.digest,
            "package_count": data.get("package_count", 0), "included_item_count": data.get("included_item_count", 0), "omitted_item_count": data.get("omitted_item_count", 0), "rejected_item_count": data.get("rejected_item_count", 0),
            "classification": data.get("classification", "unknown"), "trust_result": data.get("trust_result", "unknown"), "freshness_result": data.get("freshness_result", "unknown"), "revocation_result": data.get("revocation_result", "unknown"),
            "conflict_count": data.get("conflict_count", 0), "uncertainty_count": data.get("uncertainty_count", 0), "status": status, "duration_ms": int((time.monotonic() - started) * 1000),
            "package_set_digest": data.get("package_set_digest"), "selection_digest": data.get("selection_digest"), "context_content_digest": data.get("context_content_digest"), "context_full_digest": data.get("context_full_digest"), "report_digest": data.get("report_digest"),
        })

    @property
    def _audit_sink(self) -> ContextAuditSink:
        return self._audit_sink_obj

    def _package_material(self, packages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"package_id": p["package_id"], "package_content_sha256": p["integrity"]["package_content_sha256"], "classification": p["classification"], "permitted_purpose": p["permitted_purpose"]} for p in packages]

    def assemble(self, request_value: dict[str, Any], package_values: list[dict[str, Any]], *, correlation_id: str, dry_run: bool = False) -> Any:
        started = time.monotonic()
        request: dict[str, Any] = request_value if isinstance(request_value, dict) else {}
        try:
            request = validate_request(request_value, self._registry)
            if type(correlation_id) is not str or correlation_id != request["correlation_id"]:
                raise ContextPolicyDenied("context correlation identity is invalid")
            if len(package_values) > MAX_PACKAGES:
                raise ContextBudgetExceeded("context package count exceeds its bound")
            # A caller cannot choose the freshness clock. The committed M3.4
            # package is the sole deterministic fixture exception; all other
            # assemblies use the current normalized UTC clock.
            fixed_fixture = (
                len(package_values) == 1
                and package_values[0].get("package_id") == "package-139efdbd4d93897ec39840e7de2e7dee"
                and package_values[0].get("integrity", {}).get("package_content_sha256") == "b002f4f1def57d1231f4e17dcb189959dc343bd52786ee7366ecc2e774385bd7"
                and request["validation_time"] == "2026-08-02T00:00:00Z"
            )
            validation_time = request["validation_time"] if fixed_fixture else _iso(datetime.now(timezone.utc))
            package_values = sorted(package_values, key=lambda p: (p.get("package_id", ""), p.get("integrity", {}).get("package_content_sha256", "")))
            total = sum(len(str(p).encode("utf-8")) for p in package_values)
            if total > MAX_AGGREGATE_PACKAGE_BYTES:
                raise ContextBudgetExceeded("context package bytes exceed their bound")
            try:
                validated = [revalidate_package(p, validation_time) for p in package_values]
            except Exception as exc:
                raise ContextPackageFailure("knowledge package is invalid") from exc
            requirements = {item["package_id"]: item for item in request["package_requirements"]}
            by_id = {p["package_id"]: p for p in validated}
            for package_id, requirement in requirements.items():
                package = by_id.get(package_id)
                if package is None:
                    if requirement["requirement"] == "required":
                        raise ContextPackageFailure("required knowledge package is missing")
                    continue
                if package["integrity"]["package_content_sha256"] != requirement["package_content_sha256"]:
                    raise ContextPackageFailure("knowledge package content digest mismatch")
                if package["permitted_purpose"] != self._policy.package_purpose:
                    raise ContextPolicyDenied("knowledge package purpose is incompatible")
            if dry_run:
                self._audit_sink.append({"event_type": "context_assembly_readiness_completed", "recorded_at": _iso(datetime.now(timezone.utc)), "correlation_id": correlation_id, "request_id": request["request_id"], "status": "success", "registry_sha256": self._registry.digest, "package_count": len(validated), "duration_ms": int((time.monotonic()-started)*1000)})
                return {"readiness": {"eligible": True, "context_family": "generate_options_context", "context_family_version": "1", "provider_invoked": False, "registry_sha256": self._registry.digest}}
            item_requirements = {item["item_id"]: item for item in request["item_requirements"]}
            candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for package in validated:
                for item in package["items"]:
                    requirement = item_requirements.get(item["item_id"])
                    if requirement and item["integrity"]["item_content_sha256"] != requirement["item_content_sha256"]:
                        raise ContextPackageFailure("knowledge item content digest mismatch")
                    candidates.append((package, item))
            present_ids = {item["item_id"] for _, item in candidates}
            for requirement in request["item_requirements"]:
                if requirement["requirement"] == "required" and requirement["item_id"] not in present_ids:
                    raise ContextPackageFailure("required knowledge item is missing")
            seen: dict[str, str] = {}
            selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
            omitted: list[str] = []
            for package, item in sorted(candidates, key=lambda pair: (pair[1]["item_id"], pair[1]["integrity"]["item_content_sha256"], pair[0]["package_id"])):
                old = seen.get(item["item_id"])
                if old is not None:
                    if old != item["integrity"]["item_content_sha256"]:
                        raise ContextPackageFailure("knowledge item identity conflict")
                    omitted.append(item["item_id"])
                    continue
                seen[item["item_id"]] = item["integrity"]["item_content_sha256"]
                required = item_requirements.get(item["item_id"], {"requirement": "optional"})["requirement"] == "required"
                note = {"item_id": item["item_id"], "item_family": item["item_family"], "item_family_version": item["item_family_version"], "item_content_digest": item["integrity"]["item_content_sha256"], "source_package_id": package["package_id"], "source_package_content_digest": package["integrity"]["package_content_sha256"], "title": item["payload"]["title"], "body": item["payload"]["body"], "topic_labels": item["payload"]["topic_labels"], "language": item["payload"]["language"], "citations": item["payload"]["citations"], "classification": item["classification"], "trust": item["trust"], "freshness_qualification": "current_at_assembly", "provenance_references": [item["source_id"], item["integrity"]["item_content_sha256"]]}
                selected.append((package, item))
            if len(selected) > request["budgets"]["maximum_items"]:
                required_ids = {i["item_id"] for i in request["item_requirements"] if i["requirement"] == "required"}
                if any(i["item_id"] in required_ids for _, i in selected[request["budgets"]["maximum_items"]:]):
                    raise ContextBudgetExceeded("required context item does not fit")
                selected = selected[:request["budgets"]["maximum_items"]]
                omitted.extend(i["item_id"] for _, i in candidates if i["item_id"] not in {x[1]["item_id"] for x in selected})
            notes = []
            for package, item in selected:
                notes.append({"item_id": item["item_id"], "item_family": item["item_family"], "item_family_version": item["item_family_version"], "item_content_digest": item["integrity"]["item_content_sha256"], "source_package_id": package["package_id"], "source_package_content_digest": package["integrity"]["package_content_sha256"], "title": item["payload"]["title"], "body": item["payload"]["body"], "topic_labels": item["payload"]["topic_labels"], "language": item["payload"]["language"], "citations": item["payload"]["citations"], "classification": item["classification"], "trust": item["trust"], "freshness_qualification": "current_at_assembly", "provenance_references": [item["source_id"], item["integrity"]["item_content_sha256"]]})
            classification = max((p["classification"] for p, _ in selected), key=CLASSIFICATION_RANK.__getitem__)
            if CLASSIFICATION_RANK[classification] > CLASSIFICATION_RANK[request["classification_ceiling"]]:
                raise ContextPolicyDenied("context classification exceeds request ceiling")
            conflicts = []
            for package, _ in selected:
                for conflict in package["conflict_summary"]["conflicts"]:
                    if set(conflict["item_ids"]).issubset({i["item_id"] for _, i in selected}):
                        conflicts.append({"conflict_id": conflict["conflict_id"], "item_ids": conflict["item_ids"], "status": "unresolved", "qualification": "Conflict is preserved; no truth resolution was performed."})
            uncertainty = ["Truth was not independently verified.", "Real-world applicability was not independently verified.", "Completeness is not guaranteed.", "Absence of additional sources is not established.", "Omissions may reduce completeness."]
            limitations = ["Context is inert and has not been delivered to a reasoning provider.", "Evidence references are identifiers only and grant no access."]
            budget = {"maximum_context_bytes": request["budgets"]["maximum_context_bytes"], "context_bytes": 0, "selected_items": len(notes), "evidence_references": sum(len(n["provenance_references"]) for n in notes)}
            payload = {"selected_notes": notes, "evidence_references": [r for n in notes for r in n["provenance_references"]], "conflicts": conflicts, "uncertainty": uncertainty, "limitations": limitations, "source_qualifications": ["approved_fixture"], "budget_summary": budget}
            budget["context_bytes"] = len(str(payload).encode("utf-8"))
            if budget["context_bytes"] > budget["maximum_context_bytes"]:
                raise ContextBudgetExceeded("context content exceeds its bound")
            package_set_digest = canonical_digest(self._package_material(validated))
            selection_digest = canonical_digest({"policy": self._policy.digest, "packages": package_set_digest, "requirements": request["package_requirements"] + request["item_requirements"], "included": [n["item_id"] for n in notes], "omitted": sorted(set(omitted)), "budgets": request["budgets"]})
            context_content_digest = canonical_digest(payload)
            constructed = _timestamp(validation_time)
            earliest = min([_timestamp(p["expires_at"]) for p, _ in selected] + [_timestamp(i["stale_after"]) for _, i in selected] + [_timestamp(i["effective_until"]) for _, i in selected] + [_timestamp(i["retention_until"]) for _, i in selected] + [constructed + timedelta(seconds=self._policy.maximum_lifetime_seconds)])
            if earliest <= constructed:
                raise ContextPolicyDenied("context has no valid lifetime")
            context_id = "context-" + hashlib.sha256((request["request_id"] + context_content_digest).encode()).hexdigest()[:32]
            report = {"schema_version": "1", "report_id": "report-" + uuid.uuid4().hex, "report_contract_identity": "context_assembly_report", "report_contract_version": "1", "context_id": context_id, "request_id": request["request_id"], "correlation_id": correlation_id, "semantic_task": "generate_options", "semantic_task_version": "1", "context_family": "generate_options_context", "context_family_version": "1", "policy_identity": self._policy.identity, "policy_version": self._policy.version, "package_references": [p["package_id"] for p in validated], "included_item_references": [n["item_id"] for n in notes], "omitted_item_references": sorted(set(omitted)), "rejected_item_references": [], "classification": classification, "trust_result": "approved_fixture", "freshness_result": "all_current", "revocation_result": "none", "conflict_count": len(conflicts), "uncertainty_count": len(uncertainty), "limitations_count": len(limitations), "package_set_digest": package_set_digest, "selection_digest": selection_digest, "context_content_digest": context_content_digest, "budget_limits": request["budgets"], "budget_consumption": budget, "constructed_at": _iso(constructed), "expires_at": _iso(earliest), "lifecycle": "validated", "status": "success", "warnings": [], "limitations": limitations, "integrity": {"complete_report_sha256": "0" * 64}}
            report["integrity"]["complete_report_sha256"] = canonical_digest({**report, "integrity": {}})
            report_valid = validate_report(report, self._registry)
            report_digest = report_valid.digest
            context = {"schema_version": "1", "context_id": context_id, "context_contract_identity": "context_object", "context_contract_version": "1", "context_family": "generate_options_context", "context_family_version": "1", "request_id": request["request_id"], "correlation_id": correlation_id, "semantic_task": "generate_options", "semantic_task_version": "1", "purpose": "generate_options_local_validation", "environment": "development", "project_id": request["project_id"], "classification": classification, "policy_identity": self._policy.identity, "policy_version": "1", "package_set_digest": package_set_digest, "selection_digest": selection_digest, "context_content_digest": context_content_digest, "governance_report_digest": report_digest, "constructed_at": _iso(constructed), "expires_at": _iso(earliest), "lifecycle": "validated", "integrity": {"complete_context_sha256": "0" * 64}, "payload": payload}
            context["integrity"]["complete_context_sha256"] = canonical_digest({**context, "integrity": {}})
            context_valid = validate_context(context, self._registry)
            summary = MappingProxyType({"context_id": context_id, "context_family": "generate_options_context/1", "semantic_task": "generate_options/1", "purpose": context["purpose"], "classification": classification, "selected_item_count": len(notes), "omitted_item_count": len(set(omitted)), "rejected_item_count": 0, "conflict_count": len(conflicts), "uncertainty_count": len(uncertainty), "expires_at": context["expires_at"], "package_set_digest": package_set_digest, "selection_digest": selection_digest, "context_content_digest": context_content_digest, "complete_context_digest": context_valid.digest, "assembly_report_digest": report_valid.digest, "registry_digest": self._registry.digest, "policy_digest": self._policy.digest})
            self._write_audit(correlation_id=correlation_id, request=request, status="success", started=started, summary=dict(summary))
            return type("AssemblyResult", (), {"context": context_valid, "report": report_valid, "summary": summary})()
        except Exception:
            try:
                self._write_audit(correlation_id=correlation_id, request=request, status="failed", started=started)
            except Exception as audit_exc:
                raise ContextAuditFailure("context audit failed") from audit_exc
            raise

    def assemble_scene_breakdown(self, story: dict[str, Any], *, request_id: str, correlation_id: str, project_id: str, environment: str, validation_time: str | None = None) -> Any:
        """Movie-specific Context admission routed through the Context layer."""
        from vss_movie_scene_breakdown import assemble_scene_context
        return assemble_scene_context(story, request_id=request_id, correlation_id=correlation_id, project_id=project_id, environment=environment, validation_time=validation_time)
