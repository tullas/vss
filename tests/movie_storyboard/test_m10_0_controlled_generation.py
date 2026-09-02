from __future__ import annotations

import base64
import copy
import hashlib
import json
import shutil
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

from vss_commands import CommandRunner, ExitCode
from vss_movie_controlled_generation import (
    APPROVER_SECRET_NAME, SECRET_NAME, admit_controlled_generation, admit_generated_candidate,
    admit_grounded_controlled_generation, issue_approval,
)
from vss_movie_controlled_generation.contracts import validate_candidate_media
from vss_movie_demo import finish_demo, prepare_demo
from vss_movie_storyboard import (
    admit_grounded_storyboard_asset,
    create_grounded_storyboard_comparison,
    record_development_review_selection,
    record_grounded_storyboard_promotion,
    register_grounded_storyboard_asset, lookup_grounded_storyboard_asset,
    bind_grounded_storyboard_asset_to_shot,
)
from vss_movie_visual_grounding import (
    create_grounded_movie_route,
    create_production_visual_grounding_profile,
    create_revised_production_visual_grounding_profile,
    record_production_visual_grounding_review,
)
from vss_movie_creative_smoke.provider import SmokeHTTPResponse
from vss_runtime import RuntimeController, RuntimePolicy
from vss_runtime.audit import AuditLogger
from vss_runtime.errors import RuntimeInternalFailure
from vss_runtime.external_preflight import ExternalExecutionPreflight
from vss_providers import ControlledFrameRequest, ControlledFrameResult, GeneratedMedia, ProviderAccess
from vss_providers.errors import ControlledFrameProviderFailure
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts.canonicalization import freeze_json
from vss_resource_contracts import ResourceContractError


ROOT = Path(__file__).resolve().parents[2]
APPROVER_SECRET = "test-only-approver-key-material-00000001"  # pragma: allowlist secret
PROVIDER_SECRET = "test-only-provider-key"  # pragma: allowlist secret


class FailingAudit(AuditLogger):
    def append(self, record):
        raise RuntimeInternalFailure("controlled test audit failed")


def _chunk(kind: bytes, content: bytes) -> bytes:
    return (struct.pack(">I", len(content)) + kind + content
            + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF))


def png(*, cabx: bytes | tuple[bytes, ...] | None = None, width: int = 1280,
        compressed: bytes | None = None) -> bytes:
    header = struct.pack(">IIBBBBB", width, 720, 8, 2, 0, 0, 0)
    pixels = (b"\0" + b"\0" * (width * 3)) * 720
    chunks = [_chunk(b"IHDR", header)]
    if cabx is not None:
        for payload in cabx if isinstance(cabx, tuple) else (cabx,):
            chunks.append(_chunk(b"caBX", payload))
    chunks.extend((_chunk(b"IDAT", compressed if compressed is not None else zlib.compress(pixels)),
                   _chunk(b"IEND", b"")))
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def response(content: bytes) -> SmokeHTTPResponse:
    value = {
        "created": 42,
        "data": [{"b64_json": base64.b64encode(content).decode("ascii"), "revised_prompt": None}],
        "usage": {"input_tokens": 325, "output_tokens": 1200, "total_tokens": 1525,
                  "input_tokens_details": {"text_tokens": 325, "image_tokens": 0},
                  "output_tokens_details": {"text_tokens": 0, "image_tokens": 1200}},
        "background": "opaque", "output_format": "png", "quality": "medium", "size": "1280x720",
    }
    return SmokeHTTPResponse(json.dumps(value).encode("utf-8"), 200, "req_m10_safe")


class M100ControlledGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        story = json.loads((ROOT / "tests/fixtures/movie/story-fragment-valid.json").read_text())
        prepared = prepare_demo(story, correlation_id="m10-real-path")
        option_id = prepared.review_packet["payload"]["review_entries"][0]["option_id"]
        finished = finish_demo(
            prepared, option_id=option_id, reviewer_id="reviewer-m10",
            rationale="Accepted for controlled external review candidate test.",
            correlation_id="m10-real-path", include_storyboard=True,
        )
        cls.base_payload = {
            "story": prepared.story, "decision": finished["review_decision"],
            "review_packet": finished["review_packet"], "option_set": finished["scene_production_option_set"],
            "scene_breakdown": finished["scene_breakdown"],
            "creative_decision": finished["creative_decision_revision"],
            "canon_snapshot": finished["canon_snapshot"], "canon_binding": finished["production_canon_binding"],
            "shot_plan": finished["scene_shot_plan_draft"],
            "storyboard": finished["scene_storyboard_specification"],
            "frame_id": finished["scene_storyboard_specification"]["payload"]["ordered_frames"][0]["frame_id"],
        }
        scene = finished["scene_breakdown"]["payload"]["ordered_scenes"][0]
        cls.grounding_profile = create_production_visual_grounding_profile(
            profile_id="visual-grounding-production-alpha", revision=1,
            tenant_id="tenant-local", universe_id="universe-local",
            production_id=prepared.story["project_id"], mode="required",
            scene_ids=[scene["scene_id"]], character_ids=list(scene["declared_characters"]),
            groups=[{
                "ordinal": 1, "group_id": "production.group-alpha",
                "positive_constraints": ["Apply production-defined visual token ALPHA-POSITIVE."],
                "negative_constraints": ["Exclude production-defined visual token ALPHA-NEGATIVE."],
                "explicit_unknowns": ["Production-defined visual token ALPHA-UNKNOWN remains unresolved."],
                "limitations": ["Opaque production test constraint; VSS assigns no domain meaning."],
                "source_reference_digests": [canonical_digest({"source": "opaque-alpha"})],
            }],
            uncertainty=["The opaque production constraint is not independently verified."],
            limitations=["Opaque production-owned test data."],
            evidence_references=["evidence.opaque-alpha"],
            reviewer_accountability_id="reviewer-grounding",
        ).to_json_value()
        route = create_grounded_movie_route(
            finished["review_decision"], finished["review_packet"],
            finished["scene_production_option_set"], finished["scene_breakdown"],
            finished["creative_decision_revision"], finished["canon_snapshot"],
            finished["production_canon_binding"], finished["scene_shot_plan_draft"],
            finished["scene_storyboard_specification"], profile_data=cls.grounding_profile,
        )
        cls.grounded_payload = {
            **cls.base_payload, "profile": cls.grounding_profile,
            "grounded_creative_decision": route.creative_decision.to_json_value(),
            "grounded_canon_snapshot": route.canon_snapshot.to_json_value(),
            "grounded_canon_binding": route.canon_binding.to_json_value(),
            "grounded_shot_plan": route.shot_plan.to_json_value(),
            "grounded_storyboard": route.storyboard.to_json_value(),
        }

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for name in ("capabilities", "providers", "schemas"):
            shutil.copytree(ROOT / name, self.root / name)
        self.calls = []
        self.provider_secret_reads = []
        self.approver_secret_reads = []

    def tearDown(self):
        self.temporary.cleanup()

    def admit(self, payload=None, approval=None):
        value = payload or self.base_payload
        return admit_controlled_generation(
            value["story"], value["decision"], value["review_packet"], value["option_set"],
            value["scene_breakdown"], value["creative_decision"], value["canon_snapshot"],
            value["canon_binding"], value["shot_plan"], value["storyboard"],
            frame_id=value["frame_id"], environment="development", approval=approval,
        )

    def admit_grounded(self, payload=None, approval=None):
        value = payload or self.grounded_payload
        return admit_grounded_controlled_generation(
            value["story"], value["decision"], value["review_packet"], value["option_set"],
            value["scene_breakdown"], value["creative_decision"], value["canon_snapshot"],
            value["canon_binding"], value["shot_plan"], value["storyboard"],
            profile_data=value["profile"],
            grounded_creative_decision_data=value["grounded_creative_decision"],
            grounded_canon_snapshot_data=value["grounded_canon_snapshot"],
            grounded_canon_binding_data=value["grounded_canon_binding"],
            grounded_shot_plan_data=value["grounded_shot_plan"],
            grounded_storyboard_data=value["grounded_storyboard"],
            frame_id=value["frame_id"], environment="development", approval=approval,
        )

    def test_domain_neutral_grounded_route_is_deterministic_and_minimal(self):
        first = self.admit_grounded()
        second = self.admit_grounded()
        self.assertEqual(first.request_json(), second.request_json())
        self.assertEqual(first.request["contract_version"], "3")
        self.assertIn("ALPHA-POSITIVE", first.prompt)
        self.assertIn("ALPHA-NEGATIVE", first.prompt)
        self.assertIn("ALPHA-UNKNOWN", first.prompt)
        for hidden in ("production.group-alpha", "reviewer-grounding", "evidence.opaque-alpha"):
            self.assertNotIn(hidden, first.prompt)
        self.assertEqual(
            first.request["projection"]["visual_grounding_profile_sha256"],
            self.grounding_profile["profile_sha256"],
        )
        self.assertEqual(self.admit().request["contract_version"], "2")

    def test_grounded_real_path_fake_provider_admits_candidate(self):
        base = self.admit_grounded()
        admitted = self.admit_grounded(approval=self.approval(base))
        result, code = self.runtime(admitted, mode="generate")
        self.assertEqual(code, 0, result)
        self.assertEqual(len(self.calls), 1)
        provider_request = json.loads(self.calls[0][1])
        self.assertIn("ALPHA-POSITIVE", provider_request["prompt"])
        candidate = json.loads((self.root / result["output"]["candidate"]).read_text())
        self.assertEqual(
            candidate["lineage"]["storyboard_specification"],
            admitted.request["lineage"]["storyboard_specification"],
        )
        self.assertTrue(all(value is False for value in candidate["authority"].values()))

    def test_grounding_substitution_and_scope_mismatch_fail_before_effect(self):
        substituted = copy.deepcopy(self.grounded_payload)
        substituted["profile"]["groups"][0]["positive_constraints"][0] = "RESEALED-SUBSTITUTION"
        substituted["profile"]["profile_sha256"] = canonical_digest({
            **substituted["profile"], "profile_sha256": "0" * 64,
        })
        with self.assertRaises(Exception):
            self.admit_grounded(substituted)

        cross_tenant = copy.deepcopy(self.grounded_payload)
        cross_tenant["profile"]["scope"]["tenant_id"] = "tenant-other"
        cross_tenant["profile"]["profile_sha256"] = canonical_digest({
            **cross_tenant["profile"], "profile_sha256": "0" * 64,
        })
        with self.assertRaises(Exception):
            self.admit_grounded(cross_tenant)

        resealed_overlay = copy.deepcopy(self.grounded_payload)
        overlay = resealed_overlay["grounded_storyboard"]
        frame = overlay["ordered_frame_grounding"][0]
        frame["positive_constraints"][0] = "RESEALED-OVERLAY-SUBSTITUTION"
        frame["frame_grounding_sha256"] = canonical_digest({
            key: item for key, item in frame.items() if key != "frame_grounding_sha256"
        })
        semantic = {key: item for key, item in overlay.items()
                    if key not in {"schema_version", "result_family", "result_version",
                                   "project_id", "scene_id", "integrity"}}
        overlay["integrity"]["payload_sha256"] = canonical_digest(semantic)
        overlay["integrity"]["complete_result_sha256"] = canonical_digest({
            **overlay, "integrity": {"payload_sha256": overlay["integrity"]["payload_sha256"]},
        })
        with self.assertRaises(Exception):
            self.admit_grounded(resealed_overlay)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.provider_secret_reads, [])
        self.assertEqual(self.approver_secret_reads, [])

    def test_conflicting_or_revoked_required_grounding_fails_closed(self):
        common = {
            "profile_id": "visual-grounding-unavailable", "revision": 1,
            "tenant_id": "tenant-local", "universe_id": "universe-local",
            "production_id": self.base_payload["story"]["project_id"], "mode": "required",
            "groups": [{
                "ordinal": 1, "group_id": "production.group-unavailable",
                "positive_constraints": ["Opaque positive value."],
                "negative_constraints": ["Opaque exclusion value."],
                "explicit_unknowns": [], "limitations": ["Opaque limitation."],
                "source_reference_digests": [canonical_digest({"source": "unavailable"})],
            }], "reviewer_accountability_id": "reviewer-grounding",
        }
        profiles = (
            create_production_visual_grounding_profile(
                **common, conflicts=["Production reports an unresolved conflict."]).to_json_value(),
            create_production_visual_grounding_profile(
                **common, lifecycle="revoked").to_json_value(),
        )
        for profile in profiles:
            with self.subTest(profile=profile["lifecycle"],), self.assertRaises(Exception):
                create_grounded_movie_route(
                    self.base_payload["decision"], self.base_payload["review_packet"],
                    self.base_payload["option_set"], self.base_payload["scene_breakdown"],
                    self.base_payload["creative_decision"], self.base_payload["canon_snapshot"],
                    self.base_payload["canon_binding"], self.base_payload["shot_plan"],
                    self.base_payload["storyboard"], profile_data=profile,
                )
        self.assertEqual(self.calls, [])
        self.assertEqual(self.provider_secret_reads, [])

    def test_required_grounding_cannot_be_replaced_by_not_required_profile(self):
        profile = create_production_visual_grounding_profile(
            profile_id="visual-grounding-not-required", revision=1,
            tenant_id="tenant-local", universe_id="universe-local",
            production_id=self.base_payload["story"]["project_id"], mode="not_required",
            groups=[], reviewer_accountability_id="reviewer-grounding",
        ).to_json_value()
        route = create_grounded_movie_route(
            self.base_payload["decision"], self.base_payload["review_packet"],
            self.base_payload["option_set"], self.base_payload["scene_breakdown"],
            self.base_payload["creative_decision"], self.base_payload["canon_snapshot"],
            self.base_payload["canon_binding"], self.base_payload["shot_plan"],
            self.base_payload["storyboard"], profile_data=profile,
        )
        payload = {
            **self.base_payload, "profile": profile,
            "grounded_creative_decision": route.creative_decision.to_json_value(),
            "grounded_canon_snapshot": route.canon_snapshot.to_json_value(),
            "grounded_canon_binding": route.canon_binding.to_json_value(),
            "grounded_shot_plan": route.shot_plan.to_json_value(),
            "grounded_storyboard": route.storyboard.to_json_value(),
        }
        with self.assertRaisesRegex(Exception, "requires declared required grounding"):
            self.admit_grounded(payload)
        self.assertEqual(self.admit().request["contract_version"], "2")

    def test_grounding_review_defects_are_production_defined_and_inert(self):
        base = self.admit_grounded()
        admitted = self.admit_grounded(approval=self.approval(base))
        result, code = self.runtime(admitted, mode="generate")
        self.assertEqual(code, 0, result)
        candidate = admit_generated_candidate(self.root, admitted)
        calls = len(self.calls)
        review = record_production_visual_grounding_review(
            generation=admitted, candidate=candidate, disposition="REJECT",
            defects=[{
                "defect_code": "production.defect-alpha", "group_id": "production.group-alpha",
                "rationale": "Production-owned review evidence with opaque semantics.",
            }], reviewer_accountability_id="reviewer-grounding",
        )
        self.assertEqual(review.value["defects"][0]["defect_code"], "production.defect-alpha")
        self.assertTrue(all(value is False for value in review.value["authority"].values()))
        self.assertNotIn("approval", review.value["defects"][0])
        self.assertEqual(len(self.calls), calls)

    def test_human_authored_revised_profile_binds_review_and_second_candidate(self):
        first = self.admit_grounded()
        first_admitted = self.admit_grounded(approval=self.approval(first))
        first_result, first_code = self.runtime(first_admitted, mode="generate")
        self.assertEqual(first_code, 0, first_result)
        first_candidate = admit_generated_candidate(self.root, first_admitted)
        first_review = record_production_visual_grounding_review(
            generation=first_admitted, candidate=first_candidate, disposition="REGENERATE",
            defects=[{
                "defect_code": "production.defect-alpha", "group_id": "production.group-alpha",
                "rationale": "Opaque production-owned correction for the next review candidate.",
            }], reviewer_accountability_id="reviewer-grounding",
        )
        revised_profile = create_revised_production_visual_grounding_profile(
            predecessor_profile=self.grounding_profile, review=first_review,
            profile_id="visual-grounding-production-alpha", revision=2,
            tenant_id="tenant-local", universe_id="universe-local",
            production_id=self.base_payload["story"]["project_id"], mode="required",
            scene_ids=[self.base_payload["scene_breakdown"]["payload"]["ordered_scenes"][0]["scene_id"]],
            character_ids=list(self.base_payload["scene_breakdown"]["payload"]["ordered_scenes"][0]["declared_characters"]),
            groups=[{
                "ordinal": 1, "group_id": "production.group-alpha",
                "positive_constraints": ["Apply revised opaque production visual token ALPHA-BETA."],
                "negative_constraints": ["Exclude production-defined visual token ALPHA-NEGATIVE."],
                "explicit_unknowns": ["Production-defined visual token ALPHA-UNKNOWN remains unresolved."],
                "limitations": ["Opaque production revision; VSS assigns no domain meaning."],
                "source_reference_digests": [canonical_digest({"source": "opaque-alpha-beta"})],
            }], reviewer_accountability_id="reviewer-grounding",
        ).to_json_value()
        revised_route = create_grounded_movie_route(
            self.base_payload["decision"], self.base_payload["review_packet"], self.base_payload["option_set"],
            self.base_payload["scene_breakdown"], self.base_payload["creative_decision"],
            self.base_payload["canon_snapshot"], self.base_payload["canon_binding"], self.base_payload["shot_plan"],
            self.base_payload["storyboard"], profile_data=revised_profile,
        )
        second_payload = {**self.base_payload, "profile": revised_profile,
                          "grounded_creative_decision": revised_route.creative_decision.to_json_value(),
                          "grounded_canon_snapshot": revised_route.canon_snapshot.to_json_value(),
                          "grounded_canon_binding": revised_route.canon_binding.to_json_value(),
                          "grounded_shot_plan": revised_route.shot_plan.to_json_value(),
                          "grounded_storyboard": revised_route.storyboard.to_json_value()}
        second = self.admit_grounded(second_payload)
        self.assertEqual(second.request["contract_version"], "3")
        self.assertEqual(second.request["projection"]["visual_grounding_profile_sha256"], revised_profile["profile_sha256"])
        self.assertEqual(revised_profile["predecessor"]["review"]["review_sha256"], first_review.value["review_sha256"])
        self.assertNotEqual(first.request["request_sha256"], second.request["request_sha256"])

        second_admitted = self.admit_grounded(second_payload, approval=self.approval(second))
        second_result, second_code = self.runtime(second_admitted, mode="generate")
        self.assertEqual(second_code, 0, second_result)
        second_review = record_production_visual_grounding_review(
            generation=second_admitted, candidate=admit_generated_candidate(self.root, second_admitted),
            disposition="USE", defects=[], reviewer_accountability_id="reviewer-grounding",
        )
        self.assertEqual(second_review.value["candidate_sha256"], admit_generated_candidate(self.root, second_admitted).candidate_json()["candidate_sha256"])
        self.assertTrue(all(value is False for value in second_review.value["authority"].values()))

    def test_m10_2_through_m10_4_grounded_candidate_evidence_chain(self):
        first = self.admit_grounded()
        first_admitted = self.admit_grounded(approval=self.approval(first))
        first_result, first_code = self.runtime(first_admitted, mode="generate")
        self.assertEqual(first_code, 0, first_result)
        first_candidate = admit_generated_candidate(self.root, first_admitted)
        first_review = record_production_visual_grounding_review(
            generation=first_admitted, candidate=first_candidate, disposition="REGENERATE",
            defects=[{"defect_code": "production.defect-alpha", "group_id": "production.group-alpha",
                      "rationale": "Opaque human development review evidence."}],
            reviewer_accountability_id="reviewer-grounding",
        )
        revised_profile = create_revised_production_visual_grounding_profile(
            predecessor_profile=self.grounding_profile, review=first_review,
            profile_id="visual-grounding-production-alpha", revision=2,
            tenant_id="tenant-local", universe_id="universe-local",
            production_id=self.base_payload["story"]["project_id"], mode="required",
            groups=[{"ordinal": 1, "group_id": "production.group-alpha",
                     "positive_constraints": ["Apply revised opaque production visual token ALPHA-BETA."],
                     "negative_constraints": ["Exclude production-defined visual token ALPHA-NEGATIVE."],
                     "explicit_unknowns": ["Production-defined visual token ALPHA-UNKNOWN remains unresolved."],
                     "limitations": ["Opaque production revision; VSS assigns no domain meaning."],
                     "source_reference_digests": [canonical_digest({"source": "opaque-alpha-beta"})]}],
            reviewer_accountability_id="reviewer-grounding",
        ).to_json_value()
        route = create_grounded_movie_route(
            self.base_payload["decision"], self.base_payload["review_packet"], self.base_payload["option_set"],
            self.base_payload["scene_breakdown"], self.base_payload["creative_decision"],
            self.base_payload["canon_snapshot"], self.base_payload["canon_binding"], self.base_payload["shot_plan"],
            self.base_payload["storyboard"], profile_data=revised_profile,
        )
        second_payload = {**self.base_payload, "profile": revised_profile,
                          "grounded_creative_decision": route.creative_decision.to_json_value(),
                          "grounded_canon_snapshot": route.canon_snapshot.to_json_value(),
                          "grounded_canon_binding": route.canon_binding.to_json_value(),
                          "grounded_shot_plan": route.shot_plan.to_json_value(),
                          "grounded_storyboard": route.storyboard.to_json_value()}
        second = self.admit_grounded(second_payload)
        second_admitted = self.admit_grounded(second_payload, approval=self.approval(second))
        second_result, second_code = self.runtime(second_admitted, mode="generate")
        self.assertEqual(second_code, 0, second_result)
        second_candidate = admit_generated_candidate(self.root, second_admitted)
        second_review = record_production_visual_grounding_review(
            generation=second_admitted, candidate=second_candidate, disposition="USE", defects=[],
            reviewer_accountability_id="reviewer-grounding",
        )

        comparison = create_grounded_storyboard_comparison(
            first_admitted, first_candidate, first_review,
            second_admitted, second_candidate, second_review,
        )
        comparison_json = comparison.to_json_value()
        self.assertEqual(comparison_json["candidates"][0]["candidate_sha256"],
                         first_candidate.candidate_json()["candidate_sha256"])
        self.assertEqual(comparison_json["candidates"][1]["visual_grounding_profile"]["revision"], 2)
        self.assertEqual(comparison_json["candidate_order"], "caller_supplied_evidence_order_not_ranking")
        self.assertTrue(all(value is False for value in comparison_json["authority"].values()))
        self.assertEqual(comparison_json, create_grounded_storyboard_comparison(
            first_admitted, first_candidate, first_review,
            second_admitted, second_candidate, second_review,
        ).to_json_value())

        selection_evidence = record_development_review_selection(
            comparison, selected_candidate_id=second_candidate.candidate_json()["candidate_id"],
            reviewer_accountability_id="development.reviewer", rationale="Human development review selection.",
        )
        selection = selection_evidence.to_json_value()
        self.assertEqual(selection["comparison_sha256"], comparison_json["comparison_sha256"])
        self.assertEqual(selection["selected_candidate_sha256"], second_candidate.candidate_json()["candidate_sha256"])
        self.assertTrue(all(value is False for value in selection["authority"].values()))
        with self.assertRaisesRegex(ResourceContractError, "authoritative sealed selection"):
            record_grounded_storyboard_promotion(
                comparison, selection, second_admitted, second_candidate, second_review,
                promotion_approver_accountability_id="promotion.approver",
                rationale="Forged selection must fail closed.",
            )
        with self.assertRaisesRegex(ResourceContractError, "authoritative sealed comparison"):
            record_grounded_storyboard_promotion(
                comparison_json, selection_evidence, second_admitted, second_candidate, second_review,
                promotion_approver_accountability_id="promotion.approver",
                rationale="Forged comparison must fail closed.",
            )
        promotion_evidence = record_grounded_storyboard_promotion(
            comparison, selection_evidence, second_admitted, second_candidate, second_review,
            promotion_approver_accountability_id="promotion.approver",
            rationale="Explicit accountable human promotion approval.",
        )
        promotion = promotion_evidence.to_json_value()
        self.assertEqual(promotion["comparison_sha256"], comparison_json["comparison_sha256"])
        self.assertEqual(promotion["selection_sha256"], selection["selection_sha256"])
        self.assertEqual(promotion["selected_candidate"], comparison_json["candidates"][1])
        self.assertTrue(all(value is False for value in promotion["authority"].values()))
        with self.assertRaisesRegex(ResourceContractError, "authoritative M10.3 promotion"):
            admit_grounded_storyboard_asset(
                promotion, asset_admission_approver_accountability_id="asset.approver",
                rationale="Forged serialized evidence must fail closed.",
            )
        with self.assertRaisesRegex(ResourceContractError, "accountability identifier"):
            admit_grounded_storyboard_asset(
                promotion_evidence, asset_admission_approver_accountability_id="",
                rationale="Invalid approval metadata must not consume promotion evidence.",
            )
        with self.assertRaisesRegex(ResourceContractError, "rationale is invalid"):
            admit_grounded_storyboard_asset(
                promotion_evidence, asset_admission_approver_accountability_id="asset.approver",
                rationale="",
            )
        admission_evidence = admit_grounded_storyboard_asset(
            promotion_evidence, asset_admission_approver_accountability_id="asset.approver",
            rationale="Admit the exact promoted USE candidate as reusable-asset evidence only.",
        )
        admission = admission_evidence.to_json_value()
        self.assertEqual(admission["source"]["comparison_sha256"], comparison_json["comparison_sha256"])
        self.assertEqual(admission["source"]["selection_sha256"], selection["selection_sha256"])
        self.assertEqual(admission["source"]["promotion_sha256"], promotion["promotion_sha256"])
        self.assertEqual(admission["admitted_candidate"], promotion["selected_candidate"])
        self.assertEqual(admission["provider_binding_sha256"],
                         canonical_digest(promotion["selected_candidate"]["provider"]))
        self.assertTrue(all(value is False for value in admission["authority"].values()))
        self.assertEqual(admission["admission_sha256"], canonical_digest({
            **admission, "admission_sha256": "0" * 64,
        }))
        # M10.5: persist and resolve only the exact M10.4 metadata envelope.
        catalog = register_grounded_storyboard_asset(self.root, admission_evidence)
        self.assertEqual(catalog, lookup_grounded_storyboard_asset(self.root, catalog.asset_id))
        shot = second_payload["shot_plan"]["payload"]["ordered_shots"][0]
        binding = bind_grounded_storyboard_asset_to_shot(
            catalog, second_payload["storyboard"], second_payload["decision"],
            second_payload["review_packet"], second_payload["option_set"],
            second_payload["scene_breakdown"], second_payload["shot_plan"],
            shot_id=shot["shot_id"], approver_accountability_id="shot.approver",
            rationale="Bind the cataloged visual basis to this exact production shot.",
            grounded_shot_plan_data=second_payload["grounded_shot_plan"],
            grounded_storyboard_data=second_payload["grounded_storyboard"],
        )
        binding_json = binding.to_json_value()
        self.assertEqual(binding_json["asset_id"], catalog.asset_id)
        self.assertEqual(binding_json["shot_card_digest"], shot["shot_card_digest"])
        self.assertTrue(all(value is False for value in binding_json["authority"].values()))
        with self.assertRaisesRegex(ResourceContractError, "wrong shot"):
            bind_grounded_storyboard_asset_to_shot(
                catalog, second_payload["storyboard"], second_payload["decision"],
                second_payload["review_packet"], second_payload["option_set"],
                second_payload["scene_breakdown"], second_payload["shot_plan"],
                shot_id=second_payload["shot_plan"]["payload"]["ordered_shots"][1]["shot_id"],
                approver_accountability_id="shot.approver", rationale="Wrong-shot evidence must fail closed.",
                grounded_shot_plan_data=second_payload["grounded_shot_plan"],
                grounded_storyboard_data=second_payload["grounded_storyboard"],
            )
        with self.assertRaisesRegex(ResourceContractError, "already been admitted"):
            admit_grounded_storyboard_asset(
                promotion_evidence, asset_admission_approver_accountability_id="asset.approver",
                rationale="Replay must fail closed.",
            )
        with self.assertRaisesRegex(ResourceContractError, "already been recorded"):
            record_grounded_storyboard_promotion(
                comparison, selection_evidence, second_admitted, second_candidate, second_review,
                promotion_approver_accountability_id="promotion.approver", rationale="Replay.",
            )
        with self.assertRaisesRegex(ResourceContractError, "already been recorded"):
            record_development_review_selection(
                comparison, selected_candidate_id=first_candidate.candidate_json()["candidate_id"],
                reviewer_accountability_id="development.reviewer", rationale="Replay.",
            )

        incompatible_comparison = create_grounded_storyboard_comparison(
            first_admitted, first_candidate, first_review,
            second_admitted, second_candidate, second_review,
        )
        incompatible_selection = record_development_review_selection(
            incompatible_comparison, selected_candidate_id=second_candidate.candidate_json()["candidate_id"],
            reviewer_accountability_id="development.reviewer", rationale="Human selection.",
        )
        with self.assertRaisesRegex(ResourceContractError, "selected candidate evidence binding mismatch"):
            record_grounded_storyboard_promotion(
                incompatible_comparison, incompatible_selection, first_admitted, first_candidate, first_review,
                promotion_approver_accountability_id="promotion.approver",
                rationale="Substituted candidate must fail closed.",
            )
        tampered = incompatible_comparison.to_json_value()
        tampered["candidates"][1]["visual_grounding_profile"]["profile_sha256"] = "0" * 64
        object.__setattr__(incompatible_comparison, "_value", freeze_json(tampered))
        with self.assertRaisesRegex(ResourceContractError, "comparison package seal or authority mismatch"):
            record_grounded_storyboard_promotion(
                incompatible_comparison, incompatible_selection,
                second_admitted, second_candidate, second_review,
                promotion_approver_accountability_id="promotion.approver",
                rationale="Tampered comparison must fail closed.",
            )
        deterministic_comparison = create_grounded_storyboard_comparison(
            first_admitted, first_candidate, first_review,
            second_admitted, second_candidate, second_review,
        )
        deterministic_selection = record_development_review_selection(
            deterministic_comparison, selected_candidate_id=second_candidate.candidate_json()["candidate_id"],
            reviewer_accountability_id="development.reviewer", rationale="Human development review selection.",
        )
        deterministic_promotion = record_grounded_storyboard_promotion(
            deterministic_comparison, deterministic_selection,
            second_admitted, second_candidate, second_review,
            promotion_approver_accountability_id="promotion.approver",
            rationale="Explicit accountable human promotion approval.",
        )
        self.assertEqual(promotion, deterministic_promotion.to_json_value())
        self.assertEqual(admission, admit_grounded_storyboard_asset(
            deterministic_promotion, asset_admission_approver_accountability_id="asset.approver",
            rationale="Admit the exact promoted USE candidate as reusable-asset evidence only.",
        ).to_json_value())

        tampered_comparison = create_grounded_storyboard_comparison(
            first_admitted, first_candidate, first_review,
            second_admitted, second_candidate, second_review,
        )
        tampered_selection = record_development_review_selection(
            tampered_comparison, selected_candidate_id=second_candidate.candidate_json()["candidate_id"],
            reviewer_accountability_id="development.reviewer", rationale="Human selection.",
        )
        tampered_promotion = record_grounded_storyboard_promotion(
            tampered_comparison, tampered_selection, second_admitted, second_candidate, second_review,
            promotion_approver_accountability_id="promotion.approver", rationale="Human promotion.",
        )
        tampered_value = tampered_promotion.to_json_value()
        tampered_value["selected_candidate"]["sealed_review"]["candidate_sha256"] = "0" * 64
        tampered_value["promotion_sha256"] = canonical_digest({
            **tampered_value, "promotion_sha256": "0" * 64,
        })
        object.__setattr__(tampered_promotion, "_value", freeze_json(tampered_value))
        with self.assertRaisesRegex(ResourceContractError, "seal, lineage, or authority mismatch"):
            admit_grounded_storyboard_asset(
                tampered_promotion, asset_admission_approver_accountability_id="asset.approver",
                rationale="Validly resealed candidate substitution must fail closed.",
            )

        resealed_comparison = create_grounded_storyboard_comparison(
            first_admitted, first_candidate, first_review,
            second_admitted, second_candidate, second_review,
        )
        resealed_selection = record_development_review_selection(
            resealed_comparison, selected_candidate_id=second_candidate.candidate_json()["candidate_id"],
            reviewer_accountability_id="development.reviewer", rationale="Human selection.",
        )
        resealed_promotion = record_grounded_storyboard_promotion(
            resealed_comparison, resealed_selection, second_admitted, second_candidate, second_review,
            promotion_approver_accountability_id="promotion.approver", rationale="Human promotion.",
        )
        resealed_value = resealed_promotion.to_json_value()
        resealed_value["authority"]["publication"] = True
        resealed_value["promotion_sha256"] = canonical_digest({
            **resealed_value, "promotion_sha256": "0" * 64,
        })
        object.__setattr__(resealed_promotion, "_value", freeze_json(resealed_value))
        with self.assertRaisesRegex(ResourceContractError, "seal, lineage, or authority mismatch"):
            admit_grounded_storyboard_asset(
                resealed_promotion, asset_admission_approver_accountability_id="asset.approver",
                rationale="Resealed authority escalation must fail closed.",
            )

        rejected_comparison = create_grounded_storyboard_comparison(
            first_admitted, first_candidate, first_review,
            second_admitted, second_candidate, second_review,
        )
        rejected_selection = record_development_review_selection(
            rejected_comparison, selected_candidate_id=first_candidate.candidate_json()["candidate_id"],
            reviewer_accountability_id="development.reviewer", rationale="Human selection.",
        )
        rejected_promotion = record_grounded_storyboard_promotion(
            rejected_comparison, rejected_selection, first_admitted, first_candidate, first_review,
            promotion_approver_accountability_id="promotion.approver", rationale="Human promotion.",
        )
        with self.assertRaisesRegex(ResourceContractError, "seal, lineage, or authority mismatch"):
            admit_grounded_storyboard_asset(
                rejected_promotion, asset_admission_approver_accountability_id="asset.approver",
                rationale="A REGENERATE review cannot become reusable-asset evidence.",
            )

    def test_m10_2_rejects_duplicate_and_nonmember_selection_before_authority(self):
        admitted = self.admit_grounded()
        approved = self.admit_grounded(approval=self.approval(admitted))
        result, code = self.runtime(approved, mode="generate")
        self.assertEqual(code, 0, result)
        candidate = admit_generated_candidate(self.root, approved)
        review = record_production_visual_grounding_review(
            generation=approved, candidate=candidate, disposition="USE", defects=[],
            reviewer_accountability_id="reviewer-grounding",
        )
        with self.assertRaisesRegex(ResourceContractError, "must be distinct"):
            create_grounded_storyboard_comparison(
                approved, candidate, review, approved, candidate, review,
            )
        self.assertEqual(len(self.calls), 1)

    def test_revised_profile_rejects_resealed_or_mismatched_predecessor_evidence(self):
        profile = copy.deepcopy(self.grounding_profile)
        review = {
            "schema_version": "1", "contract_identity": "production_visual_grounding_review", "contract_version": "1",
            "review_id": "visual-grounding-review-" + "0" * 32,
            "candidate_sha256": "1" * 64, "frame_grounding_sha256": "2" * 64,
            "visual_grounding_profile_sha256": profile["profile_sha256"], "disposition": "REGENERATE",
            "defects": [{"defect_code": "production.defect-alpha", "group_id": "production.group-alpha", "rationale": "Opaque evidence."}],
            "reviewer_accountability_id": "reviewer-grounding",
            "authority": {"profile_mutation": False, "prompt_edit": False, "provider_execution": False,
                          "runtime_execution": False, "approval": False, "reservation": False, "regeneration": False},
            "limitations": ["accountability_evidence_only", "production_defined_defect_codes", "not_truth_by_itself",
                            "not_profile_mutation", "not_prompt_authority", "not_provider_or_runtime_authority"],
            "review_sha256": "0" * 64,
        }
        review["review_id"] = "visual-grounding-review-" + canonical_digest(
            {key: value for key, value in review.items() if key not in {"review_id", "review_sha256"}})[:32]
        review["review_sha256"] = canonical_digest({**review, "review_sha256": "0" * 64})
        revised = create_revised_production_visual_grounding_profile(
            predecessor_profile=profile, review=review, profile_id=profile["profile_id"], revision=2,
            tenant_id="tenant-local", universe_id="universe-local", production_id=profile["scope"]["production_id"],
            mode="required", groups=profile["groups"], reviewer_accountability_id="reviewer-grounding",
        ).to_json_value()
        revised["predecessor"]["review"]["candidate_sha256"] = "3" * 64
        revised["profile_sha256"] = canonical_digest({**revised, "profile_sha256": "0" * 64})
        with self.assertRaisesRegex(ResourceContractError, "visual grounding review (identity|seal) mismatch"):
            from vss_resource_contracts import validate_production_visual_grounding_profile
            validate_production_visual_grounding_profile(revised)

    def test_grounding_review_rejects_resealed_caller_evidence(self):
        base = self.admit_grounded()
        admitted = self.admit_grounded(approval=self.approval(base))
        result, code = self.runtime(admitted, mode="generate")
        self.assertEqual(code, 0, result)
        raw_candidate = json.loads((self.root / result["output"]["candidate"]).read_text())
        with self.assertRaisesRegex(ResourceContractError, "authoritative admitted evidence"):
            record_production_visual_grounding_review(
                generation=admitted.request_json(), candidate=raw_candidate, disposition="REJECT",
                defects=[], reviewer_accountability_id="reviewer-grounding",
            )
        raw_candidate["lineage"]["storyboard_frame"] = "0" * 64
        raw_candidate["candidate_id"] = "generated-review-" + canonical_digest({
            key: value for key, value in raw_candidate.items()
            if key not in {"candidate_id", "candidate_sha256"}
        })[:32]
        raw_candidate["candidate_sha256"] = "0" * 64
        raw_candidate["candidate_sha256"] = canonical_digest(raw_candidate)
        (self.root / result["output"]["candidate"]).write_text(json.dumps(raw_candidate))
        with self.assertRaisesRegex(ResourceContractError, "authoritative binding mismatch"):
            admit_generated_candidate(self.root, admitted)

    def test_grounding_review_rejects_defect_group_absent_from_bound_profile(self):
        base = self.admit_grounded()
        admitted = self.admit_grounded(approval=self.approval(base))
        result, code = self.runtime(admitted, mode="generate")
        self.assertEqual(code, 0, result)
        candidate = admit_generated_candidate(self.root, admitted)
        with self.assertRaisesRegex(ResourceContractError, "defect group is absent"):
            record_production_visual_grounding_review(
                generation=admitted, candidate=candidate, disposition="REJECT",
                defects=[{
                    "defect_code": "production.defect-alpha", "group_id": "production.group-missing",
                    "rationale": "Production-owned review evidence with opaque semantics.",
                }], reviewer_accountability_id="reviewer-grounding",
            )

    def approval(self, admitted):
        return issue_approval(
            admitted.request_json(), recorded_by="reviewer-m10", secret=APPROVER_SECRET,
            issued_at="2030-01-02T03:00:00Z", expires_at="2030-01-02T03:15:00Z",
        )

    def transport(self, *args):
        self.calls.append(args)
        return response(png())

    def provider_secret_reader(self, name):
        self.provider_secret_reads.append(name)
        return PROVIDER_SECRET

    def approver_secret_reader(self, name):
        self.approver_secret_reads.append(name)
        return APPROVER_SECRET

    def controller(self, *, policy=None, transport=None):
        return RuntimeController(
            root=self.root, policy=policy,
            controlled_provider_transport=transport or self.transport,
            controlled_provider_secret_reader=self.provider_secret_reader,
            controlled_approver_secret_reader=self.approver_secret_reader,
            controlled_now=lambda: "2030-01-02T03:05:00Z",
            external_execution_preflight=ExternalExecutionPreflight(
                environment_contains=lambda name: name == SECRET_NAME,
                resolver=lambda hostname, port: [(hostname, port)],
            ),
        )

    def runtime(self, admitted, *, mode, controller=None):
        return (controller or self.controller()).run(
            command="movie.controlled-review-frame-generate", environment="development", configuration={},
            input_data={"admission_id": admitted.request["request_sha256"], "mode": mode},
            correlation_id="m10-test", started_at="2030-01-02T03:05:00.000Z", started_clock=0.0,
            dry_run=mode == "preflight", timeout_seconds=150, admitted_request=admitted,
        )

    def test_genuine_demo_path_is_deterministic_and_minimizes_provider_projection(self):
        first = self.admit()
        second = self.admit()
        self.assertEqual(first.request_json(), second.request_json())
        prompt = first.prompt.casefold()
        for expected in ("clean cinematic", "continuity constraints", "negative constraints"):
            self.assertIn(expected, prompt)
        for prohibited in ("tenant-local", "reviewer-m10", "canon_sha256", "request_sha256"):
            self.assertNotIn(prohibited, prompt)
        self.assertEqual(first.request["bounds"]["maximum_provider_attempts"], 1)
        self.assertEqual(first.request["bounds"]["maximum_cost_usd"], "0.100000")
        self.assertEqual(first.request["contract_version"], "2")
        self.assertEqual(first.request["provider"]["version"], "1.1.0")
        self.assertEqual(first.request["provider"]["output_policy_identity"],
                         "vss.opaque-provider-content-credentials.png/1")
        for section, keys in (("capability", ("manifest_sha256", "handler_sha256")),
                              ("provider", ("manifest_sha256", "implementation_sha256"))):
            for key in keys:
                self.assertRegex(first.request[section][key], r"^[0-9a-f]{64}$")
        with self.assertRaises(TypeError):
            first.request["provider"]["model_snapshot"] = "moving-alias"

    def test_preflight_is_zero_call_zero_secret_zero_reservation(self):
        admitted = self.admit()
        result, code = self.runtime(admitted, mode="preflight")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["output"]["provider_call_count"], 0)
        self.assertFalse(result["output"]["attempt_reserved"])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.provider_secret_reads, [])
        self.assertEqual(self.approver_secret_reads, [])
        self.assertFalse((self.root / ".local/movie/m10-0-controlled-review-frame").exists())

    def test_one_approved_fake_call_admits_quarantined_candidate_and_empty_review(self):
        base = self.admit()
        admitted = self.admit(approval=self.approval(base))
        result, code = self.runtime(admitted, mode="generate")
        self.assertEqual(code, 0, result)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.approver_secret_reads, [APPROVER_SECRET_NAME])
        self.assertEqual(self.provider_secret_reads, [SECRET_NAME])
        output = result["output"]
        candidate = json.loads((self.root / output["candidate"]).read_text())
        review = json.loads((self.root / output["review"]).read_text())
        self.assertEqual(candidate["status"], "development_review_quarantined")
        self.assertEqual(candidate["scope"]["project_id"], base.request["scope"]["project_id"])
        self.assertTrue(all(value is False for value in candidate["authority"].values()))
        self.assertEqual(candidate["preservation"]["policy"], "disposable_local")
        self.assertEqual(candidate["media"]["content_credentials"], {
            "present": False, "container": "none", "chunk_count": 0, "chunk_bytes": 0,
            "payload_sha256": None, "interpretation": "not_applicable",
            "verification_status": "not_applicable", "trust_status": "not_applicable",
            "grants_vss_authority": False,
        })
        self.assertIsNone(review["disposition"])
        self.assertEqual((self.root / output["image"]).read_bytes(), png())
        outcome = json.loads((self.root / output["attempt_outcome"]).read_text())
        self.assertEqual((outcome["terminal_status"], outcome["classification"]),
                         ("admitted", "admitted"))
        self.assertEqual(outcome["candidate_sha256"], candidate["candidate_sha256"])

    def test_valid_story_substitution_is_rejected_before_any_secret_or_call(self):
        payload = copy.deepcopy(self.base_payload)
        payload["story"]["payload"]["fragment_text"] += " A validly shaped substitution."
        with self.assertRaises(Exception):
            self.admit(payload)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.provider_secret_reads, [])
        self.assertEqual(self.approver_secret_reads, [])

    def test_tampered_approval_and_kill_switch_fail_before_attempt(self):
        base = self.admit()
        approval = self.approval(base)
        approval["recorded_by"] = "attacker"
        admitted = self.admit(approval=approval)
        result, code = self.runtime(admitted, mode="generate")
        self.assertEqual(code, ExitCode.PERMISSION_DENIED, result)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.provider_secret_reads, [])
        attempt_root = self.root / ".local/movie/m10-0-controlled-review-frame"
        self.assertFalse(attempt_root.exists())

        policy = RuntimePolicy(
            allowed_builtin_permissions=("provider_access",),
            allowed_provider_identities=("movie.storyboard-image.openai",),
            allowed_capability_permissions={"movie.controlled-review-frame":
                ("filesystem_write", "network", "provider_access", "secrets")},
            controlled_media_killed=True,
        )
        result, code = self.runtime(self.admit(approval=self.approval(base)), mode="generate",
                                    controller=self.controller(policy=policy))
        self.assertEqual(code, ExitCode.PERMISSION_DENIED, result)
        self.assertEqual(self.calls, [])

    def test_expired_or_overlong_approval_is_denied_before_attempt(self):
        base = self.admit()
        with self.assertRaises(ResourceContractError):
            issue_approval(
                base.request_json(), recorded_by="reviewer-m10", secret=APPROVER_SECRET,
                issued_at="2030-01-02T03:00:00Z", expires_at="2030-01-02T03:15:01Z",
            )
        expired = issue_approval(
            base.request_json(), recorded_by="reviewer-m10", secret=APPROVER_SECRET,
            issued_at="2030-01-02T02:45:00Z", expires_at="2030-01-02T03:00:00Z",
        )
        result, code = self.runtime(self.admit(approval=expired), mode="generate")
        self.assertEqual(code, ExitCode.PERMISSION_DENIED, result)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.provider_secret_reads, [])
        self.assertEqual(self.approver_secret_reads, [APPROVER_SECRET_NAME])
        self.assertFalse((self.root / ".local/movie/m10-0-controlled-review-frame").exists())

    def test_closed_provider_response_and_cost_ceiling_are_terminal(self):
        base = self.admit()
        approval = self.approval(base)

        def unexpected_field(value):
            value["unexpected"] = "not admitted"

        def extra_image(value):
            value["data"].append(copy.deepcopy(value["data"][0]))

        def excessive_cost(value):
            value["usage"].update({"output_tokens": 4_000_000, "total_tokens": 4_000_325})

        def unexpected_usage_field(value):
            value["usage"]["unexpected"] = 0

        def output_details_not_object(value):
            value["usage"]["output_tokens_details"] = []

        def output_details_missing_field(value):
            value["usage"]["output_tokens_details"] = {"image_tokens": 1200}

        def output_details_extra_field(value):
            value["usage"]["output_tokens_details"]["unexpected"] = 0

        def output_details_boolean(value):
            value["usage"]["output_tokens_details"]["text_tokens"] = True

        def output_details_negative(value):
            value["usage"]["output_tokens_details"]["image_tokens"] = -1

        def output_details_overflow(value):
            value["usage"]["output_tokens_details"]["image_tokens"] = 10_000_001

        for label, mutate in (("unexpected-field", unexpected_field),
                              ("extra-image", extra_image), ("excessive-cost", excessive_cost),
                              ("unexpected-usage-field", unexpected_usage_field),
                              ("output-details-not-object", output_details_not_object),
                              ("output-details-missing-field", output_details_missing_field),
                              ("output-details-extra-field", output_details_extra_field),
                              ("output-details-boolean", output_details_boolean),
                              ("output-details-negative", output_details_negative),
                              ("output-details-overflow", output_details_overflow)):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                isolated_root = Path(directory)
                for name in ("capabilities", "providers", "schemas"):
                    shutil.copytree(ROOT / name, isolated_root / name)
                calls = []

                def malformed_transport(*args):
                    calls.append(args)
                    value = json.loads(response(png()).content)
                    mutate(value)
                    return SmokeHTTPResponse(
                        json.dumps(value).encode("utf-8"), 200, "req_m10_rejected")

                controller = RuntimeController(
                    root=isolated_root,
                    controlled_provider_transport=malformed_transport,
                    controlled_provider_secret_reader=self.provider_secret_reader,
                    controlled_approver_secret_reader=self.approver_secret_reader,
                    controlled_now=lambda: "2030-01-02T03:05:00Z",
                    external_execution_preflight=ExternalExecutionPreflight(
                        environment_contains=lambda name: name == SECRET_NAME,
                        resolver=lambda hostname, port: [(hostname, port)],
                    ),
                )
                admitted = self.admit(approval=approval)
                result, code = self.runtime(admitted, mode="generate", controller=controller)
                self.assertNotEqual(code, 0, result)
                self.assertEqual(len(calls), 1)
                artifact_root = (isolated_root / ".local/movie/m10-0-controlled-review-frame"
                                 / base.request["request_sha256"])
                self.assertTrue((artifact_root / "attempt.json").exists())
                self.assertTrue((artifact_root / "attempt-outcome.json").exists())
                self.assertFalse((artifact_root / "generated-review-candidate.json").exists())

    def test_opaque_content_credentials_are_admitted_unchanged_and_replay_is_terminal(self):
        base = self.admit()
        approval = self.approval(base)
        admitted = self.admit(approval=approval)
        content = png(cabx=b"foreign-opaque-manifest")
        result, code = self.runtime(admitted, mode="generate",
                                    controller=self.controller(transport=lambda *args: response(content)))
        self.assertEqual(code, 0, result)
        root = self.root / ".local/movie/m10-0-controlled-review-frame" / base.request["request_sha256"]
        self.assertEqual((root / "image.png").read_bytes(), content)
        candidate = json.loads((root / "generated-review-candidate.json").read_text())
        credentials = candidate["media"]["content_credentials"]
        self.assertEqual(credentials, {
            "present": True, "container": "png_cabx", "chunk_count": 1,
            "chunk_bytes": len(b"foreign-opaque-manifest"),
            "payload_sha256": hashlib.sha256(b"foreign-opaque-manifest").hexdigest(),
            "interpretation": "opaque_unparsed", "verification_status": "not_performed",
            "trust_status": "untrusted_external", "grants_vss_authority": False,
        })
        self.assertTrue(all(value is False for value in candidate["authority"].values()))
        outcome = json.loads((root / "attempt-outcome.json").read_text())
        serialized = json.dumps({"candidate": candidate, "outcome": outcome})
        self.assertNotIn("foreign-opaque-manifest", serialized)
        audit = "\n".join(path.read_text() for path in (self.root / ".local/runtime/audit").glob("*.jsonl"))
        self.assertNotIn("foreign-opaque-manifest", audit)
        calls = len(self.calls)
        result, code = self.runtime(admitted, mode="generate")
        self.assertNotEqual(code, 0, result)
        self.assertEqual(len(self.calls), calls)

    def test_malformed_content_credentials_and_pngs_are_terminal_with_sanitized_outcomes(self):
        idat_then_cabx = png()[:-12] + _chunk(b"caBX", b"late") + _chunk(b"IEND", b"")
        disallowed = png()[:-12] + _chunk(b"tEXt", b"hidden") + _chunk(b"IEND", b"")
        bad_crc = bytearray(png(cabx=b"foreign")); bad_crc[40] ^= 1
        cases = {
            "empty-cabx": png(cabx=b""),
            "duplicate-cabx": png(cabx=(b"one", b"two")),
            "oversized-cabx": png(cabx=b"x" * (4 * 1024 * 1024 + 1)),
            "misplaced-cabx": idat_then_cabx,
            "bad-crc": bytes(bad_crc),
            "truncated": png()[:-1],
            "disallowed-metadata": disallowed,
            "invalid-profile": png(width=1279),
            "unsafe-decompression": png(compressed=zlib.compress(b"short")),
        }
        base = self.admit()
        approval = self.approval(base)
        for label, content in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                isolated_root = Path(directory)
                for name in ("capabilities", "providers", "schemas"):
                    shutil.copytree(ROOT / name, isolated_root / name)
                calls = []
                controller = RuntimeController(
                    root=isolated_root,
                    controlled_provider_transport=lambda *args, value=content: (
                        calls.append(args) or response(value)),
                    controlled_provider_secret_reader=self.provider_secret_reader,
                    controlled_approver_secret_reader=self.approver_secret_reader,
                    controlled_now=lambda: "2030-01-02T03:05:00Z",
                    external_execution_preflight=ExternalExecutionPreflight(
                        environment_contains=lambda name: name == SECRET_NAME,
                        resolver=lambda hostname, port: [(hostname, port)],
                    ),
                )
                result, code = self.runtime(self.admit(approval=approval), mode="generate", controller=controller)
                self.assertNotEqual(code, 0, result)
                self.assertEqual(len(calls), 1)
                root = isolated_root / ".local/movie/m10-0-controlled-review-frame" / base.request["request_sha256"]
                outcome = json.loads((root / "attempt-outcome.json").read_text())
                self.assertEqual(outcome["terminal_status"], "output_rejected")
                self.assertEqual(outcome["classification"], "output_invalid")
                self.assertEqual(outcome["usage_and_cost"]["availability"], "available")
                self.assertIsNone(outcome["candidate_sha256"])
                self.assertFalse((root / "generated-review-candidate.json").exists())

    def test_resealed_content_credentials_substitution_fails_media_reconstruction(self):
        base = self.admit()
        content = png(cabx=b"opaque")
        result, code = self.runtime(
            self.admit(approval=self.approval(base)), mode="generate",
            controller=self.controller(transport=lambda *args: response(content)),
        )
        self.assertEqual(code, 0, result)
        candidate = json.loads((self.root / result["output"]["candidate"]).read_text())
        candidate["media"]["content_credentials"]["payload_sha256"] = "f" * 64
        candidate["candidate_id"] = "generated-review-" + canonical_digest({
            key: item for key, item in candidate.items() if key not in {"candidate_id", "candidate_sha256"}
        })[:32]
        candidate["candidate_sha256"] = "0" * 64
        candidate["candidate_sha256"] = canonical_digest(candidate)
        with self.assertRaises(ResourceContractError):
            validate_candidate_media(candidate, content)

    def test_safe_handle_reconstructs_and_rejects_provider_summary_substitution(self):
        content = png(cabx=b"opaque")

        class LyingProvider:
            def generate(self, request, *, credential, transport):
                return ControlledFrameResult(
                    media=GeneratedMedia("image/png", content, 1280, 720, hashlib.sha256(content).hexdigest()),
                    latency_ms=1, usage=MappingProxyType({"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}),
                    estimated_cost_usd="0.000035", response_sha256="a" * 64,
                    provider_created=42, request_id="req_safe",
                    content_credentials=MappingProxyType({
                        "present": False, "container": "none", "chunk_count": 0, "chunk_bytes": 0,
                        "payload_sha256": None, "interpretation": "not_applicable",
                        "verification_status": "not_applicable", "trust_status": "not_applicable",
                        "grants_vss_authority": False,
                    }),
                )

        handle = ProviderAccess(
            controlled=LyingProvider(), controlled_secret_reader=lambda name: PROVIDER_SECRET,
            controlled_transport=object(),
        ).get_controlled_frame_generator()
        with self.assertRaises(ControlledFrameProviderFailure):
            handle.generate(ControlledFrameRequest(prompt="bounded", request_sha256="a" * 64,
                                                    provider_request_sha256="b" * 64))

    def test_capability_and_provider_code_drift_fail_before_secret_or_call(self):
        for label, relative in (
            ("capability", "capabilities/movie-controlled-review-frame/handler.py"),
            ("provider", "providers/builtin/movie-storyboard-image-openai/implementation.py"),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                isolated_root = Path(directory)
                for name in ("capabilities", "providers", "schemas"):
                    shutil.copytree(ROOT / name, isolated_root / name)
                path = isolated_root / relative
                path.write_text(path.read_text() + "\n# validly shaped drift\n")
                base = self.admit()
                result, code = self.runtime(
                    self.admit(approval=self.approval(base)), mode="generate",
                    controller=RuntimeController(
                        root=isolated_root,
                        controlled_provider_transport=self.transport,
                        controlled_provider_secret_reader=self.provider_secret_reader,
                        controlled_approver_secret_reader=self.approver_secret_reader,
                        controlled_now=lambda: "2030-01-02T03:05:00Z",
                        external_execution_preflight=ExternalExecutionPreflight(
                            environment_contains=lambda name: name == SECRET_NAME,
                            resolver=lambda hostname, port: [(hostname, port)],
                        ),
                    ),
                )
                self.assertNotEqual(code, 0, result)
                self.assertEqual(self.calls, [])
                self.assertEqual(self.provider_secret_reads, [])
                self.assertEqual(self.approver_secret_reads, [])

    def test_audit_failure_admits_no_candidate_and_records_terminal_outcome(self):
        base = self.admit()
        controller = self.controller(transport=lambda *args: response(png(cabx=b"opaque")))
        controller.audit = FailingAudit(self.root / ".local/runtime/audit", trusted_root=self.root)
        result, code = self.runtime(self.admit(approval=self.approval(base)), mode="generate",
                                    controller=controller)
        self.assertEqual(code, int(ExitCode.INTERNAL_ERROR), result)
        root = self.root / ".local/movie/m10-0-controlled-review-frame" / base.request["request_sha256"]
        self.assertFalse((root / "image.png").exists())
        self.assertFalse((root / "generated-review-candidate.json").exists())
        outcome = json.loads((root / "attempt-outcome.json").read_text())
        self.assertEqual((outcome["terminal_status"], outcome["classification"]),
                         ("output_rejected", "runtime_or_audit_failed"))
        self.assertEqual(outcome["usage_and_cost"]["availability"], "available")

    def test_command_runner_preflight_approval_and_generate_use_real_stage_service(self):
        payload = {**self.base_payload, "mode": "preflight"}
        result, code = CommandRunner(runtime_controller=self.controller()).run(
            "movie.controlled-review-frame", "development", payload, "m10-runner")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["output"]["request"]["request_sha256"],
                         result["output"]["request_sha256"])
        self.assertEqual(self.calls, [])

        with patch.dict("os.environ", {APPROVER_SECRET_NAME: APPROVER_SECRET}):
            approval_result, approval_code = CommandRunner().run(
                "movie.controlled-review-frame", "development",
                {**self.base_payload, "mode": "approve", "recorded_by": "reviewer-m10"},
                "m10-runner-approve",
            )
        self.assertEqual(approval_code, 0, approval_result)
        self.assertEqual(approval_result["output"]["provider_call_count"], 0)
        approval = approval_result["output"]["approval"]

        controller = self.controller()
        controller.controlled_now = lambda: approval["issued_at"]
        generated, generated_code = CommandRunner(runtime_controller=controller).run(
            "movie.controlled-review-frame", "development",
            {**self.base_payload, "mode": "generate", "approval": approval},
            "m10-runner-generate",
        )
        self.assertEqual(generated_code, 0, generated)
        self.assertEqual(generated["output"]["provider_call_count"], 1)

    def test_command_runner_grounded_preflight_is_zero_call(self):
        payload = {
            **self.base_payload,
            "visual_grounding_profile": self.grounded_payload["profile"],
            "grounded_creative_decision": self.grounded_payload["grounded_creative_decision"],
            "grounded_canon_snapshot": self.grounded_payload["grounded_canon_snapshot"],
            "grounded_canon_binding": self.grounded_payload["grounded_canon_binding"],
            "grounded_shot_plan": self.grounded_payload["grounded_shot_plan"],
            "grounded_storyboard": self.grounded_payload["grounded_storyboard"],
            "mode": "preflight",
        }
        result, code = CommandRunner(runtime_controller=self.controller()).run(
            "movie.controlled-review-frame", "development", payload, "m10-grounded-runner")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["output"]["request"]["contract_version"], "3")
        self.assertEqual(result["output"]["provider_call_count"], 0)
        self.assertEqual(self.calls, [])
        incomplete = copy.deepcopy(payload)
        incomplete.pop("grounded_storyboard")
        result, code = CommandRunner(runtime_controller=self.controller()).run(
            "movie.controlled-review-frame", "development", incomplete,
            "m10-grounded-runner-incomplete")
        self.assertEqual(code, ExitCode.INVALID_INPUT, result)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
