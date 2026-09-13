# Issue #165 — Assurance Fitness and Change-Impact Design Checkpoint v2

**Status:** revised proposal; implementation remains blocked pending current reviews and issue approval.
**Milestone:** `assurance-fitness-change-impact-v1`
**Proposed branch after clearance:** `feature/assurance-fitness-change-impact-v1`

## Concrete production value

The first useful subject is the existing story-to-shot-plan path:

```text
story -> scene breakdown -> human-accepted option -> creative decision revision
      -> canon snapshot -> production-canon binding -> shot-plan draft
```

Suppose a scene already has an accepted decision revision `d1`, canon snapshot
`c1`, and immutable production binding `b1`. A later accepted human review
changes the scene action, producing `d2`, `c2`, and a candidate binding request
for the next shot-plan draft. The repository change also has fresh exact-change
validation and CI evidence. The assessment reconstructs both decision/canon
chains and the prior binding. It must return
`affected_reassessment_required` plus `additional_assurance_required`; the old
binding remains historical evidence and the assessment flags its required
reassessment before a human uses it for the next shot-plan step. The inert result
does not enforce or execute that boundary.

For an unchanged `d1`/`c1` subject, the same path can return `unaffected` when
the complete registered dependency set is identical and repository assurance
is fresh. That avoids repeating human option review or rebinding solely because
an unrelated, already-classified repository change occurred. It never skips
the validation profiles or human/security gates required for that repository
change.

Today `scripts/vss-agent impact` selects path/domain validation obligations;
the milestone controller binds validation, reviews, and CI to exact repository
identity; and `assess_production_binding_impact` reconstructs one immutable
production dependency chain. Each component is deterministic, but no existing
contract consumes their authoritative outputs together for the exact next
shot-plan action, proves that no applicable obligation was omitted, and emits
one joint fitness/impact result. A caller or reviewer must currently join those
separate results manually and can overlook a stale or missing dimension. V1
adds only that bounded composition seam.

## Reused contracts and bounded coverage proof

Reuse `config/agent-harness-v2.json` plus `scripts/vss-agent` for changed-path
classification, risk, fixed profiles, and evidence; `src/vss_dev/milestone.py`
for exact source identity, mission/review state, validation freshness, and CI;
the exact task/result registry and closed schemas in
`src/vss_resource_contracts`; `src/vss_movie_canon/service.py` for
`assess_production_binding_impact`; and
`src/vss_resource_admission/service.py` for
`reassess_storyboard_visual_reference_rights`. These components remain the
authorities for their facts and do not acquire execution authority.

V1 adds a **finite assurance coverage table to the existing harness-v2 impact
map**, not a graph/database or generic registry. Each supported exact/prefix
path rule gains a closed, sorted list of obligation IDs from this enum:
`repo.impact_union`, `milestone.validation`, `mission.alignment`,
`mission.review_receipts`, `ci.exact_head`, `resource.canon_decisions`,
`resource.rights_eligibility`, `schema.consumer_closure`,
`dependency.subject_enumeration`, `security.l3_review`,
`policy.controller_self_change`, and
`workflow.exact_ci`. Each ID resolves to one exact existing validation profile,
review mechanism, or registered task/result evaluator/version. The table is
bounded (at most 64 path rules, 16 obligation IDs per rule, and 8 supported
operation contracts); nested objects are closed and `additionalProperties` is
false. It has no transitive traversal or caller-defined rules.

For the first slice, coverage rows attach `resource.canon_decisions` to the
existing movie demo, scene-breakdown, option-review, canon, and shot-plan
source/test/contract rules; attach `resource.rights_eligibility` to the
resource-admission and rights-bearing storyboard-reference rules; attach
`schema.consumer_closure` to registered contract/schema rules;
`policy.controller_self_change` to controller, harness, map, and validation
policy rules; `workflow.exact_ci` to CI/workflow rules; and
`security.l3_review` to security-sensitive rules. Every row also carries the
baseline repository impact, milestone validation, and mission-alignment IDs.
The coverage table reuses each harness rule's exact `pattern`; it does not
maintain a second path matcher.

Each row also has one closed `effect_scope`: `exact_registered_subject` or
`all_affected_subjects`. It is part of the trusted table, never request data.
The exact-subject value is permitted only when the registered task/result
schema binds the exact scene/resource and its complete direct dependency set.
Code, schema, policy, or shared-operation changes whose accepted coverage row
is `all_affected_subjects` require `dependency.subject_enumeration` from an
existing authoritative enumerator. If no enumerator exists or it cannot prove
the full bounded set, return `incomplete_fail_closed`; a caller-provided list
of a few subject IDs cannot stand in for completeness. V1 supports the exact
scene shot-plan request only. It makes no `unaffected` claim for every
historical scene after a shared implementation change.

Completeness is established for one requested operation, not asserted by the
caller:

1. Reconstruct the full exact changed-path set and governed change identity
   from Git/controller evidence. Union every matching harness rule and every
   obligation ID. Any unclassified path or rule without coverage is
   `incomplete_fail_closed`.
2. Derive the production operation from the validated task/result contract
   identity and exact task/result compatibility registry. Derive repository
   assurance obligations independently from changed paths, pinned policy, and
   controller mission/validation/CI state. There is no caller `impact_scope`,
   free-form intended action, or optional obligation list. The assessed task is
   the exact registered request already being evaluated, not a selector in the
   assessment input. A missing, unsupported, or contradictory operation
   mapping is `incomplete_fail_closed`.
3. Resolve every obligation from the pinned base-version table and the exact
   contract registry. The table must cover every rule in the supported
   domains; an architecture test checks this closure. A candidate change to
   the table/map cannot validate itself under weaker candidate rules.
4. For the shot-plan operation, the registered production-binding contract
   defines the complete dependency set for that exact scene subject: exact
   canon snapshot and every required creative decision in its closed,
   bounded schema. The existing evaluator reconstructs all upstream
   artifacts and scope. A caller may supply binding/scene/artifact identifiers
   and evidence, but cannot omit a schema-required decision or choose fewer
   dependency kinds.
5. Where the exact task/result chain contains a rights-bearing reusable
   storyboard reference, the registered rights contract requires the complete
   source artifact, admission, asset, resolution request/result, and candidate
   rights chain; `reassess_storyboard_visual_reference_rights` validates it.
   If an operation can affect more subjects than the exact registered request
   can enumerate, or a required contract/evaluator is absent, coverage is
   incomplete. V1 does not claim portfolio-wide impact or infer unlisted
   dependents.

The caller supplies only evidence references and subject identifiers for the
real operation under assessment; the evaluator resolves and validates the
registered task/result identity and subject from those authorities. The
contract derives the mandatory dependency set and authority class; the
controller and path map separately derive repository-work obligations. A
different task is a different real request, not a narrower scope for the same
request. This bounded subject model does not become a generalized dependency
graph.

## Authority-sensitive obligation rules

The finite obligation table adds mandatory requirements; it never removes a
harness profile or controller gate.

| Change or operation class | Minimum derived obligations |
| --- | --- |
| Rights-bearing resource, rights policy/schema, or reuse/promotion action | Exact registered rights chain and rights reassessment; required human rights review. Unknown rights applicability or missing evaluator is incomplete and cannot be fit/unaffected. |
| Canon, creative-decision, or product-authority action | Reconstruct exact decision/canon lineage; require the active mission's Strategic, Constitutional, and UNKNOWN_UNKNOWN reviews where declared. `unknown`, `conflicting`, `CHALLENGE`, or unresolved authority alignment is incomplete and cannot produce either `fit` or `unaffected`. |
| Security code/policy, secrets, or security-classified impact | At least existing L3/security profiles and applicable security/human review. Never classify from changed candidate policy alone. |
| Controller, harness map, coverage table, schema, contract registry, or validation policy | Compare pinned base and candidate identities; require base-policy interpretation, all matched consumer/architecture/security profiles, at least L3, fresh exact-HEAD CI, and independent applicable review. No self-waiver or self-downgrade. |
| CI/workflow definition or workflow activation policy | Pinned workflow path/blob and complete required exact-HEAD pull-request CI observation; L3 and applicable human/security review. This assessment never activates a workflow. |
| Unknown path, unsupported contract/action, incomplete rights or dependency chain | `incomplete_fail_closed`; no inferred unaffected result. |

`authority_alignment` must be exactly `aligned` for `fit` or `unaffected`.
Mission decisions and review receipts are read from the current controller
assessment, bound by its exact assessment digest. A new assessment invalidates
old receipts. Review acceptance remains evidence and grants no production,
product/canon, Runtime, provider, merge, or publication authority.

## Proposed request/result and classifications

The strict `vss.assurance-assessment-request/1` contains exact repository/base/
HEAD/change identity; the full changed paths and existing harness plan; pinned
base/candidate policy, map, schema, and registry digests; a validated
task/result identity and exact subject identifiers; milestone validation,
review, and CI evidence; and all dependency/rights artifacts required by the
derived finite coverage table. It contains no caller-selected scope, risk,
profile subset, review set, dependency subset, or authority claim.

The strict `vss.assurance-assessment-result/1` contains the request digest,
reconstructed source identity, derived coverage IDs, sorted reason codes,
bounded evidence references, `assurance_fitness` and `change_impact`:

- `assurance_fitness`: `fit`, `additional_assurance_required`, or
  `incomplete_fail_closed`;
- `change_impact`: `unaffected`, `affected_reassessment_required`,
  `not_applicable_by_registered_contract`, or `incomplete_fail_closed`.

`fit` means all obligations for this exact registered action are complete and
fresh. A changed exact dependency requires reassessment and cannot be `fit` for
an action that consumes the prior binding. `not_applicable_by_registered_contract`
is allowed only when the authoritative operation contract explicitly has no
production dependency; it is never an inference from missing input. Any
unknown/unresolved authority alignment, unclassified impact, stale identity,
missing evidence, unsupported authority transition, or incomplete coverage
forces `incomplete_fail_closed` for both dimensions.

Reason codes are closed. Assurance codes: `exact_identity_and_required_evidence_fresh`,
`assurance_obligation_missing`, `validation_level_insufficient`,
`review_required`, `ci_required`, `evidence_stale`, `unknown_path`,
`coverage_rule_missing`, `identity_conflict`, `policy_or_controller_change`,
`authority_alignment_unresolved`, `unsupported_authority_transition`,
`evidence_incomplete`. Dependency/rights codes reuse exact registered
evaluator results, including `exact_dependencies_unchanged`,
`selected_dependency_changed`, `scope_mismatch`,
`dependency_identity_ambiguous`, `authoritative_chain_incomplete`,
`candidate_rights_unknown`, and `candidate_rights_conflicting`.

## Freshness, monotonicity, determinism, and limits

Source identity is reconstructed from exact repository/base/HEAD and controller
change identity plus residue provenance. Validation binds the same change
identity, map digest, and residue provenance. CI binds exact HEAD, branch,
pinned workflow blob, pull-request event, and complete required jobs. Review
receipts bind the current mission assessment event. Dependency and rights
results are rebuilt from authoritative upstream content; caller digests are
never accepted as substitutes.

Required validation is the union of every matching harness rule and the maximum
of their L0-L3 levels; all profiles remain. Existing controller, human,
security, and authority gates are additive. L3 remains mandatory for merge
readiness. Historical evidence is immutable; affected results create new
reassessment obligations only.

Canonical sorted inputs produce identical semantic output. Timestamps, UUIDs,
randomness, file-system paths, unordered iteration, and mutable `latest` values
do not affect classification. Schemas are closed and digests are reconstructed.
V1 is an inert local transformation: no Runtime/provider imports or calls,
external execution, automatic tests/CI, remediation, regeneration, scheduling,
publication, workflow activation, merge, or push. All controller authority
fields remain constant false.

## Adversarial coverage and first executable slice

After design approval, the first implementation may cover only the registered
story-to-shot-plan scene operation above. Tests must exercise the real path
from story/demo preparation through human option review, decision revision,
canon snapshot, production binding, and shot-plan input, then cover unchanged
and changed exact dependency cases. Adversarial cases include base/HEAD/change
identity drift; stale or wrong-SHA validation/CI/review; unknown paths; missing
coverage rows; caller scope/profile/action substitution; extra/missing
dependency fields; validly resealed alternate upstream artifacts; unknown or
conflicting rights; candidate self-change to map/schema/policy/controller/
workflow/security; unresolved mission alignment; malicious inert text; and
deterministic replay. Tests also prove every supported harness path rule maps
to a closed obligation set and that unsupported/multi-subject impact fails
closed.

No migration is needed: prior artifacts and evidence stay immutable, and the
new result is additive. The finite coverage table is the smallest new contract
because existing harness impact rules do not identify obligation families,
while existing artifact evaluators already provide the exact bounded
dependency reconstruction. No graph, database, scheduler, approval system, or
parallel workflow framework is introduced.
