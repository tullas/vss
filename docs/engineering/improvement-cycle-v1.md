# Consolidated VSS Engineering & Production Improvement Cycle

Status: implemented offline foundation; advisory and development-only. This
cycle does not authorize provider execution, production, publication, merge,
workflow activation, controller recovery, Attempt 6, or a new Film #1 shot.

## 1. Recovered inventory and disposition

The authoritative source remains `improvement-backlog-v1.json`; this report is
the consolidated disposition and acceptance overlay, not a second backlog.
There are 16 canonical queued candidates and 16 historical themes in the
bounded archaeology record. No new candidate was admitted.

| Disposition | Count | Canonical candidates / reason |
| --- | ---: | --- |
| DO_NOW | 1 | `improvement-c566e11af4dcc39957f64252`: repeatable adjacent-shot lifecycle, digital twin, identity, recovery, media admission, and KPIs |
| DO_SOON | 5 | `improvement-08110a72a0f8efb79a736c86`, `improvement-0967a667bd3f6efeaa459fe8`, `improvement-f13fed2accb693747a5a5812`, `improvement-14a9f8f5ac9563c0cff2cebb`, `improvement-724b76d03adca4ad81febe9c` |
| DEFER | 6 | `improvement-7da5507c74b3ed1bbcf28128`, `improvement-206d5d3efda036666042ecbe`, `improvement-1155a82f72a46b0259c1c97c`, `improvement-5864f4093adfa98ff99fd3b5`, `improvement-84486260fa77a617c59ef6ae`, `improvement-34a733ce16d3f476975324ea` |
| RETIRE_OR_MERGE | 4 | `improvement-69f29209589025c0ee56b232` merges into bounded handoff work; `improvement-67c3ce1ff4e6a0cdec8ccd83` remains controller-governance review; `improvement-19e542319bf5be3e07f29108` and `improvement-e7f7855249a556efdfb7ce99` are speculative analyst/governance work |

The source backlog's existing dispositions remain unchanged because its v1
contract intentionally records advisory queue state, not execution authority.
Dependencies are: identity binding before lifecycle admission; lifecycle
before digital-twin scenarios; digital twin before paid/provider admission;
KPI extraction after durable lifecycle evidence.

Acceptance is measurable: a new package reaches `creatively_reviewed` with one
submission; pre-acceptance failures report zero provider calls; accepted
operations preserve one operation name through recovery; malformed media never
reaches technical admission; all named scenarios run with no network call.

## 2. Systemic root-cause clusters

| Cluster | Evidence pattern | Existing backlog coverage |
| --- | --- | --- |
| Development-loop efficiency | repeated manual reconstruction and validation | handoff, context, validation, cache candidates |
| ChatGPT/Codex/GitHub handoff | durable packets exist but friction remains | `081...`, `096...`, `f13...` |
| Controller lifecycle/merge identity | merge SHA and execution identity were conflated | `67c...`; frozen M11 controller intentionally untouched |
| Semantic request identity | planning/authorization/execution drifted | prerequisite `c566...`; implemented in lifecycle |
| Execution namespace identity | adjacent execution namespace collision | prerequisite `c566...`; implemented in lifecycle |
| Authorization/provider acceptance | approval, reservation, and acceptance diverged | prerequisite `c566...`; existing Runtime ledger retained |
| Credential/readiness lifecycle | readiness was not immediate/reliable at boundary | prerequisite `c566...`; existing preflight retained |
| Provider persistence/recovery | accepted terminal result needed recovery | prerequisite `c566...`; same-operation invariant implemented |
| Media admission | terminal representation and local admission diverged | prerequisite `c566...`; scenario coverage implemented |
| Offline digital-twin fidelity | prior fake transports lacked one cross-stage corpus | prerequisite `c566...`; lifecycle twin implemented |
| Failure injection | failures were adapter-specific | prerequisite `c566...`; 13 scenario families covered |
| End-to-end production testing | component/CI success did not prove path readiness | prerequisite `c566...`; golden path implemented |
| Observability/diagnosis | evidence was scattered and diagnosis costly | `7da...`, `f13...`, `724...`; bounded recorder/KPIs implemented |
| Governance complexity/effectiveness | controls can add burden without reducing intervention | `14a...` and historical strategic-review themes; measured, not expanded |

Historical recommendations are reconciled in
`historical-improvement-backlog-recovery.md`: GitHub coordination, provider
preflight, rights/provenance, bounded asset admission, and current local
movie path were already implemented or partially implemented; speculative
object storage, generalized agents, delegated spend envelopes, and platform
business ambitions remain deferred.

## 3. Reusable production lifecycle

The offline state machine is:

`planned → rehearsed → authorized → execution_reserved →
provider_submission_attempted → provider_accepted → provider_processing →
provider_terminal → artifact_recovered → technically_admitted →
creatively_reviewed`

Human approval owns authorization; Runtime owns reservation and transport;
provider evidence owns acceptance, processing, and terminal state; Runtime
recovery owns artifact recovery; the media admission service owns technical
admission; human review owns creative disposition. An accepted operation is
never resubmitted: recovery is keyed by the deterministic operation name.
Pre-provider failures remain zero-call outcomes and cannot be confused with
provider acceptance.

## 4. Development loop and KPI mechanism

The durable unit is an approved-shot package plus bounded JSON flight
recorder. A compact result can be read by CLI/tests and reused by future
bootstrap/next-action reporting. Existing checkpoint, reset-session, CI, and
validation commands remain the handoff mechanism. This cycle adds no merge,
provider, spend, publication, or security authority.

`vss.production-development-kpis` derives source changes, interventions,
handoffs, unblock PRs, pre-provider failures, accepted submissions, recovery,
cost, and approved-shot-to-reviewable-video wall-clock time from lifecycle
results. Cost is zero for this rehearsal.

## 5. Completion boundary

The golden-path test proves a new adjacent-shot package is consumed without
shot-specific source changes and reaches the provider boundary/reviewable
state offline. It does not prove real-provider readiness, credential validity,
paid cost, controller recovery, or permission to resume production.

The lifecycle package now accepts the real admitted moving-shot request shape
for offline rehearsal, binding its authoritative request digest and
shot-specific namespace. The provider handler remains independently governed
by Runtime, its one-attempt ledger, and persisted provider evidence; this bridge
is an integration check, not a second execution path.
