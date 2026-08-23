from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.movie_storyboard.test_m8_0 import STORY, bundle, execute as execute_storyboard, reseal_storyboard
from vss_commands import CommandRunner, ExitCode
from vss_commands.cli import main
from vss_movie_storyboard_render import AdmittedStoryboardRender, admit_storyboard_render
from vss_providers import GeneratedMedia, ProviderAccess, ProviderExecutionFailure, StoryboardRenderRequest
from vss_runtime import RuntimeController
from vss_runtime.audit import AuditLogger
from vss_runtime.errors import RuntimeInternalFailure
from vss_runtime.errors import CapabilityExecutionFailure
from vss_runtime.artifacts import StoryboardArtifactPublisher
from vss_runtime.policy import RuntimePolicy

ROOT = Path(__file__).resolve().parents[2]


class FailingAudit(AuditLogger):
    def append(self, record):
        raise RuntimeInternalFailure("runtime audit record could not be written")


class M81StoryboardRenderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        shutil.copytree(ROOT / "capabilities", self.root / "capabilities")
        shutil.copytree(ROOT / "providers", self.root / "providers")
        shutil.copytree(ROOT / "schemas", self.root / "schemas")
        self.values = bundle()
        self.storyboard = execute_storyboard(self.values)["scene_storyboard_specification"]
        self.payload = dict(zip(("decision", "review_packet", "option_set", "scene_breakdown", "shot_plan"), self.values))
        self.payload["storyboard"] = self.storyboard

    def tearDown(self):
        self.temporary.cleanup()

    def controller(self, **kwargs):
        return RuntimeController(root=self.root, **kwargs)

    def render(self, *, dry_run=False, controller=None, payload=None, timeout=None):
        return CommandRunner(runtime_controller=controller or self.controller()).run(
            "movie.render-storyboard", "development", payload or self.payload,
            "m81-test", dry_run=dry_run, timeout_seconds=timeout,
        )

    def test_deterministic_parseable_three_frame_svg_and_exact_bindings(self):
        first, code = self.render()
        self.assertEqual(code, 0, first)
        path = self.root / first["output"]["artifact_path"]
        content = path.read_bytes()
        self.assertEqual(hashlib.sha256(content).hexdigest(), first["output"]["content_sha256"])
        root = ET.fromstring(content)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        frames = self.storyboard["payload"]["ordered_frames"]
        positions = [content.index(frame["frame_id"].encode()) for frame in frames]
        self.assertEqual(positions, sorted(positions))
        for frame, binding in zip(frames, first["output"]["frame_bindings"]):
            self.assertEqual(binding, {k: frame[k] for k in ("frame_id", "frame_specification_digest")})
            self.assertIn(frame["frame_specification_digest"].encode(), content)
        repeated, code = self.render()
        self.assertEqual(code, 0, repeated)
        self.assertEqual(first["output"], repeated["output"])
        self.assertEqual(content, path.read_bytes())

    def test_artifact_writer_fixed_parent_containment_and_normal_creation(self):
        digest, content = "a" * 64, b"<svg/>"
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repository"; repository.mkdir()
            publisher = StoryboardArtifactPublisher(repository)
            relative = publisher.stage(digest, content); publisher.publish()
            self.assertEqual(relative, f".local/movie/storyboards/{digest}/storyboard.svg")
            self.assertEqual((repository / relative).read_bytes(), content)
            self.assertEqual(stat.S_IMODE((repository / ".local").stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((repository / relative).stat().st_mode), 0o600)

        for boundary in (".local", ".local/movie", ".local/movie/storyboards"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as directory:
                base = Path(directory); repository = base / "repository"; repository.mkdir()
                outside = base / "outside/deep/.local/movie/storyboards"; outside.mkdir(parents=True)
                redirect = repository / boundary; redirect.parent.mkdir(parents=True, exist_ok=True)
                redirect.symlink_to(outside, target_is_directory=True)
                with self.assertRaises(CapabilityExecutionFailure):
                    StoryboardArtifactPublisher(repository)
                self.assertFalse((outside / digest / "storyboard.svg").exists())

    def test_artifact_writer_digest_destination_special_conflict_and_idempotency(self):
        digest, content = "b" * 64, b"<svg/>"
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory); outside = repository / "outside"; outside.mkdir()
            root = repository / ".local/movie/storyboards"; root.mkdir(parents=True)
            digest_path = root / digest; digest_path.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(CapabilityExecutionFailure):
                StoryboardArtifactPublisher(repository).stage(digest, content)
            self.assertFalse((outside / "storyboard.svg").exists())
            digest_path.unlink(); digest_path.mkdir()
            destination = digest_path / "storyboard.svg"; destination.symlink_to(outside / "target.svg")
            with self.assertRaises(CapabilityExecutionFailure):
                StoryboardArtifactPublisher(repository).stage(digest, content)
            self.assertFalse((outside / "target.svg").exists())
            destination.unlink()
            if hasattr(os, "mkfifo"):
                os.mkfifo(destination)
                with self.assertRaises(CapabilityExecutionFailure):
                    StoryboardArtifactPublisher(repository).stage(digest, content)
                destination.unlink()
            destination.write_bytes(b"conflicting")
            with self.assertRaises(CapabilityExecutionFailure):
                StoryboardArtifactPublisher(repository).stage(digest, content)
            destination.write_bytes(content)
            publisher = StoryboardArtifactPublisher(repository)
            relative = publisher.stage(digest, content); publisher.publish()
            self.assertEqual(relative, f".local/movie/storyboards/{digest}/storyboard.svg")
            self.assertEqual(destination.read_bytes(), content)

    def test_dry_run_and_production_fail_without_provider_or_write(self):
        with patch("vss_providers.access.SafeStoryboardRenderHandle.render") as render:
            response, code = self.render(dry_run=True)
        render.assert_not_called()
        self.assertEqual((code, response["output"]["review_media_status"]), (0, "validation_only"))
        self.assertFalse((self.root / ".local/movie/storyboards").exists())
        response, code = CommandRunner(runtime_controller=self.controller()).run(
            "movie.render-storyboard", "production", self.payload, "m81-production")
        self.assertEqual(code, int(ExitCode.INVALID_INPUT))

    def test_public_boundary_rejects_direct_projection_and_authority_injection(self):
        admitted = admit_storyboard_render(*self.values, self.storyboard, environment="development")
        response, code = self.controller().run(
            "movie.storyboard-render", "development", {}, {"admission_id": admitted.admission_id},
            "bypass", "2026-01-01T00:00:00.000Z", 0.0,
        )
        self.assertEqual(code, int(ExitCode.INVALID_INPUT))
        with self.assertRaises(TypeError):
            AdmittedStoryboardRender(object(), admission_id="0" * 64, project_id="p", scene_id="s",
                                      storyboard_specification_digest="0" * 64, frames=())
        forged = copy.deepcopy(self.storyboard)
        forged["payload"]["authority_boundary"]["media_generation_authority"] = True
        reseal_storyboard(forged)
        response, code = self.render(payload={**self.payload, "storyboard": forged})
        self.assertEqual(code, int(ExitCode.INVALID_INPUT))
        response, code = self.render(payload={**self.payload, "destination": "../../escape.svg"})
        self.assertEqual(code, int(ExitCode.INVALID_INPUT))

    def test_resealed_frame_and_upstream_substitutions_fail_closed(self):
        mutations = []
        for mutate in (
            lambda frames: frames.pop(), lambda frames: frames.append(copy.deepcopy(frames[-1])),
            lambda frames: frames.reverse(), lambda frames: frames[0].update({"frame_id": "frame-" + "0" * 24}),
            lambda frames: frames[0].update({"environment": "unsupported orbital palace"}),
        ):
            forged = copy.deepcopy(self.storyboard); mutate(forged["payload"]["ordered_frames"]); reseal_storyboard(forged)
            mutations.append({**self.payload, "storyboard": forged})
        upstream = copy.deepcopy(self.payload)
        upstream["decision"] = copy.deepcopy(upstream["decision"])
        upstream["decision"]["request_id"] = "validly-resealed-substitution"
        from vss_reasoning_contracts import canonical_digest
        upstream["decision"]["integrity"]["complete_result_sha256"] = canonical_digest(
            {**upstream["decision"], "integrity": {"payload_sha256": upstream["decision"]["integrity"]["payload_sha256"]}}
        )
        mutations.append(upstream)
        for payload in mutations:
            with self.subTest(index=mutations.index(payload)):
                _, code = self.render(payload=payload)
                self.assertEqual(code, int(ExitCode.INVALID_INPUT))

    def test_provider_manifest_implementation_permission_and_digest_attacks(self):
        manifest = self.root / "providers/builtin/movie-storyboard-render-local/provider.yaml"
        original = manifest.read_text()
        for old, new in (("movie.storyboard-render.local", "movie.storyboard-render.evil"),
                         ("vss.local-deterministic-storyboard-svg", "evil-renderer"),
                         ("version: 1.0.0", "version: 9.0.0")):
            manifest.write_text(original.replace(old, new))
            _, code = self.render(controller=self.controller())
            self.assertNotEqual(code, 0)
            manifest.write_text(original)
        denied = RuntimePolicy(allowed_provider_identities=(), allowed_capability_permissions={"movie.storyboard-render": ("provider_access", "filesystem_write")})
        _, code = self.render(controller=self.controller(policy=denied)); self.assertEqual(code, int(ExitCode.PERMISSION_DENIED))
        denied = RuntimePolicy(allowed_provider_identities=("movie.storyboard-render.local",), allowed_capability_permissions={"movie.storyboard-render": ("provider_access",)})
        _, code = self.render(controller=self.controller(policy=denied)); self.assertEqual(code, int(ExitCode.PERMISSION_DENIED))
        registry = self.controller().provider_registry
        registration = registry.resolve("movie.storyboard-render.local")
        implementation = registration.implementation_path
        implementation.write_text(implementation.read_text() + "\n# substituted after resolution\n")
        from vss_providers import ProviderIncompatible
        with self.assertRaises(ProviderIncompatible):
            registry.initialize(registration)

    def test_provider_output_rejects_digest_type_malformed_active_and_external_svg(self):
        admitted = admit_storyboard_render(*self.values, self.storyboard, environment="development")
        request = StoryboardRenderRequest(admitted.project_id, admitted.scene_id, admitted.storyboard_specification_digest, admitted.frames)
        class Fake:
            def __init__(self, content, media="image/svg+xml", digest=None): self.content, self.media, self.digest = content, media, digest
            def render(self, request):
                return GeneratedMedia(self.media, self.content, 1200, 1500, self.digest or hashlib.sha256(self.content).hexdigest())
        samples = ((b"<svg", "image/svg+xml", None),
                   (b'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1500"><script/></svg>', "image/svg+xml", None),
                   (b'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1500"><image href="https://evil"/></svg>', "image/svg+xml", None),
                   (b'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1500"/>', "image/png", None),
                   (b'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1500"/>', "image/svg+xml", "0" * 64),
                   (b"x" * 262145, "image/svg+xml", None))
        for content, media, digest in samples:
            with self.subTest(content=content), self.assertRaises(ProviderExecutionFailure):
                ProviderAccess(storyboard=Fake(content, media, digest)).get_storyboard_renderer().render(request)

    def test_source_xml_injection_is_escaped_and_svg_remains_inert(self):
        admitted = admit_storyboard_render(*self.values, self.storyboard, environment="development")
        registration = self.controller().provider_registry.resolve("movie.storyboard-render.local")
        provider = self.controller().provider_registry.initialize(registration)
        frames = list(admitted.frames)
        frame = dict(frames[0]); frame["subject_focus"] = '<script>alert(1)</script><image href="https://evil">'; frames[0] = frame
        media = provider.render(StoryboardRenderRequest(admitted.project_id, admitted.scene_id, admitted.storyboard_specification_digest, tuple(frames)))
        ET.fromstring(media.content)
        self.assertNotIn(b"<script>", media.content); self.assertNotIn(b"https://evil", media.content)

    def test_filesystem_symlink_special_conflict_audit_and_timeout_fail_closed(self):
        digest = self.storyboard["payload"]["storyboard_specification_digest"]
        directory = self.root / ".local/movie/storyboards"; directory.mkdir(parents=True)
        target = directory / digest
        target.symlink_to(self.root)
        _, code = self.render(); self.assertNotEqual(code, 0)
        target.unlink(); target.mkdir(); (target / "storyboard.svg").write_bytes(b"conflict")
        _, code = self.render(); self.assertNotEqual(code, 0)
        (target / "storyboard.svg").unlink(); target.rmdir()
        audit = FailingAudit(self.root / ".local/runtime/audit", trusted_root=self.root)
        _, code = self.render(controller=self.controller(audit_logger=audit)); self.assertEqual(code, int(ExitCode.INTERNAL_ERROR))
        self.assertFalse((directory / digest / "storyboard.svg").exists())
        class SlowProvider:
            def render(self, request):
                import time
                time.sleep(.1)
                raise RuntimeError("cancelled execution completed late")
        # Runtime timeout is cooperative-only: the worker may finish, but cannot publish afterward.
        with patch("vss_providers.registry.ProviderRegistry.initialize", return_value=SlowProvider()):
            _, code = self.render(controller=self.controller(), timeout=.01)
        self.assertEqual(code, int(ExitCode.TIMEOUT))
        self.assertFalse((directory / digest / "storyboard.svg").exists())

    def test_knowledge_lineage_mutation_fails_closed(self):
        values = bundle(knowledge=True)
        storyboard = execute_storyboard(values)["scene_storyboard_specification"]
        payload = dict(zip(("decision", "review_packet", "option_set", "scene_breakdown", "shot_plan"), values))
        payload["storyboard"] = storyboard
        payload["option_set"] = copy.deepcopy(payload["option_set"])
        payload["option_set"]["knowledge_bindings"][0]["admission_decision_id"] = "substituted-admission"
        from vss_reasoning_contracts import canonical_digest
        payload["option_set"]["integrity"]["complete_result_sha256"] = canonical_digest(
            {**payload["option_set"], "integrity": {"payload_sha256": payload["option_set"]["integrity"]["payload_sha256"]}}
        )
        _, code = self.render(payload=payload)
        self.assertEqual(code, int(ExitCode.INVALID_INPUT))

    def test_committed_fixture_demo_render_flag_uses_real_path(self):
        stdout = StringIO()
        args = ["movie", "demo", "--story", str(STORY), "--reviewer-id", "m81.reviewer",
                "--correlation-id", "m81-e2e", "--option-id", "option-802bf5f0a0d8df08c1376b91",
                "--render-storyboard"]
        with patch("vss_runtime.RuntimeController", return_value=self.controller()), \
                redirect_stdout(stdout), redirect_stderr(StringIO()):
            self.assertEqual(main(args), 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["storyboard_render"]["review_media_status"], "development_review_media")
        self.assertTrue((self.root / result["storyboard_render"]["artifact_path"]).is_file())
        self.assertEqual(len(result["scene_storyboard_specification"]["payload"]["ordered_frames"]), 3)

    def test_standalone_cli_renders_and_dry_run_has_no_effect(self):
        arguments = ["movie", "render-storyboard"]
        names = ("decision", "review-packet", "option-set", "scene-breakdown", "shot-plan", "storyboard")
        values = (*self.values, self.storyboard)
        for name, value in zip(names, values):
            path = self.root / f"{name}.json"
            path.write_text(json.dumps(value))
            arguments.extend((f"--{name}", str(path)))
        arguments.extend(("--environment", "development", "--correlation-id", "m81-cli"))
        stdout = StringIO()
        with patch("vss_runtime.RuntimeController", return_value=self.controller()), redirect_stdout(stdout):
            self.assertEqual(main(arguments), 0)
        response = json.loads(stdout.getvalue())
        self.assertEqual(response["output"]["media_type"], "image/svg+xml")
        fresh = self.controller()
        with patch("vss_runtime.RuntimeController", return_value=fresh), redirect_stdout(StringIO()):
            self.assertEqual(main(arguments + ["--dry-run"]), 0)


if __name__ == "__main__":
    unittest.main()
