import copy
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "character_continuity_contracts"))

from fixtures import identity, observation, reference, scene_breakdown, sequence, task
from vss_context import ContextAssembler
from vss_commands.runner import CommandRunner
from vss_context_contracts import ContextContractRegistry, validate_context
from vss_movie_character_continuity import CharacterContinuityProviderView, CharacterContinuityRuleCatalogue, character_continuity_provider_view
from vss_movie_contracts import (
    MovieContractRegistry, validate_character_identity, validate_character_observation,
    validate_character_reference, validate_character_continuity_observation_set,
    validate_character_continuity_task, validate_continuity_sequence,
    validate_executable_character_continuity_task, validate_scene_breakdown,
)
from vss_movie_contracts.errors import MovieContractError
from vss_movie_scene_breakdown import MovieRevocation, MovieRevocationSnapshot
from vss_reasoning import InvalidReasoningRequest, ReasoningAuditFailure
from vss_reasoning.gateway import ReasoningGateway
from vss_reasoning.registry import ReasoningImplementationRegistry
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_providers import DeterministicCharacterContinuityProvider


class Audit:
    def __init__(self, fail=False): self.records=[]; self.fail=fail
    def append(self, record):
        if self.fail: raise RuntimeError("audit unavailable")
        self.records.append(record)


class CharacterContinuityReasoningTests(unittest.TestCase):
    def setUp(self):
        self.movie = MovieContractRegistry.built_in(); self.context_registry = ContextContractRegistry.built_in()
        self.breakdown = validate_scene_breakdown(scene_breakdown(), self.movie)
        self.sequence = validate_continuity_sequence(sequence(self.breakdown), self.breakdown, self.movie)
        self.reference = validate_character_reference(reference(), self.movie)
        self.identity = validate_character_identity(identity([self.reference.to_json_value()]), [self.reference], self.movie)
        raw = [observation(self.sequence.value, "presence", 1), observation(self.sequence.value, "possession", 1), observation(self.sequence.value, "physical_state", 2), observation(self.sequence.value, "physical_state", 3)]
        raw[-1]["payload"]["state"] = "restrained"
        raw[-1]["observation_content_digest"] = canonical_digest({k:v for k,v in raw[-1].items() if k != "observation_content_digest"})
        self.observations = tuple(validate_character_observation(x, self.identity, self.sequence, self.movie) for x in raw)
        self.task_v1 = validate_character_continuity_task(task(self.sequence.value), self.sequence, [self.identity], self.movie)
        self.task = validate_executable_character_continuity_task(task(self.sequence.value, "2"), self.sequence, [self.identity], self.movie)
        self.context_audit = Audit(); self.reasoning_audit = Audit()
        assembled = ContextAssembler(audit=self.context_audit).assemble_character_continuity(self.task, self.sequence, (self.identity,), self.observations, correlation_id=self.task.value["correlation_id"], environment="development")
        self.context = assembled.context; self.report = assembled.report
        self.gateway = ReasoningGateway._for_testing(implementations=ReasoningImplementationRegistry.built_in(), audit=self.reasoning_audit)

    def execute(self, **kwargs):
        return self.gateway.execute_character_continuity(kwargs.pop("task", self.task), kwargs.pop("context", self.context), continuity_sequence=self.sequence, character_identities=(self.identity,), observations=self.observations, environment="development", correlation_id=self.task.value["correlation_id"], **kwargs)

    def test_exact_registry_evolution_and_context_registration(self):
        self.assertEqual(self.movie.resolve_result("analyze_character_continuity/1", "character_continuity_observation_set/1"), "character_continuity_observation_set/1")
        self.assertEqual(self.movie.resolve_result("analyze_character_continuity/2", "character_continuity_observation_set/1"), "character_continuity_observation_set/1")
        self.assertEqual(self.context_registry.resolve("character_continuity_context", "1").schema_identity, "vss.character_continuity_context/1")
        with self.assertRaises(Exception): self.context_registry.resolve("character_continuity_context", "latest")

    def test_v1_remains_valid_but_cannot_assemble_or_execute(self):
        self.assertEqual(self.task_v1.value["implementation_availability"], "not_implemented")
        with self.assertRaises(Exception):
            ContextAssembler(audit=Audit()).assemble_character_continuity(self.task_v1, self.sequence, (self.identity,), self.observations, correlation_id=self.task_v1.value["correlation_id"], environment="development")
        with patch.object(DeterministicCharacterContinuityProvider, "analyze", autospec=True) as provider:
            with self.assertRaises(InvalidReasoningRequest): self.execute(task=self.task_v1)
            with self.assertRaises(InvalidReasoningRequest): self.execute(task=self.task_v1, dry_run=True)
            self.assertEqual(provider.call_count, 0)

    def test_context_is_generic_valid_bounded_and_report_is_safe(self):
        validated = validate_context(self.context.to_json_value(), self.context_registry)
        self.assertEqual(validated.value["semantic_task_version"], "2")
        self.assertEqual(len(validated.value["payload"]["selected_scenes"]), 3)
        self.assertEqual(self.report["observation_count"], 4)
        self.assertNotIn("observations", self.report)
        self.assertEqual(len(self.context_audit.records), 1)

    def test_assembly_requires_validated_bound_artifacts(self):
        with self.assertRaises(Exception):
            ContextAssembler(audit=Audit()).assemble_character_continuity(self.task.to_json_value(), self.sequence, (self.identity,), self.observations, correlation_id=self.task.value["correlation_id"], environment="development")
        with self.assertRaises(Exception):
            ContextAssembler(audit=Audit()).assemble_character_continuity(self.task, self.sequence.to_json_value(), (self.identity,), self.observations, correlation_id=self.task.value["correlation_id"], environment="development")

    def test_provider_view_is_minimal_deeply_immutable_and_exact(self):
        view = character_continuity_provider_view(self.context)
        self.assertIs(type(view), CharacterContinuityProviderView)
        exposed = set(view.__dataclass_fields__)
        self.assertFalse(exposed & {"runtime","audit","registry","report","workflow","capability","path","provider","strategy"})
        with self.assertRaises(Exception): view.project_id = "other"
        with self.assertRaises(Exception): view.observations[0]["category"] = "location"
        with self.assertRaises(TypeError): DeterministicCharacterContinuityProvider().analyze(self.context)

    def test_catalogue_is_exact_immutable_and_persistence_is_off(self):
        catalogue = CharacterContinuityRuleCatalogue.built_in()
        self.assertEqual(catalogue.persistence, "off")
        self.assertEqual(catalogue.admitted_categories, ("presence","possession","physical_state"))
        self.assertEqual(catalogue.digest, CharacterContinuityRuleCatalogue.built_in().digest)
        with self.assertRaises(Exception): catalogue.persistence = "on"

    def test_gateway_calls_once_and_independently_validates_result(self):
        with patch.object(DeterministicCharacterContinuityProvider, "analyze", autospec=True, side_effect=DeterministicCharacterContinuityProvider.analyze) as provider:
            output = self.execute()
            self.assertEqual(provider.call_count, 1)
        self.assertEqual(output["provider_call_count"], 1)
        validate_character_continuity_observation_set(output["character_continuity_observation_set"], self.observations, self.sequence, self.task)
        self.assertEqual(len(self.reasoning_audit.records), 1)

    def test_nonmention_never_becomes_absence_transition_or_contradiction(self):
        result = self.execute()["character_continuity_observation_set"]
        text = str(result).lower()
        for forbidden in ("does_not_possess", "lost", "removed", "disappearance"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(result["payload"]["explicit_transitions"], [])
        self.assertEqual(result["payload"]["contradictions"], [])
        self.assertFalse(result["payload"]["review_suggested"])

    def test_changed_state_is_unknown_not_generic_contradiction(self):
        result = self.execute()["character_continuity_observation_set"]
        self.assertTrue(any("not generically contradictory" in x for x in result["payload"]["unknowns"]))

    def test_dry_run_calls_zero_providers_and_returns_no_result(self):
        with patch.object(DeterministicCharacterContinuityProvider, "analyze", autospec=True) as provider:
            output = self.execute(dry_run=True)
            self.assertEqual(provider.call_count, 0)
        self.assertEqual(output["readiness"]["provider_call_count"], 0)
        self.assertIsNone(output["readiness"]["result_digest"])

    def test_invalid_expired_and_revoked_contexts_call_zero_providers(self):
        invalid = self.context.to_json_value(); invalid["context_content_digest"] = "0"*64
        expired = self.context.to_json_value(); expired["expires_at"] = expired["constructed_at"]; expired["integrity"]["complete_context_sha256"] = canonical_digest({**expired, "integrity":{}})
        revocations = MovieRevocationSnapshot((MovieRevocation("character_observation", self.observations[0].value["observation_id"], self.observations[0].value["observation_content_digest"], "2000-01-01T00:00:00Z", "test"),))
        with patch.object(DeterministicCharacterContinuityProvider, "analyze", autospec=True) as provider:
            for context, rev in ((invalid,None),(expired,None),(self.context,revocations)):
                with self.assertRaises(InvalidReasoningRequest): self.execute(context=context, revocations=rev)
            self.assertEqual(provider.call_count, 0)

    def test_determinism_input_order_and_correlation_domains(self):
        first = self.execute(); second = self.execute()
        self.assertEqual(first["semantic_result_digest"], second["semantic_result_digest"])
        self.assertEqual(first["provider_visible_digest"], second["provider_visible_digest"])
        reverse = ContextAssembler(audit=Audit()).assemble_character_continuity(self.task, self.sequence, (self.identity,), tuple(reversed(self.observations)), correlation_id=self.task.value["correlation_id"], environment="development").context
        self.assertEqual(reverse.value["context_content_digest"], self.context.value["context_content_digest"])

    def test_semantic_digests_are_process_cwd_and_hash_seed_independent(self):
        script = """
from fixtures import identity,observation,reference,scene_breakdown,sequence,task
from vss_movie_contracts import *
from vss_movie_character_continuity import *
from vss_reasoning_contracts import canonical_digest
r=MovieContractRegistry.built_in(); b=validate_scene_breakdown(scene_breakdown(),r); s=validate_continuity_sequence(sequence(b),b,r); ref=validate_character_reference(reference(),r); ident=validate_character_identity(identity([ref.to_json_value()]),[ref],r); t=validate_executable_character_continuity_task(task(s.value,'2'),s,[ident],r); obs=validate_character_observation(observation(s.value,'possession',1),ident,s,r); c=assemble_character_continuity_context(t,s,(ident,),(obs,),validation_time='2026-08-08T00:00:00Z'); v=character_continuity_provider_view(c); notes=analyze_explicit_observations(v); out=create_character_continuity_result(v,{'request_id':t.value['request_id'],'correlation_id':t.value['correlation_id']},notes); print(c.value['context_content_digest'],v.provider_visible_digest,out['payload']['semantic_result_digest'])
"""
        env = dict(os.environ); env["PYTHONPATH"] = f"{ROOT/'src'}:{ROOT/'tests/character_continuity_contracts'}"
        values=[]
        for seed,cwd in (("1",ROOT),("991",Path("/tmp"))):
            current=dict(env); current["PYTHONHASHSEED"]=seed; current["M5_2_HARMLESS"]="different-"+seed
            values.append(subprocess.run([sys.executable,"-c",script],cwd=cwd,env=current,check=True,capture_output=True,text=True).stdout.strip())
        self.assertEqual(values[0], values[1])

    def test_concurrent_requests_are_isolated(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: self.execute(), range(12)))
        self.assertEqual(len({x["semantic_result_digest"] for x in results}), 1)
        self.assertEqual(len(self.reasoning_audit.records), 12)

    def test_context_and_result_substitution_fail_closed(self):
        bad = self.context.to_json_value(); bad["project_id"] = "other-project"; bad["integrity"]["complete_context_sha256"] = canonical_digest({**bad, "integrity":{}})
        with self.assertRaises(InvalidReasoningRequest): self.execute(context=bad)

    def test_audit_failure_is_fatal_and_single_attempt(self):
        audit = Audit(fail=True)
        gateway = ReasoningGateway._for_testing(implementations=ReasoningImplementationRegistry.built_in(), audit=audit)
        with self.assertRaises(ReasoningAuditFailure):
            gateway.execute_character_continuity(self.task, self.context, continuity_sequence=self.sequence, character_identities=(self.identity,), observations=self.observations, environment="development", correlation_id=self.task.value["correlation_id"])
        self.assertEqual(audit.records, [])

    def test_narrow_command_routes_assemble_and_analyze_without_policy_logic(self):
        bundle = {"task":self.task.to_json_value(), "scene_breakdown":self.breakdown.to_json_value(), "continuity_sequence":self.sequence.to_json_value(), "character_references":[self.reference.to_json_value()], "character_identities":[self.identity.to_json_value()], "character_observations":[x.to_json_value() for x in self.observations]}
        assembled, code = CommandRunner(reasoning_gateway=self.gateway).run("movie.context-assemble-character-continuity", "development", bundle, self.task.value["correlation_id"])
        self.assertEqual(code, 0)
        analyzed, code = CommandRunner(reasoning_gateway=self.gateway).run("movie.analyze-character-continuity", "development", {**bundle, "context":assembled["output"]["context"]}, self.task.value["correlation_id"])
        self.assertEqual(code, 0)
        self.assertEqual(analyzed["output"]["provider_call_count"], 1)


if __name__ == "__main__": unittest.main()
