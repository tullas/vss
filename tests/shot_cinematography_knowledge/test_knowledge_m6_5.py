import unittest

from tests.shot_cinematography_lessons.test_lessons_m6_4 import execute, lesson_task, source_for
from tests.shot_observation_context.test_context import observation, seal
from vss_movie_cinematic_knowledge import (
    admit_lesson_candidate, create_admission_decision, create_lifecycle_event,
    current_use_eligible,
)
from vss_movie_contracts import validate_shot_cinematography_lesson_candidate_set
from vss_reasoning_contracts import canonical_digest


class ShotCinematographyKnowledgeTests(unittest.TestCase):
    def test_variation_candidate_is_admitted_without_new_meaning(self):
        raw = [observation(1), observation(2), observation(3)]
        for item, angle in zip(raw, ("level", "low_angle", "dutch_angle")):
            item["attributes"]["camera_angle"] = {"status": "observed", "value": angle}
            seal(item, "observation_content_digest")
        _, candidates, _, admitted = self._admit(source_for(raw))
        candidate = candidates.value["payload"]["candidates"][0]
        self.assertEqual(candidate["candidate_type"], "variation_lesson_candidate")
        self.assertEqual(admitted.knowledge.value["proposition"]["values"], ("level", "low_angle", "dutch_angle"))

    def _admit(self, source=None, *, decision_id="a" * 32):
        source = source or source_for([observation(1), observation(2)])
        output = execute(source)
        task = lesson_task(source)
        candidates = validate_shot_cinematography_lesson_candidate_set(
            output["shot_cinematography_lesson_candidate_set"], task=task,
            pattern_set=source[2], invocation_binding_digest=output["invocation_binding_digest"],
        )
        candidate = candidates.value["payload"]["candidates"][0]
        decision = create_admission_decision(
            candidate=candidate, actor_identity="human-reviewer-001",
            decision_id="shot-knowledge-admission-" + decision_id,
            decision_at="2026-08-10T00:00:00Z", project_id=source[0].value["project_id"],
            classification=source[0].value["classification"],
        )
        admitted = admit_lesson_candidate(
            candidates, lesson_task=task, pattern_set=source[2], pattern_task=source[1],
            context=source[0], pattern_invocation_binding_digest=source[3],
            candidate_invocation_binding_digest=output["invocation_binding_digest"],
            admission_decision=decision, effective_until="2027-01-01T00:00:00Z",
            retention_until="2028-01-01T00:00:00Z",
        )
        return source, candidates, decision, admitted

    def test_explicit_human_admission_is_exact_project_scoped_and_current(self):
        source, _, decision, admitted = self._admit()
        self.assertEqual(decision.value["actor_kind"], "human")
        self.assertEqual(admitted.knowledge.value["project_id"], source[0].value["project_id"])
        self.assertEqual(admitted.knowledge.value["domain"], "shot_cinematography")
        self.assertEqual(current_use_eligible(admitted.knowledge, validation_time="2026-09-01T00:00:00Z").digest, admitted.knowledge.digest)

    def test_identity_is_deterministic_and_source_lineage_is_preserved(self):
        first = self._admit(decision_id="b" * 32)[3]
        second = self._admit(decision_id="c" * 32)[3]
        self.assertEqual(first.knowledge.value["knowledge_content_digest"], second.knowledge.value["knowledge_content_digest"])
        self.assertEqual(first.knowledge.value["source_candidate"], second.knowledge.value["source_candidate"])
        self.assertNotEqual(first.knowledge.value["admission_decision_id"], second.knowledge.value["admission_decision_id"])

    def test_duplicate_and_automatic_admission_are_rejected(self):
        source, candidates, decision, admitted = self._admit()
        with self.assertRaises(ValueError):
            admit_lesson_candidate(candidates, lesson_task=lesson_task(source), pattern_set=source[2], pattern_task=source[1], context=source[0], pattern_invocation_binding_digest=source[3], candidate_invocation_binding_digest=candidates.value["invocation_binding_digest"], admission_decision=decision, effective_until="2027-01-01T00:00:00Z", retention_until="2028-01-01T00:00:00Z", prior_admissions=[admitted.knowledge])
        forged = decision.to_json_value(); forged["actor_kind"] = "provider"
        forged["decision_content_digest"] = canonical_digest({k: v for k, v in forged.items() if k != "decision_content_digest"})
        with self.assertRaises(Exception):
            create_admission_decision(candidate=candidates.value["payload"]["candidates"][0], actor_identity="provider", decision_id="shot-knowledge-admission-" + "d" * 32, decision_at="2026-08-10T00:00:00Z", project_id=source[0].value["project_id"], classification=source[0].value["classification"])

    def test_tampered_candidate_or_scope_fails_closed(self):
        source, candidates, decision, _ = self._admit()
        raw = candidates.to_json_value(); raw["payload"]["candidates"][0]["proposition"]["attribute"] = "movement"
        raw["payload"]["semantic_result_digest"] = canonical_digest({**raw["payload"], "semantic_result_digest": None})
        raw["integrity"]["payload_sha256"] = canonical_digest(raw["payload"])
        raw["integrity"]["complete_result_sha256"] = canonical_digest({**raw, "integrity": {"payload_sha256": raw["integrity"]["payload_sha256"]}})
        task = lesson_task(source)
        with self.assertRaises(Exception):
            validate_shot_cinematography_lesson_candidate_set(
                raw, task=task, pattern_set=source[2],
                invocation_binding_digest="0" * 64,
            )

    def test_withdrawal_challenge_and_supersession_are_not_current(self):
        _, _, _, admitted = self._admit()
        for kind, reason in (("withdraw", "owner_request"), ("challenge", "evidence_challenge"), ("revoke", "integrity_failure")):
            event = create_lifecycle_event(event_id="shot-knowledge-lifecycle-" + ({"withdraw": "a", "challenge": "b", "revoke": "c"}[kind] * 32), event_kind=kind, actor_identity="human-reviewer-001", target_knowledge_id=admitted.knowledge.value["knowledge_id"], target_knowledge_digest=admitted.knowledge.digest, event_at="2026-09-01T00:00:00Z", reason_code=reason)
            with self.assertRaises(ValueError):
                current_use_eligible(admitted.knowledge, lifecycle_events=[event], validation_time="2026-10-01T00:00:00Z")

    def test_unknown_lifecycle_and_recommendation_fields_are_rejected(self):
        _, _, _, admitted = self._admit()
        event = {"schema_version": "1", "contract_identity": "shot_cinematography_knowledge_lifecycle_event", "contract_version": "99"}
        with self.assertRaises(Exception):
            current_use_eligible(admitted.knowledge, lifecycle_events=[event], validation_time="2026-09-01T00:00:00Z")
        raw = admitted.knowledge.to_json_value(); raw["recommendation"] = "use this"
        with self.assertRaises(Exception):
            current_use_eligible(raw, validation_time="2026-09-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
