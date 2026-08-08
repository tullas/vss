import copy
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from vss_context import ContextAssembler
from vss_context_contracts import ContextContractRegistry, validate_context
from vss_movie_contracts import MovieContractRegistry, validate_production_option_set, validate_production_options_task
from vss_movie_contracts.errors import MovieContractError
from vss_movie_production_options import *
from vss_movie_scene_breakdown import MovieRevocation, MovieRevocationSnapshot, assemble_scene_context, break_down_scenes
from vss_reasoning import InvalidReasoningRequest, ReasoningAuditFailure
from vss_reasoning.gateway import ReasoningGateway
from vss_reasoning.registry import ReasoningImplementationRegistry
from vss_reasoning_contracts import canonical_digest, load_json_document
from vss_reasoning_providers import DeterministicSceneProductionOptionsProvider

ROOT=Path(__file__).resolve().parents[2]
def load(name): return load_json_document((ROOT/'tests/fixtures/movie'/name).read_bytes())

class Audit:
    def __init__(self, fail=False): self.records=[]; self.fail=fail
    def append(self, record):
        if self.fail: raise RuntimeError("unavailable")
        self.records.append(record)

class ProductionOptionsTests(unittest.TestCase):
    def setUp(self):
        self.request=load('generate-scene-production-options-request-valid.json')
        self.context=load('scene-production-options-context-valid.json')
        self.breakdown=load('scene-breakdown-valid.json')
        self.audit=Audit()
        self.gateway=ReasoningGateway._for_testing(implementations=ReasoningImplementationRegistry.built_in(),audit=self.audit)

    def test_registries_are_exact_immutable_and_deterministic(self):
        movie=MovieContractRegistry.built_in(); context=ContextContractRegistry.built_in()
        self.assertEqual(movie.digest,MovieContractRegistry.built_in().digest)
        self.assertIn('generate_scene_production_options/1',{r.identity for r in movie.registrations})
        self.assertIn('scene_production_option_set/1',{r.identity for r in movie.registrations})
        self.assertEqual(context.resolve('scene_production_options_context','1').schema_identity,'vss.scene_production_options_context/1')
        self.assertEqual(context.digest,ContextContractRegistry.built_in().digest)
        with self.assertRaises(Exception): context.registrations[0].identity='x'

    def test_task_is_strict_and_rejects_policy_overrides(self):
        validate_production_options_task(self.request)
        for key in ('rank','provider','model','prompt','metadata','selected'):
            bad=copy.deepcopy(self.request); bad[key]=True
            with self.assertRaises(MovieContractError): validate_production_options_task(bad)

    def test_context_generic_validation_and_exact_scene_binding(self):
        validated=validate_context(self.context,ContextContractRegistry.built_in())
        self.assertEqual(validated.value['payload']['selected_scene_id'],self.request['scene_id'])
        bad=copy.deepcopy(self.context); bad['payload']['selected_scene_digest']='0'*64; bad['context_content_digest']=canonical_digest(bad['payload']); bad['integrity']['complete_context_sha256']=canonical_digest({**bad,'integrity':{}})
        with self.assertRaises(Exception): validate_context(bad,ContextContractRegistry.built_in())

    def test_assembly_preserves_qualifications_and_generates_no_options(self):
        outcome=ContextAssembler(audit=self.audit).assemble_scene_production_options(self.request,self.breakdown,correlation_id='m4-3-local-run',environment='development',validation_time='2026-08-02T00:00:00Z')
        self.assertNotIn('options',outcome.context.value['payload'])
        self.assertTrue(outcome.context.value['payload']['ambiguity'])
        self.assertTrue(outcome.context.value['payload']['unknowns'])
        self.assertEqual(outcome.report['status'],'success')
        self.assertEqual(len(self.audit.records),1)

    def test_unknown_scene_and_digest_substitution_are_rejected(self):
        for scene_id,digest in (('unknown',self.request['scene_content_digest']),(self.request['scene_id'],'0'*64)):
            with self.assertRaises(ValueError): assemble_production_options_context(self.breakdown,request_id='r',correlation_id='c',project_id='movie-local',scene_id=scene_id,scene_content_digest=digest,validation_time='2026-08-02T00:00:00Z')

    def test_catalogue_is_frozen_complete_stable_and_nonranking(self):
        a=ProductionProfileCatalogue.built_in(); b=ProductionProfileCatalogue.built_in()
        self.assertEqual(a.digest,b.digest); self.assertEqual([p.ordinal for p in a.profiles],[1,2,3,4])
        self.assertEqual([p.identity for p in a.profiles],['minimal_stage','location_live_action','stylized_2d','stylized_3d'])
        self.assertTrue(all(p.mandatory_unknowns and p.mandatory_external_validation and p.mandatory_limitations for p in a.profiles))
        self.assertFalse(any({'vendor','rank','score','recommended','selected'} & set(p.material()) for p in a.profiles))
        with self.assertRaises(Exception): a.profiles += (a.profiles[0],)

    def test_provider_view_is_deeply_immutable_and_structurally_isolated(self):
        view=production_provider_view(self.context)
        exposed={field for field in view.__dataclass_fields__}
        self.assertFalse(exposed & {'context','assembly_report','policy','revocation','registry','schema','audit','runtime','workflow','path','file','connector','callback'})
        with self.assertRaises(Exception): view.scene_id='x'
        with self.assertRaises(Exception): view.source_observations[0]['text']='x'
        with self.assertRaises(TypeError): DeterministicSceneProductionOptionsProvider().generate(self.context,{})

    def test_gateway_executes_once_validates_result_and_is_deterministic(self):
        with patch.object(DeterministicSceneProductionOptionsProvider,'generate',autospec=True,side_effect=DeterministicSceneProductionOptionsProvider.generate) as generate:
            first=self.gateway.execute_scene_production_options(self.request,self.context,environment='development',correlation_id='m4-3-local-run')
            self.assertEqual(generate.call_count,1)
        second=self.gateway.execute_scene_production_options(self.request,self.context,environment='development',correlation_id='m4-3-local-run')
        self.assertEqual(first['semantic_result_digest'],second['semantic_result_digest'])
        self.assertEqual([o['ordinal'] for o in first['scene_production_option_set']['payload']['options']],[1,2,3,4])
        self.assertEqual(first['provider_call_count'],1); validate_production_option_set(first['scene_production_option_set'])
        self.assertTrue(first['scene_production_option_set']['payload']['stable_order_is_not_ranking'])

    def test_dry_run_completes_binding_and_calls_zero_providers(self):
        with patch.object(DeterministicSceneProductionOptionsProvider,'generate',autospec=True) as generate:
            result=self.gateway.execute_scene_production_options(self.request,self.context,environment='development',correlation_id='m4-3-local-run',dry_run=True)
            self.assertEqual(generate.call_count,0)
        self.assertEqual(result['readiness']['provider_call_count'],0); self.assertIsNone(result['readiness']['result_digest'])
        self.assertRegex(result['readiness']['invocation_binding_digest'],r'^[0-9a-f]{64}$')

    def test_invalid_expired_and_revoked_contexts_make_zero_calls(self):
        cases=[]
        invalid=copy.deepcopy(self.context); invalid['payload']['selected_scene_id']='substitute'; cases.append((invalid,None))
        expired=copy.deepcopy(self.context); expired['expires_at']=expired['constructed_at']; expired['integrity']['complete_context_sha256']=canonical_digest({**expired,'integrity':{}}); cases.append((expired,None))
        rev=MovieRevocationSnapshot((MovieRevocation('scene',self.request['scene_id'],self.request['scene_content_digest'],'2026-08-02T00:00:01Z','test'),)); cases.append((self.context,rev))
        with patch.object(DeterministicSceneProductionOptionsProvider,'generate',autospec=True) as generate:
            for value,snapshot in cases:
                with self.assertRaises(InvalidReasoningRequest): self.gateway.execute_scene_production_options(self.request,value,environment='development',correlation_id='m4-3-local-run',revocations=snapshot)
            self.assertEqual(generate.call_count,0)

    def test_result_rejects_hidden_ranking_and_execution_fields(self):
        result=self.gateway.execute_scene_production_options(self.request,self.context,environment='development',correlation_id='m4-3-local-run')['scene_production_option_set']
        for key in ('rank','recommended','workflow','prompt'):
            bad=copy.deepcopy(result); bad['payload']['options'][0][key]=True; bad['integrity']['payload_sha256']=canonical_digest(bad['payload']); bad['integrity']['complete_result_sha256']=canonical_digest({**bad,'integrity':{'payload_sha256':bad['integrity']['payload_sha256']}})
            with self.assertRaises(MovieContractError): validate_production_option_set(bad)

    def test_audit_is_bound_and_failure_is_fatal(self):
        self.gateway.execute_scene_production_options(self.request,self.context,environment='development',correlation_id='m4-3-local-run')
        record=self.audit.records[-1]
        for key in ('scene_breakdown_digest','scene_id','context_content_digest','provider_visible_digest','invocation_binding_digest','provider_call_count','revocation_result','result_digest'): self.assertIsNotNone(record[key])
        failing=ReasoningGateway._for_testing(implementations=ReasoningImplementationRegistry.built_in(),audit=Audit(fail=True))
        with self.assertRaises(ReasoningAuditFailure): failing.execute_scene_production_options(self.request,self.context,environment='development',correlation_id='m4-3-local-run')

    def test_concurrent_requests_do_not_contaminate_results_or_audit(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(lambda _: self.gateway.execute_scene_production_options(self.request,self.context,environment='development',correlation_id='m4-3-local-run'),range(12)))
        self.assertEqual(len({r['semantic_result_digest'] for r in results}),1)
        self.assertEqual(len(self.audit.records),12)
        self.assertTrue(all(r['provider_call_count']==1 for r in self.audit.records))
