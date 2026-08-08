import concurrent.futures
import os
import subprocess
import sys
import unittest

from vss_movie_contracts import (
    MovieContractRegistry, ValidatedMovieArtifact, validate_character_reference,
    validate_character_identity, validate_continuity_sequence, validate_character_observation,
    validate_character_continuity_task, validate_character_continuity_observation_set,
    validate_scene_breakdown,
)
from vss_movie_contracts.errors import MovieContractError
from vss_reasoning_contracts import canonical_digest
from vss_reasoning_contracts import load_json_document
from vss_reasoning_contracts.errors import InvalidSemanticInput, UnsafeSemanticContent

from fixtures import copied, identity, observation, reference, result, scene_breakdown, sequence, task


class CharacterContinuityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=MovieContractRegistry.built_in()
        cls.breakdown=validate_scene_breakdown(scene_breakdown(), cls.registry)
        cls.sequence_value=sequence(cls.breakdown)
        cls.sequence=validate_continuity_sequence(cls.sequence_value, cls.breakdown, cls.registry)
        cls.reference=validate_character_reference(reference(), cls.registry)
        cls.identity=validate_character_identity(identity([cls.reference.to_json_value()]), [cls.reference], cls.registry)

    def assertRejected(self, validator, value, *args):
        with self.assertRaises(MovieContractError): validator(value, *args)

    def test_registry_exact_registration_compatibility_and_immutability(self):
        expected={"character_reference/1","character_identity/1","continuity_sequence/1","character_observation/1","analyze_character_continuity/1","character_continuity_observation_set/1"}
        actual={item.identity for item in self.registry.registrations}
        self.assertTrue(expected <= actual)
        self.assertEqual(self.registry.resolve_result("analyze_character_continuity/1","character_continuity_observation_set/1"),"character_continuity_observation_set/1")
        self.assertNotIn("character_continuity_context/1",actual)
        with self.assertRaises(TypeError): self.registry.schemas["x"]={}
        with self.assertRaises(TypeError): self.registry.compatibility["x"]="y"
        with self.assertRaises(MovieContractError): self.registry.resolve("character_reference","latest")

    def test_reference_valid_id_bounds_and_digest(self):
        self.assertEqual(self.reference.value["display_label"],"Arin")
        for field,value in (("reference_id","Arin"),("content_digest","0"*64),("actor_id","actor-1"),("metadata",{})):
            candidate=copied(reference()); candidate[field]=value
            self.assertRejected(validate_character_reference,candidate,self.registry)
        for mutate in (lambda value: value.update(project_id="other-project"), lambda value: value["source_binding"].update(digest="0"*64)):
            candidate=copied(reference()); mutate(candidate)
            self.assertRejected(validate_character_reference,candidate,self.registry)

    def test_display_label_unicode_and_collisions_do_not_bind_identity(self):
        first=validate_character_reference(reference("character-ref-guard-a","Guard"),self.registry)
        second=validate_character_reference(reference("character-ref-guard-b","Guard"),self.registry)
        self.assertNotEqual(first.value["reference_id"],second.value["reference_id"])
        composed=validate_character_reference(reference("character-ref-accent-a","Café"),self.registry)
        decomposed=validate_character_reference(reference("character-ref-accent-b","Cafe\u0301"),self.registry)
        self.assertNotEqual(composed.value["display_label"],decomposed.value["display_label"])
        lookalike=validate_character_reference(reference("character-ref-lookalike","Аrin"),self.registry)
        uppercase=validate_character_reference(reference("character-ref-uppercase","ARIN"),self.registry)
        self.assertNotEqual(lookalike.value["display_label"],uppercase.value["display_label"])
        candidate=copied(reference()); candidate["reference_id"]="character-ref-árin"
        self.assertRejected(validate_character_reference,candidate,self.registry)

    def test_identity_requires_exact_unambiguous_reference_binding(self):
        self.assertEqual(self.identity.value["identity_basis"],"explicit_source_identity")
        base=identity([self.reference.to_json_value()])
        candidate=copied(base); candidate["ambiguity"]=["Guard could refer to two people"]
        candidate["content_digest"]=canonical_digest({k:v for k,v in candidate.items() if k!="content_digest"})
        self.assertRejected(validate_character_identity,candidate,[self.reference],self.registry)
        for field,value in (("bound_reference_ids",["character-ref-missing"]),("actor_identity","actor-1"),("identity_basis","display_label_match")):
            candidate=copied(base); candidate[field]=value
            if "content_digest" in candidate: candidate["content_digest"]=canonical_digest({k:v for k,v in candidate.items() if k!="content_digest"})
            self.assertRejected(validate_character_identity,candidate,[self.reference],self.registry)
        candidate=copied(base); candidate["bound_reference_content_digests"]=["0"*64]; candidate["content_digest"]=canonical_digest({k:v for k,v in candidate.items() if k!="content_digest"})
        self.assertRejected(validate_character_identity,candidate,[self.reference],self.registry)
        extra=validate_character_reference(reference("character-ref-zara","Zara"),self.registry)
        self.assertRejected(validate_character_identity,base,[self.reference,extra],self.registry)
        self.assertRejected(validate_character_identity,base,[self.reference,self.reference],self.registry)
        first=reference("character-ref-arin-a","Arin"); second=reference("character-ref-arin-b","Arin")
        artifacts=[validate_character_reference(item,self.registry) for item in (first,second)]
        ordered=identity([first,second]); validate_character_identity(ordered,artifacts,self.registry)
        reordered=copied(ordered); reordered["bound_reference_ids"].reverse(); reordered["bound_reference_content_digests"].reverse(); reordered["content_digest"]=canonical_digest({k:v for k,v in reordered.items() if k!="content_digest"})
        self.assertRejected(validate_character_identity,reordered,list(reversed(artifacts)),self.registry)

    def test_sequence_exact_explicit_chronology_and_scene_binding(self):
        self.assertEqual([x["continuity_position"] for x in self.sequence.value["selected_scenes"]],[1,2,3])
        cases=[]
        one=copied(self.sequence_value); one["selected_scenes"]=one["selected_scenes"][:1]; cases.append(one)
        duplicate=copied(self.sequence_value); duplicate["selected_scenes"][1]["scene_id"]=duplicate["selected_scenes"][0]["scene_id"]; cases.append(duplicate)
        gap=copied(self.sequence_value); gap["selected_scenes"][1]["continuity_position"]=3; cases.append(gap)
        digest=copied(self.sequence_value); digest["selected_scenes"][0]["scene_content_digest"]="0"*64; cases.append(digest)
        unknown=copied(self.sequence_value); unknown["selected_scenes"][0]["scene_id"]="scene-unknown"; cases.append(unknown)
        breakdown_digest=copied(self.sequence_value); breakdown_digest["scene_breakdown_digest"]="0"*64; cases.append(breakdown_digest)
        project=copied(self.sequence_value); project["project_id"]="other-project"; cases.append(project)
        for candidate in cases:
            candidate["content_digest"]=canonical_digest({k:v for k,v in candidate.items() if k!="content_digest"})
            self.assertRejected(validate_continuity_sequence,candidate,self.breakdown,self.registry)
        ordinal=copied(self.sequence_value); ordinal["selected_scenes"][0]["ordinal"]=1
        self.assertRejected(validate_continuity_sequence,ordinal,self.breakdown,self.registry)

    def test_explicit_continuity_order_is_independent_of_scene_ordinal(self):
        value=copied(self.sequence_value); value["selected_scenes"].reverse()
        for position,item in enumerate(value["selected_scenes"],1): item["continuity_position"]=position
        value["content_digest"]=canonical_digest({k:v for k,v in value.items() if k!="content_digest"})
        admitted=validate_continuity_sequence(value,self.breakdown,self.registry)
        self.assertEqual(admitted.value["selected_scenes"][0]["scene_id"],"scene-continuity-003")

    def test_eight_scene_boundary_and_overflow(self):
        breakdown_value=scene_breakdown(); seed=copied(breakdown_value["payload"]["ordered_scenes"][-1])
        for position in range(4,9):
            item=copied(seed); item["ordinal"]=position; item["scene_id"]=f"scene-extra-{position}"; item["source_span"]={"start":position*100,"end":position*100+50}; item["scene_content_digest"]=canonical_digest({k:v for k,v in item.items() if k!="scene_content_digest"}); breakdown_value["payload"]["ordered_scenes"].append(item)
        breakdown_value["integrity"]["payload_sha256"]=canonical_digest(breakdown_value["payload"])
        breakdown=validate_scene_breakdown(breakdown_value,self.registry); value=sequence(breakdown)
        value["content_digest"]=canonical_digest({k:v for k,v in value.items() if k!="content_digest"})
        validate_continuity_sequence(value,breakdown,self.registry)
        value["selected_scenes"].append({"scene_id":"scene-extra-9","scene_content_digest":seed["scene_content_digest"],"continuity_position":9})
        self.assertRejected(validate_continuity_sequence,value,breakdown,self.registry)

    def test_observation_categories_are_positive_explicit_and_bound(self):
        for category,ordinal in (("presence",1),("possession",1),("physical_state",3)):
            value=observation(self.sequence_value,category,ordinal)
            validate_character_observation(value,self.identity,self.sequence,self.registry)
        unsupported=copied(observation(self.sequence_value)); unsupported["category"]="location"
        self.assertRejected(validate_character_observation,unsupported,self.identity,self.sequence,self.registry)
        absent=copied(observation(self.sequence_value)); absent["payload"]["state"]="absent"
        self.assertRejected(validate_character_observation,absent,self.identity,self.sequence,self.registry)
        negative=copied(observation(self.sequence_value,"possession",1)); negative["payload"]["state"]="does_not_possess"
        self.assertRejected(validate_character_observation,negative,self.identity,self.sequence,self.registry)
        recovered=copied(observation(self.sequence_value,"physical_state",3)); recovered["payload"]["state"]="recovered"
        self.assertRejected(validate_character_observation,recovered,self.identity,self.sequence,self.registry)
        for category in ("costume","emotion","relationship","dialogue","performance"):
            candidate=copied(observation(self.sequence_value)); candidate["category"]=category
            self.assertRejected(validate_character_observation,candidate,self.identity,self.sequence,self.registry)
        inherited=copied(observation(self.sequence_value)); inherited["persists_until"]="transition"
        self.assertRejected(validate_character_observation,inherited,self.identity,self.sequence,self.registry)

    def test_observation_substitution_and_digest_fail_closed(self):
        base=observation(self.sequence_value,"possession",1)
        for field,value in (("character_id","character-other"),("scene_id","scene-other"),("sequence_position",2),("continuity_sequence_digest","0"*64),("observation_content_digest","0"*64)):
            candidate=copied(base); candidate[field]=value
            self.assertRejected(validate_character_observation,candidate,self.identity,self.sequence,self.registry)

    def test_task_is_validation_only_and_exact(self):
        valid_task=task(self.sequence_value); validate_character_continuity_task(valid_task,self.sequence,[self.identity],self.registry)
        for field,injected in (("provider","x"),("prompt","x"),("execution",{}),("expected_result_version","latest"),("implementation_availability","required")):
            candidate=copied(valid_task); candidate[field]=injected
            if "task_content_digest" in candidate: candidate["task_content_digest"]=canonical_digest({k:v for k,v in candidate.items() if k!="task_content_digest"})
            self.assertRejected(validate_character_continuity_task,candidate,self.sequence,[self.identity],self.registry)
        candidate=copied(valid_task); candidate["selected_observation_categories"].reverse(); candidate["task_content_digest"]=canonical_digest({k:v for k,v in candidate.items() if k!="task_content_digest"})
        self.assertRejected(validate_character_continuity_task,candidate,self.sequence,[self.identity],self.registry)

    def test_cross_artifact_dependencies_are_mandatory_and_validated(self):
        with self.assertRaises(MovieContractError): validate_character_identity(identity([self.reference.to_json_value()]),registry=self.registry)
        with self.assertRaises(MovieContractError): validate_continuity_sequence(self.sequence_value,registry=self.registry)
        value=observation(self.sequence_value,"presence",1)
        with self.assertRaises(MovieContractError): validate_character_observation(value,registry=self.registry)
        with self.assertRaises(MovieContractError): validate_character_observation(value,self.identity,None,self.registry)
        task_value=task(self.sequence_value)
        with self.assertRaises(MovieContractError): validate_character_continuity_task(task_value,registry=self.registry)
        result_value=result(self.sequence_value,[value])
        artifact=validate_character_observation(value,self.identity,self.sequence,self.registry)
        with self.assertRaises(MovieContractError): validate_character_continuity_observation_set(result_value,[artifact],registry=self.registry)
        with self.assertRaises(MovieContractError): validate_character_identity(identity([self.reference.to_json_value()]),[self.reference.to_json_value()],self.registry)

    def test_result_is_inert_resolved_and_immutable(self):
        values=[observation(self.sequence_value,"presence",1),observation(self.sequence_value,"possession",1),observation(self.sequence_value,"physical_state",3)]
        artifacts=[validate_character_observation(x,self.identity,self.sequence,self.registry) for x in values]
        admitted_task=validate_character_continuity_task(task(self.sequence_value),self.sequence,[self.identity],self.registry)
        artifact=validate_character_continuity_observation_set(result(self.sequence_value,values),artifacts,self.sequence,admitted_task,self.registry)
        with self.assertRaises(TypeError): artifact.value["payload"]["review_suggested"]=True
        values[0]["scene_id"]="scene-substituted"
        self.assertEqual(artifact.value["payload"]["observations"][0]["scene_id"],"scene-continuity-001")
        exported=artifact.to_json_value(); exported["payload"]["observations"].clear()
        self.assertEqual(len(artifact.value["payload"]["observations"]),3)

    def test_result_rejects_substitution_actions_and_unresolved_observations(self):
        value=observation(self.sequence_value,"presence",1); artifact=validate_character_observation(value,self.identity,self.sequence,self.registry)
        base=result(self.sequence_value,[value])
        admitted_task=validate_character_continuity_task(task(self.sequence_value),self.sequence,[self.identity],self.registry)
        validate_character_continuity_observation_set(base,[artifact],self.sequence,admitted_task,self.registry)
        for mutation in ("recommendation","repair","action","priority","severity","approval","plan","workflow"):
            candidate=copied(base); candidate["payload"][mutation]="must_fix"
            self.assertRejected(validate_character_continuity_observation_set,candidate,[artifact],self.sequence,admitted_task,self.registry)
        self.assertRejected(validate_character_continuity_observation_set,base,[],self.sequence,admitted_task,self.registry)
        candidate=copied(base); candidate["payload"]["observations"][0]["scene_id"]="scene-other"
        candidate["payload"]["semantic_result_digest"]=canonical_digest({**candidate["payload"],"semantic_result_digest":None}); candidate["integrity"]["payload_sha256"]=canonical_digest(candidate["payload"]); candidate["integrity"]["complete_result_sha256"]=canonical_digest({**candidate,"integrity":{"payload_sha256":candidate["integrity"]["payload_sha256"]}})
        self.assertRejected(validate_character_continuity_observation_set,candidate,[artifact],self.sequence,admitted_task,self.registry)
        candidate=copied(base); candidate["request_id"]="substituted-request"; candidate["integrity"]["complete_result_sha256"]=canonical_digest({**candidate,"integrity":{"payload_sha256":candidate["integrity"]["payload_sha256"]}})
        with self.assertRaises(MovieContractError): validate_character_continuity_observation_set(candidate,[artifact],self.sequence,admitted_task,self.registry)

    def test_transition_and_contradiction_are_structural_only(self):
        first=observation(self.sequence_value,"possession",1)
        second=observation(self.sequence_value,"possession",2)
        artifacts=[validate_character_observation(item,self.identity,self.sequence,self.registry) for item in (first,second)]
        value=result(self.sequence_value,[first,second])
        transition={"transition_id":"continuity-transition-lantern","character_id":"character-arin","category":"possession","from_observation_id":first["observation_id"],"from_observation_digest":first["observation_content_digest"],"to_observation_id":second["observation_id"],"to_observation_digest":second["observation_content_digest"],"transition_basis":"explicit_source_transition","evidence_references":["continuity-fragment-001:explicit-transition"],"qualification":"Structural explicit-transition fixture only.","confidence":{"level":"low","basis":"No transition analysis was performed.","qualifications":["The structure does not prove a state change."]},"limitations":["No persistence is inferred."],"transition_content_digest":""}
        transition["transition_content_digest"]=canonical_digest({k:v for k,v in transition.items() if k!="transition_content_digest"})
        contradiction={"contradiction_id":"continuity-contradiction-lantern","character_id":"character-arin","category":"possession","observation_bindings":[{"observation_id":item["observation_id"],"observation_digest":item["observation_content_digest"]} for item in (first,second)],"evidence_references":["continuity-fragment-001:scene-1","continuity-fragment-001:scene-2"],"qualification":"Structural unresolved fixture; logical incompatibility was not determined.","confidence":{"level":"low","basis":"Validation establishes bindings only.","qualifications":["No contradiction discovery was performed."]},"unresolved_status":"unresolved","limitations":["Human semantic review would be required."],"contradiction_content_digest":""}
        contradiction["contradiction_content_digest"]=canonical_digest({k:v for k,v in contradiction.items() if k!="contradiction_content_digest"})
        value["payload"]["explicit_transitions"]=[transition]; value["payload"]["contradictions"]=[contradiction]; value["payload"]["review_suggested"]=True
        value["payload"]["semantic_result_digest"]=canonical_digest({**value["payload"],"semantic_result_digest":None}); value["integrity"]["payload_sha256"]=canonical_digest(value["payload"]); value["integrity"]["complete_result_sha256"]=canonical_digest({**value,"integrity":{"payload_sha256":value["integrity"]["payload_sha256"]}})
        admitted_task=validate_character_continuity_task(task(self.sequence_value),self.sequence,[self.identity],self.registry)
        validate_character_continuity_observation_set(value,artifacts,self.sequence,admitted_task,self.registry)
        invalid=copied(value); invalid["payload"]["contradictions"][0]["observation_bindings"][1]=copied(invalid["payload"]["contradictions"][0]["observation_bindings"][0])
        invalid["payload"]["contradictions"][0]["contradiction_content_digest"]=canonical_digest({k:v for k,v in invalid["payload"]["contradictions"][0].items() if k!="contradiction_content_digest"}); invalid["payload"]["semantic_result_digest"]=canonical_digest({**invalid["payload"],"semantic_result_digest":None}); invalid["integrity"]["payload_sha256"]=canonical_digest(invalid["payload"]); invalid["integrity"]["complete_result_sha256"]=canonical_digest({**invalid,"integrity":{"payload_sha256":invalid["integrity"]["payload_sha256"]}})
        self.assertRejected(validate_character_continuity_observation_set,invalid,artifacts,self.sequence,admitted_task,self.registry)
        def reseal(candidate, section, digest_field):
            record=candidate["payload"][section][0]; record[digest_field]=canonical_digest({k:v for k,v in record.items() if k!=digest_field})
            candidate["payload"]["semantic_result_digest"]=canonical_digest({**candidate["payload"],"semantic_result_digest":None}); candidate["integrity"]["payload_sha256"]=canonical_digest(candidate["payload"]); candidate["integrity"]["complete_result_sha256"]=canonical_digest({**candidate,"integrity":{"payload_sha256":candidate["integrity"]["payload_sha256"]}})
        mutations=(
            lambda record: record.update(to_observation_id=record["from_observation_id"],to_observation_digest=record["from_observation_digest"]),
            lambda record: record.update(from_observation_id=second["observation_id"],from_observation_digest=second["observation_content_digest"],to_observation_id=first["observation_id"],to_observation_digest=first["observation_content_digest"]),
            lambda record: record.update(character_id="character-other"),
            lambda record: record.update(category="physical_state"),
            lambda record: record.update(to_observation_id="character-observation-unknown"),
            lambda record: record.update(to_observation_digest="0"*64),
        )
        for mutate in mutations:
            candidate=copied(value); mutate(candidate["payload"]["explicit_transitions"][0]); reseal(candidate,"explicit_transitions","transition_content_digest")
            self.assertRejected(validate_character_continuity_observation_set,candidate,artifacts,self.sequence,admitted_task,self.registry)
        for field,injected in (("severity","critical"),("priority","urgent"),("repair","reshoot"),("action","must_fix")):
            candidate=copied(value); candidate["payload"]["contradictions"][0][field]=injected
            self.assertRejected(validate_character_continuity_observation_set,candidate,artifacts,self.sequence,admitted_task,self.registry)
        contradiction_mutations=(
            lambda record: record["observation_bindings"][1].update(observation_id="character-observation-unknown"),
            lambda record: record["observation_bindings"][1].update(observation_digest="0"*64),
            lambda record: record.update(character_id="character-other"),
            lambda record: record.update(category="physical_state"),
        )
        for mutate in contradiction_mutations:
            candidate=copied(value); mutate(candidate["payload"]["contradictions"][0]); reseal(candidate,"contradictions","contradiction_content_digest")
            self.assertRejected(validate_character_continuity_observation_set,candidate,artifacts,self.sequence,admitted_task,self.registry)

    def test_review_suggested_is_an_inert_boolean(self):
        value=observation(self.sequence_value,"presence",1); artifact=validate_character_observation(value,self.identity,self.sequence,self.registry)
        admitted_task=validate_character_continuity_task(task(self.sequence_value),self.sequence,[self.identity],self.registry)
        candidate=result(self.sequence_value,[value]); candidate["payload"]["review_suggested"]=True
        candidate["payload"]["semantic_result_digest"]=canonical_digest({**candidate["payload"],"semantic_result_digest":None}); candidate["integrity"]["payload_sha256"]=canonical_digest(candidate["payload"]); candidate["integrity"]["complete_result_sha256"]=canonical_digest({**candidate,"integrity":{"payload_sha256":candidate["integrity"]["payload_sha256"]}})
        validate_character_continuity_observation_set(candidate,[artifact],self.sequence,admitted_task,self.registry)
        candidate["payload"]["review_suggested"]="high"
        self.assertRejected(validate_character_continuity_observation_set,candidate,[artifact],self.sequence,admitted_task,self.registry)

    def test_duplicate_json_nonfinite_custom_mapping_and_constructor_rejected(self):
        with self.assertRaises(TypeError): ValidatedMovieArtifact(reference())
        class Custom(dict): pass
        self.assertRejected(validate_character_reference,Custom(reference()),self.registry)
        candidate=copied(reference()); candidate["source_binding"]["source_sequence"]=True
        self.assertRejected(validate_character_reference,candidate,self.registry)
        candidate=copied(reference()); candidate["display_label"]=float("nan")
        self.assertRejected(validate_character_reference,candidate,self.registry)
        candidate=copied(reference()); candidate["source_binding"]["source_sequence"]=10**100
        self.assertRejected(validate_character_reference,candidate,self.registry)
        candidate=copied(reference()); candidate["cycle"]=candidate
        self.assertRejected(validate_character_reference,candidate,self.registry)
        with self.assertRaises(InvalidSemanticInput): load_json_document('{"reference_id":"a","reference_id":"b"}')
        with self.assertRaises(UnsafeSemanticContent): load_json_document('{"value":NaN}')

    def test_schema_errors_are_stable_and_do_not_echo_values(self):
        candidate=copied(reference()); candidate["display_label"]=["private-story-value"]
        with self.assertRaises(MovieContractError) as raised: validate_character_reference(candidate,self.registry)
        self.assertEqual(str(raised.exception),"movie artifact does not match its contract")
        self.assertNotIn("private-story-value",str(raised.exception))

    def test_all_validated_artifacts_are_recursive_snapshots(self):
        reference_value=reference(); reference_artifact=validate_character_reference(reference_value,self.registry)
        identity_value=identity([reference_value]); identity_artifact=validate_character_identity(identity_value,[reference_artifact],self.registry)
        sequence_value=copied(self.sequence_value); sequence_artifact=validate_continuity_sequence(sequence_value,self.breakdown,self.registry)
        observation_value=observation(sequence_value,"presence",1); observation_artifact=validate_character_observation(observation_value,identity_artifact,sequence_artifact,self.registry)
        task_value=task(sequence_value); task_artifact=validate_character_continuity_task(task_value,sequence_artifact,[identity_artifact],self.registry)
        for artifact in (reference_artifact,identity_artifact,sequence_artifact,observation_artifact,task_artifact):
            with self.assertRaises(TypeError): artifact.value["schema_version"]="2"
            exported=artifact.to_json_value(); exported["schema_version"]="2"; self.assertEqual(artifact.value["schema_version"],"1")
        reference_value["declaration_evidence"].append("mutated")
        self.assertEqual(tuple(reference_artifact.value["declaration_evidence"]),("continuity-fragment-001:character-arin",))

    def test_determinism_hash_seed_and_concurrency(self):
        self.assertEqual(MovieContractRegistry.built_in().digest,self.registry.digest)
        command="from vss_movie_contracts import MovieContractRegistry; print(MovieContractRegistry.built_in().digest)"
        outputs=[]
        for seed in ("1","999"):
            env=dict(os.environ); env["PYTHONHASHSEED"]=seed
            outputs.append(subprocess.check_output([sys.executable,"-c",command],text=True,env=env).strip())
        self.assertEqual(outputs,[self.registry.digest,self.registry.digest])
        valid=reference()
        invalid=copied(valid); invalid["actor_id"]="actor"
        def run(index):
            try: return validate_character_reference(valid if index%2==0 else invalid,self.registry).digest
            except MovieContractError: return "rejected"
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(run,range(64)))
        self.assertEqual(results.count("rejected"),32)
        self.assertEqual(len(set(results)-{"rejected"}),1)


if __name__ == "__main__": unittest.main()
