import unittest
from copy import deepcopy
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "character_continuity_contracts"))

from fixtures import identity, observation, reference, scene_breakdown, seal, sequence, task, transition_evidence
from vss_context import ContextAssembler
from vss_context_contracts import ContextContractRegistry
from vss_movie_character_continuity import CharacterContinuityAnalysisRuleCatalogue, CharacterContinuityRuleCatalogue
from vss_movie_contracts import (
    MovieContractRegistry, validate_character_continuity_task,
    validate_character_continuity_transition_evidence, validate_character_identity,
    validate_character_observation, validate_character_reference,
    validate_continuity_sequence, validate_executable_character_continuity_task,
    validate_scene_breakdown,
)
from vss_reasoning.gateway import ReasoningGateway


class Audit:
    def __init__(self): self.records = []
    def append(self, record): self.records.append(record)


class CharacterContinuityM53Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.movie = MovieContractRegistry.built_in()
        cls.breakdown = validate_scene_breakdown(scene_breakdown(), cls.movie)
        cls.sequence = validate_continuity_sequence(sequence(cls.breakdown), cls.breakdown, cls.movie)
        cls.reference = validate_character_reference(reference(), cls.movie)
        cls.identity = validate_character_identity(identity([cls.reference.to_json_value()]), [cls.reference], cls.movie)
        first_raw = observation(cls.sequence.value, "physical_state", 1)
        second_raw = observation(cls.sequence.value, "physical_state", 2)
        second_raw["payload"]["state"] = "restrained"
        second_raw = seal(second_raw, "observation_content_digest")
        cls.observations = (
            validate_character_observation(first_raw, cls.identity, cls.sequence, cls.movie),
            validate_character_observation(second_raw, cls.identity, cls.sequence, cls.movie),
        )
        cls.task_v3 = validate_executable_character_continuity_task(task(cls.sequence.value, "3"), cls.sequence, [cls.identity], cls.movie)
        cls.transition = validate_character_continuity_transition_evidence(
            transition_evidence(cls.sequence.value, first_raw, second_raw), cls.observations, cls.sequence, cls.movie
        )

    def assemble(self, task_value=None, transitions=None):
        return ContextAssembler(audit=Audit()).assemble_character_continuity(
            task_value or self.task_v3, self.sequence, (self.identity,), self.observations,
            transition_evidence=(self.transition,) if transitions is None else transitions,
            correlation_id=self.task_v3.value["correlation_id"], environment="development",
        ).context

    def execute(self, context=None, task_value=None, transitions=None, dry_run=False):
        return ReasoningGateway.built_in().execute_character_continuity(
            task_value or self.task_v3, context or self.assemble(), continuity_sequence=self.sequence,
            character_identities=(self.identity,), observations=self.observations,
            transition_evidence=(self.transition,) if transitions is None else transitions,
            environment="development", correlation_id=self.task_v3.value["correlation_id"], dry_run=dry_run,
        )

    def test_exact_registrations_and_historical_catalogue(self):
        self.assertEqual(self.movie.resolve_result("analyze_character_continuity/3", "character_continuity_observation_set/1"), "character_continuity_observation_set/1")
        contexts = ContextContractRegistry.built_in()
        self.assertEqual(contexts.resolve("character_continuity_context", "2").schema_identity, "vss.character_continuity_context/2")
        self.assertEqual(CharacterContinuityRuleCatalogue.built_in().digest, "166f8a5057ab7098085350d54d36708ef618f9ccc875588cc1e26aece38dc13c")  # pragma: allowlist secret
        self.assertEqual(CharacterContinuityAnalysisRuleCatalogue.built_in().version, "1.1.0")

    def test_v1_v2_v3_task_semantics_are_exact(self):
        v1 = validate_character_continuity_task(task(self.sequence.value, "1"), self.sequence, [self.identity], self.movie)
        v2 = validate_executable_character_continuity_task(task(self.sequence.value, "2"), self.sequence, [self.identity], self.movie)
        self.assertEqual((v1.value["lifecycle"], v1.value["implementation_availability"]), ("defined_validation_only", "not_implemented"))
        self.assertEqual(v2.value["expected_context_version"], "1")
        self.assertEqual(self.task_v3.value["expected_context_version"], "2")

    def test_transition_evidence_is_independently_bound(self):
        self.assertEqual(self.transition.value["transition_basis"], "explicit_source_transition")
        forged = self.transition.to_json_value(); forged["to_observation_digest"] = "0" * 64; seal(forged, "content_digest")
        with self.assertRaises(Exception): validate_character_continuity_transition_evidence(forged, self.observations, self.sequence, self.movie)
        with self.assertRaises(Exception): validate_character_continuity_transition_evidence({"payload":{}}, self.observations, self.sequence, self.movie)

    def test_context_versions_reject_crossed_tasks(self):
        v2 = validate_executable_character_continuity_task(task(self.sequence.value, "2"), self.sequence, [self.identity], self.movie)
        v1_context = ContextAssembler(audit=Audit()).assemble_character_continuity(v2, self.sequence, (self.identity,), self.observations, correlation_id=v2.value["correlation_id"], environment="development").context
        v2_context = self.assemble()
        with self.assertRaises(Exception): self.execute(context=v1_context)
        with self.assertRaises(Exception): ReasoningGateway.built_in().execute_character_continuity(v2, v2_context, continuity_sequence=self.sequence, character_identities=(self.identity,), observations=self.observations, environment="development", correlation_id=v2.value["correlation_id"])

    def test_explicit_transition_is_preserved_and_qualified(self):
        payload = self.execute()["character_continuity_observation_set"]["payload"]
        self.assertEqual(len(payload["explicit_transitions"]), 1)
        self.assertEqual(payload["explicit_transitions"][0]["transition_basis"], "explicit_source_transition")
        self.assertIn("1.1.0", payload["explicit_transitions"][0]["qualification"])
        self.assertEqual(payload["contradictions"], [])
        self.assertFalse(payload["review_suggested"])

    def test_different_values_without_evidence_are_not_transition_or_contradiction(self):
        context = self.assemble(transitions=())
        payload = self.execute(context=context, transitions=())["character_continuity_observation_set"]["payload"]
        self.assertEqual(payload["explicit_transitions"], [])
        self.assertEqual(payload["contradictions"], [])
        self.assertTrue(any("incomparable" in value for value in payload["unknowns"]))

    def test_dry_run_has_zero_provider_calls_and_no_result(self):
        output = self.execute(dry_run=True)
        self.assertEqual(output["readiness"]["provider_call_count"], 0)
        self.assertIsNone(output["readiness"]["result_digest"])

    def test_invalid_transition_fails_before_provider(self):
        with self.assertRaises(Exception): self.execute(transitions=())

    def test_determinism(self):
        context = self.assemble()
        first = self.execute(context=context); second = self.execute(context=context)
        self.assertEqual(first["semantic_result_digest"], second["semantic_result_digest"])
        self.assertEqual(first["provider_visible_digest"], second["provider_visible_digest"])

    def test_nonmention_does_not_create_absence_loss_or_transition(self):
        raw = observation(self.sequence.value, "possession", 1)
        admitted = validate_character_observation(raw, self.identity, self.sequence, self.movie)
        context = ContextAssembler(audit=Audit()).assemble_character_continuity(
            self.task_v3, self.sequence, (self.identity,), (admitted,), transition_evidence=(),
            correlation_id=self.task_v3.value["correlation_id"], environment="development",
        ).context
        result = ReasoningGateway.built_in().execute_character_continuity(
            self.task_v3, context, continuity_sequence=self.sequence, character_identities=(self.identity,),
            observations=(admitted,), transition_evidence=(), environment="development",
            correlation_id=self.task_v3.value["correlation_id"],
        )["character_continuity_observation_set"]
        self.assertEqual(result["payload"]["explicit_transitions"], [])
        self.assertEqual(result["payload"]["contradictions"], [])
        self.assertFalse(any(term in str(result).lower() for term in ("does_not_possess", "lost", "absent")))

    def test_shared_gateway_concurrency_is_isolated(self):
        gateway = ReasoningGateway.built_in(); context = self.assemble()
        def run(_):
            return gateway.execute_character_continuity(
                self.task_v3, context, continuity_sequence=self.sequence, character_identities=(self.identity,),
                observations=self.observations, transition_evidence=(self.transition,), environment="development",
                correlation_id=self.task_v3.value["correlation_id"],
            )["semantic_result_digest"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            values = list(pool.map(run, range(8)))
        self.assertEqual(len(set(values)), 1)


if __name__ == "__main__":
    unittest.main()
