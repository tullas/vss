from __future__ import annotations

import copy
import hashlib
import os
import shutil
import struct
import tempfile
import time
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json

from tests.movie_storyboard.test_m8_0 import bundle, execute as execute_storyboard, reseal_storyboard
from vss_commands import CommandRunner, ExitCode
from vss_commands.cli import main
from vss_movie_pictorial import AdmittedPictorialFrame, admit_pictorial_frame
from vss_providers import GeneratedMedia, PictorialFrameRequest, ProviderAccess, ProviderExecutionFailure
from vss_providers.png import validate_pictorial_png
from vss_runtime import RuntimeController
from vss_runtime.artifacts import PictorialArtifactPublisher
from vss_runtime.audit import AuditLogger
from vss_runtime.errors import CapabilityExecutionFailure, RuntimeInternalFailure
from vss_runtime.policy import RuntimePolicy

ROOT = Path(__file__).resolve().parents[2]


class FailingAudit(AuditLogger):
    def append(self, record):
        raise RuntimeInternalFailure("audit failed")


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)


class M82PictorialFrameTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for name in ("capabilities", "providers", "schemas"):
            shutil.copytree(ROOT / name, self.root / name)
        self.values = bundle(knowledge=True)
        self.storyboard = execute_storyboard(self.values)["scene_storyboard_specification"]
        self.frame = self.storyboard["payload"]["ordered_frames"][0]
        self.payload = dict(zip(("decision", "review_packet", "option_set", "scene_breakdown", "shot_plan"), self.values))
        self.payload.update(storyboard=self.storyboard, frame_id=self.frame["frame_id"])

    def tearDown(self): self.temporary.cleanup()
    def controller(self, **kwargs): return RuntimeController(root=self.root, **kwargs)
    def generate(self, payload=None, controller=None, dry_run=False, timeout=None):
        return CommandRunner(runtime_controller=controller or self.controller()).run(
            "movie.generate-pictorial-frame", "development", payload or self.payload,
            "m82-test", dry_run=dry_run, timeout_seconds=timeout)

    def test_genuine_one_frame_png_is_deterministic_bound_and_non_authoritative(self):
        first, code = self.generate(); self.assertEqual(code, 0, first)
        output = first["output"]; path = self.root / output["artifact_path"]
        content = path.read_bytes()
        self.assertEqual(validate_pictorial_png(content), (640, 360))
        self.assertEqual(hashlib.sha256(content).hexdigest(), output["content_sha256"])
        self.assertEqual(output["frame_id"], self.frame["frame_id"])
        self.assertEqual(output["frame_specification_digest"], self.frame["frame_specification_digest"])
        self.assertEqual(output["provider_call_count"], 1)
        self.assertTrue(all(value is False for value in output["authority_boundary"].values()))
        second, code = self.generate(); self.assertEqual(code, 0, second)
        self.assertEqual(output["content_sha256"], second["output"]["content_sha256"])
        self.assertEqual(content, path.read_bytes())
        self.assertEqual(output["semantic_request_digest"], second["output"]["semantic_request_digest"])
        self.assertNotEqual(output["execution_attempt_id"], second["output"]["execution_attempt_id"])

    def test_adaptation_is_deterministic_minimized_and_admission_unforgeable(self):
        one = admit_pictorial_frame(*self.values, self.storyboard, frame_id=self.frame["frame_id"], environment="development")
        two = admit_pictorial_frame(*self.values, self.storyboard, frame_id=self.frame["frame_id"], environment="development")
        self.assertEqual((one.semantic_request_digest, one.provider_visible_digest),
                         (two.semantic_request_digest, two.provider_visible_digest))
        self.assertEqual(set(one.projection), {"depictable_facts", "required_narrative_emphasis",
            "narrative_context", "deliberate_ambiguities", "creative_degrees_of_freedom", "shot",
            "prohibited_contradictions", "depiction_instructions", "output"})
        self.assertNotIn("review_packet", one.projection); self.assertNotIn("knowledge_influence", one.projection)
        with self.assertRaises(TypeError): AdmittedPictorialFrame(object())
        response, code = self.controller().run("movie.pictorial-frame-generate", "development", {},
            {"admission_id": one.admission_id}, "bypass", "2026-01-01T00:00:00.000Z", 0.0)
        self.assertEqual(code, int(ExitCode.INVALID_INPUT), response)

    def test_dry_run_production_and_caller_injections_fail_closed(self):
        with patch("vss_providers.access.SafePictorialFrameHandle.generate") as generate:
            response, code = self.generate(dry_run=True)
        generate.assert_not_called(); self.assertEqual(code, 0)
        self.assertEqual(response["output"]["provider_call_count"], 0)
        self.assertFalse((self.root / ".local/movie/storyboard-images").exists())
        _, code = CommandRunner(runtime_controller=self.controller()).run(
            "movie.generate-pictorial-frame", "production", self.payload, "production")
        self.assertEqual(code, int(ExitCode.INVALID_INPUT))
        for injected in ({**self.payload, "destination": "../../escape.png"},
                         {**self.payload, "provider": "attacker"},
                         {**self.payload, "final_frame_selection": True}):
            _, code = self.generate(payload=injected); self.assertEqual(code, int(ExitCode.INVALID_INPUT))

    def test_resealed_storyboard_frame_and_knowledge_substitutions_fail(self):
        mutations = []
        for mutate in (lambda f: f.pop(), lambda f: f.append(copy.deepcopy(f[0])), lambda f: f.reverse(),
                       lambda f: f[0].update(frame_id="frame-" + "0" * 24),
                       lambda f: f[0].update(environment="unsupported orbital palace")):
            forged = copy.deepcopy(self.storyboard); mutate(forged["payload"]["ordered_frames"]); reseal_storyboard(forged)
            mutations.append({**self.payload, "storyboard": forged})
        knowledge = copy.deepcopy(self.payload); knowledge["option_set"] = copy.deepcopy(knowledge["option_set"])
        knowledge["option_set"]["knowledge_bindings"][0]["admission_decision_id"] = "substituted"
        from vss_reasoning_contracts import canonical_digest
        knowledge["option_set"]["integrity"]["complete_result_sha256"] = canonical_digest(
            {**knowledge["option_set"], "integrity": {"payload_sha256": knowledge["option_set"]["integrity"]["payload_sha256"]}})
        mutations.append(knowledge)
        for value in mutations:
            _, code = self.generate(payload=value); self.assertEqual(code, int(ExitCode.INVALID_INPUT))

    def test_provider_identity_implementation_version_and_permissions_are_exact(self):
        manifest = self.root / "providers/builtin/movie-storyboard-image-local/provider.yaml"
        original = manifest.read_text()
        for old, new in (("movie.storyboard-image.local", "movie.storyboard-image.evil"),
                         ("vss.local-deterministic-pictorial-png", "evil"),
                         ("version: 1.0.0", "version: 2.0.0")):
            manifest.write_text(original.replace(old, new)); _, code = self.generate(); self.assertNotEqual(code, 0)
            manifest.write_text(original)
        for permissions in (("provider_access",), ("filesystem_write",)):
            policy = RuntimePolicy(allowed_provider_identities=("movie.storyboard-image.local",),
                allowed_capability_permissions={"movie.pictorial-frame-generation": permissions})
            _, code = self.generate(controller=self.controller(policy=policy)); self.assertEqual(code, int(ExitCode.PERMISSION_DENIED))
        registry = self.controller().provider_registry
        registration = registry.resolve("movie.storyboard-image.local")
        registration.implementation_path.write_text(registration.implementation_path.read_text() + "\n# substitution\n")
        from vss_providers import ProviderIncompatible
        with self.assertRaises(ProviderIncompatible): registry.initialize(registration)

    def test_png_boundary_rejects_crc_dimensions_metadata_trailing_and_bombs(self):
        admitted = admit_pictorial_frame(*self.values, self.storyboard, frame_id=self.frame["frame_id"], environment="development")
        registration = self.controller().provider_registry.resolve("movie.storyboard-image.local")
        valid = self.controller().provider_registry.initialize(registration).generate(PictorialFrameRequest(
            admitted.project_id, admitted.scene_id, admitted.storyboard_specification_digest, admitted.frame_id,
            admitted.frame_specification_digest, admitted.semantic_request_digest, admitted.provider_visible_digest,
            admitted.projection)).content
        request = PictorialFrameRequest(admitted.project_id, admitted.scene_id,
            admitted.storyboard_specification_digest, admitted.frame_id, admitted.frame_specification_digest,
            admitted.semantic_request_digest, admitted.provider_visible_digest, admitted.projection)
        exact_provider = self.controller().provider_registry.initialize(registration)
        one_call = ProviderAccess(pictorial=exact_provider).get_pictorial_frame_generator()
        one_call.generate(request)
        from vss_providers import ProviderAccessDenied
        with self.assertRaises(ProviderAccessDenied): one_call.generate(request)
        ihdr_end = 8 + 12 + 13
        bad_crc = bytearray(valid); bad_crc[29] ^= 1
        bad_dimension = valid[:16] + struct.pack(">I", 641) + valid[20:]
        bad_dimension = bad_dimension[:29] + struct.pack(">I", zlib.crc32(bad_dimension[12:29]) & 0xffffffff) + bad_dimension[33:]
        metadata = valid[:ihdr_end] + chunk(b"tEXt", b"secret=value") + valid[ihdr_end:]
        raw_bomb = b"\0" + b"\0" * (640 * 3)
        bomb = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 640, 360, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw_bomb * 361)) + chunk(b"IEND", b"")
        for content in (b"not-png", bytes(bad_crc), bad_dimension, metadata, valid + b"trailing", bomb, b"x" * (2 * 1024 * 1024 + 1)):
            class Fake:
                def generate(self, request): return GeneratedMedia("image/png", content, 640, 360, hashlib.sha256(content).hexdigest())
            with self.assertRaises(ProviderExecutionFailure):
                ProviderAccess(pictorial=Fake()).get_pictorial_frame_generator().generate(PictorialFrameRequest(
                    admitted.project_id, admitted.scene_id, admitted.storyboard_specification_digest,
                    admitted.frame_id, admitted.frame_specification_digest, admitted.semantic_request_digest,
                    admitted.provider_visible_digest, admitted.projection))
        for media_type, digest in (("image/jpeg", hashlib.sha256(valid).hexdigest()), ("image/png", "0" * 64)):
            class Deceptive:
                def generate(self, request): return GeneratedMedia(media_type, valid, 640, 360, digest)
            with self.assertRaises(ProviderExecutionFailure):
                ProviderAccess(pictorial=Deceptive()).get_pictorial_frame_generator().generate(PictorialFrameRequest(
                    admitted.project_id, admitted.scene_id, admitted.storyboard_specification_digest,
                    admitted.frame_id, admitted.frame_specification_digest, admitted.semantic_request_digest,
                    admitted.provider_visible_digest, admitted.projection))

    def test_content_addressed_writer_rejects_symlinks_special_conflict_and_is_idempotent(self):
        digest, frame, content = "a" * 64, "frame-" + "b" * 24, b"png"
        content_digest = hashlib.sha256(content).hexdigest()
        publisher = PictorialArtifactPublisher(self.root)
        relative = publisher.stage(digest, frame, content_digest, content); publisher.publish()
        self.assertEqual(relative, f".local/movie/storyboard-images/{digest}/{frame}/{content_digest}.png")
        publisher = PictorialArtifactPublisher(self.root); self.assertEqual(publisher.stage(digest, frame, content_digest, content), relative)
        destination = self.root / relative; destination.write_bytes(b"conflict")
        with self.assertRaises(CapabilityExecutionFailure): PictorialArtifactPublisher(self.root).stage(digest, frame, content_digest, content)
        destination.unlink()
        if hasattr(os, "mkfifo"):
            os.mkfifo(destination)
            with self.assertRaises(CapabilityExecutionFailure): PictorialArtifactPublisher(self.root).stage(digest, frame, content_digest, content)
            destination.unlink()
        outside = self.root / "outside"; outside.mkdir()
        frame_dir = destination.parent; shutil.rmtree(frame_dir); frame_dir.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(CapabilityExecutionFailure): PictorialArtifactPublisher(self.root).stage(digest, frame, content_digest, content)
        self.assertFalse((outside / f"{content_digest}.png").exists())

        frame_dir.unlink(); frame_dir.mkdir()
        destination = frame_dir / f"{content_digest}.png"
        destination.symlink_to(outside / "target.png")
        with self.assertRaises(CapabilityExecutionFailure): PictorialArtifactPublisher(self.root).stage(digest, frame, content_digest, content)
        self.assertFalse((outside / "target.png").exists())
        destination.unlink()
        external_hardlink = outside / "linked.png"; external_hardlink.write_bytes(content)
        os.link(external_hardlink, destination)
        with self.assertRaises(CapabilityExecutionFailure): PictorialArtifactPublisher(self.root).stage(digest, frame, content_digest, content)

    def test_fixed_parent_symlink_escape_is_rejected_without_external_file(self):
        for boundary in (".local", ".local/movie", ".local/movie/storyboard-images"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as directory:
                repository = Path(directory) / "repository"; repository.mkdir()
                outside = Path(directory) / "outside"; outside.mkdir()
                link = repository / boundary; link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(outside, target_is_directory=True)
                with self.assertRaises(CapabilityExecutionFailure): PictorialArtifactPublisher(repository)
                self.assertEqual(list(outside.iterdir()), [])

    def test_audit_failure_and_timeout_never_publish(self):
        audit = FailingAudit(self.root / ".local/runtime/audit", trusted_root=self.root)
        _, code = self.generate(controller=self.controller(audit_logger=audit))
        self.assertEqual(code, int(ExitCode.INTERNAL_ERROR))
        self.assertEqual(list((self.root / ".local/movie/storyboard-images").rglob("*.png")), [])
        class Slow:
            def generate(self, request): time.sleep(.1); raise RuntimeError("late")
        with patch("vss_providers.registry.ProviderRegistry.initialize", return_value=Slow()):
            _, code = self.generate(controller=self.controller(), timeout=.01)
        self.assertEqual(code, int(ExitCode.TIMEOUT))
        time.sleep(.12)
        self.assertEqual(list((self.root / ".local/movie/storyboard-images").rglob("*.png")), [])

    def test_explicit_cli_uses_real_runtime_path(self):
        paths = {}
        for name in ("decision", "review_packet", "option_set", "scene_breakdown", "shot_plan", "storyboard"):
            path = self.root / f"{name}.json"; path.write_text(json.dumps(self.payload[name])); paths[name] = path
        arguments = ["movie", "generate-pictorial-frame"]
        for name, path in paths.items(): arguments.extend((f"--{name.replace('_', '-')}", str(path)))
        arguments.extend(("--frame-id", self.frame["frame_id"], "--environment", "development",
                          "--correlation-id", "m82-cli"))
        output = StringIO()
        with patch("vss_runtime.RuntimeController", return_value=self.controller()), redirect_stdout(output), redirect_stderr(StringIO()):
            self.assertEqual(main(arguments), 0)
        response = json.loads(output.getvalue())
        self.assertTrue((self.root / response["output"]["artifact_path"]).is_file())


if __name__ == "__main__": unittest.main()
