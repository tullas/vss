# Historical Improvement Backlog Recovery

Status: completed bounded archaeology; advisory only. Review receipt:
`docs/reviews/historical-improvement-backlog-recovery-strategic-review.md`.

## Scope and method

This report reconciles the historical leads supplied for this milestone with
the current `docs/engineering/improvement-backlog-v1.json` (15 candidates),
the DEV-WF-1/2/3 mechanisms documented in `docs/agent-coordination.md`, the
active decisions in `docs/architecture/decisions/index.json`, the ADR and
milestone history, the agent-coordination record, and the current `vss movie
demo` path. Historical evidence was treated as provenance, not as approval.

No M11 evidence, provider, media, video, paid, Runtime, production,
publication, deployment, canon, or workflow state was changed.

## Historical dispositions

| Historical theme | Disposition | Current reconciliation |
| --- | --- | --- |
| GitHub/repository as authoritative inter-agent communication bus | already-implemented | DEV-WF checkpoints, exact-HEAD CI observations, issue/PR audit mirrors, and reset-session packets exist. GitHub remains coordination evidence, not execution authority. |
| Reduce/eliminate human ChatGPT↔Codex relay | duplicate-of-existing-candidate | The execution-packet, checkpoint, and reset-session mechanisms reduce repeated relay; remaining friction is represented by `improvement-f13fed2accb693747a5a5812` and related handoff candidates. No second candidate admitted. |
| Delegated-agent resource/spend envelopes | strategic-review-only | ADR-0001 preserves this as a future requirement for any delegated work. It is not current authority, and this report does not turn it into an implementation requirement. |
| Controlled media storage outside Git with hashes/provenance in Git | partially-implemented | Heavy-data separation, local quarantine, exact digests, lineage, and provenance views exist; a general durable media store and external anchoring do not. The gap crosses storage/rights/production boundaries and is not admitted under the v1 candidate contract. |
| Eventual governed object-storage backend | strategic-review-only | ADR-0027 and local-first decisions preserve a future storage evolution path. No scale or recovery evidence justifies selecting a backend in this milestone. |
| Provider reachability/preflight and host execution boundaries | already-implemented | M11 admission, zero-call readiness/preflight, immediate reservation boundary, and explicit host handoff scripts enforce the current boundary. No provider or host execution occurred here. |
| Reusable character/world/location asset consistency | partially-implemented | Character continuity and storyboard reusable-asset admission/catalogue/lineage cover bounded character and visual-reference use. General cross-production world/location consistency is not implemented, but no compatible, evidence-backed v1 observation exists. |
| Production-package automation | strategic-review-only | Production packaging remains outside the current Film #1 review ladder and would require explicit production, rights, artifact, and authority decisions. It is not a current engineering candidate. |
| Reusable digital asset lifecycle | partially-implemented | Scoped immutable resource admission, asset cataloguing, revocation/revalidation, provenance, and explicit non-promotion limits exist. A generalized lifecycle is not implemented and is not admitted. |
| Rights/licensing/provenance readiness | already-implemented | Rights are first-class in the Constitution and active contracts; provenance, eligibility reassessment, source lineage, and limitations are implemented. Legal licensing adjudication remains out of scope. |
| Story → screenplay → storyboard → image → moving shot → dialogue/audio → edited scene → rough film → finished POC | partially-implemented | The current executable path covers story → scene breakdown → options → human review → accepted decision → shot-plan draft → storyboard specification → local SVG/PNG review candidates. Screenplay parsing, moving shot, audio, editing, rough film, and finished POC are not current capabilities; M11 remains the next product direction. |
| Multi-agent story/film production orchestration | strategic-review-only | Historical ambition only. Active decisions reject a generalized agent framework, governor, autonomous scheduling, and production authority. |
| Master-agent coordination of specialist creative agents | strategic-review-only | Historical ambition only. DEV-WF coordination is repository development handoff, not creative-agent orchestration or production control. |
| Consistent character/reference assets passed between generation stages | duplicate-of-existing-candidate | The implemented character-continuity and storyboard asset boundaries cover the bounded form; broader lifecycle concerns are captured by the partial asset themes above and existing handoff/context candidates. No duplicate admitted. |
| VSS as a licensable AI studio/platform | strategic-review-only | Long-range business/platform ambition. It is not authorized by DEC-0001/DEC-0002 and creates no present product or engineering requirement. |

## Candidate reconciliation

The 15 existing candidates remain the sole admitted backlog records. This
recovery admits zero new candidates. The historical themes do not have a
matching DEV-WF observation in the append-only milestone history, and the v1
contract has no compatible product/storage/rights category. Creating a
synthetic observation or broadening the schema here would defeat the
controller's exact-observation and architecture-review boundaries.

Existing candidates enriched: none. Candidate IDs are deterministic over the
complete candidate body, including evidence; adding this report as evidence
would change those IDs and therefore be a replacement rather than provenance
enrichment. The report itself preserves the historical relationship without
mutating the sealed v1 records.

No `related_to`, `depends_on`, or `supersedes` fields are added. The current
relationships are understandable from the report and existing candidate
source/evidence fields; an actual future need for machine-consumed
relationships would require a separate architecture review.

## Counts and limitations

| Disposition | Count |
| --- | ---: |
| already-implemented | 3 |
| partially-implemented | 4 |
| duplicate-of-existing-candidate | 2 |
| superseded | 0 |
| rejected/incompatible | 0 |
| strategic-review-only | 6 |
| surviving-backlog-candidate | 0 |

The supplied themes are historical leads, not a complete repository-wide
history. This bounded report records the full supplied set and the inspected
authoritative records; it does not claim legal, provider, quality, cost, or
production feasibility.
