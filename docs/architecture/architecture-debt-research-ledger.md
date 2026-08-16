# Architecture Debt and Research Ledger

## Purpose

This small ledger holds evidenced pressure and research questions until their
decision trigger exists. An entry is not an ADR, roadmap commitment, feature
authorization, or permission to introduce a dependency. It prevents an
interesting idea from becoming architecture merely through repetition.

Allowed types are `ARCHITECTURE_PRESSURE`, `RESEARCH_THEME`,
`FRAMEWORK_CANDIDATE`, `RETIREMENT_CANDIDATE`, `TECHNOLOGY_EXPERIMENT`, and
`MISSION_RISK`. Allowed statuses are `OBSERVE`, `RESEARCH`,
`WAIT_FOR_EVIDENCE`, `READY_FOR_DECISION`, `RESOLVED`, and `RETIRED`.

## Current entries

| ID | Title | Type | Status | Evidence | Current consequence | Trigger for reconsideration | Owner domain | Decision date/checkpoint |
|---|---|---|---|---|---|---|---|---|
| ADRL-001 | ReasoningGateway lifecycle and size pressure | `ARCHITECTURE_PRESSURE` | `OBSERVE` | M5 checkpoint found a sound semantic-only Gateway with growing validation/audit adapter repetition | Maintain explicit bounded adapters; no refactor solely for line count | Another independent domain materially duplicates lifecycle, adapter code outweighs generic lifecycle, inconsistent gates emerge, or domain rules enter Gateway | Semantic Reasoning | 2026-08-09 / M5 checkpoint |
| ADRL-002 | Semantic evidence-binding pattern | `FRAMEWORK_CANDIDATE` | `WAIT_FOR_EVIDENCE` | M5.3 and M6.2 now repeat independent evidence validation → exact Context projection; M6.2 ends before provider/result binding and does not yet demonstrate safely removable domain-independent duplication | Document the pattern; keep semantics domain-owned; do not promote the candidate | A further independent domain repeats the full stable lifecycle or measured maintenance evidence isolates removable mechanics without erasing domain validation | Context / Semantic contracts | 2026-08-16 / M6.2 implementation evidence |
| ADRL-003 | Architecture Intelligence | `RESEARCH_THEME` | `RESEARCH` | Evidence matrix, dependency tests, entropy categories, and acceptance history could support better architecture insight | Research may improve review evidence; it gains no authority and creates no service commitment | A bounded research question and repository evidence set can be evaluated without affecting authoritative decisions | Architecture Governance | 2026-08-09 / simplicity-governance baseline |
| ADRL-004 | Probabilistic confidence and calibration | `ARCHITECTURE_PRESSURE` | `READY_FOR_DECISION` | Current contracts qualify confidence but do not define calibration, abstention, model comparability, or deterministic/probabilistic coexistence | Blocks probabilistic Cinematic Observation implementation, not its ADR | Cinematic Observation / Film Learning ADR | Future Cinematic Observation | 2026-08-09 / M5 checkpoint |
| ADRL-005 | External source rights and withdrawal | `MISSION_RISK` | `READY_FOR_DECISION` | Existing provenance/revocation primitives do not establish analytical rights, derivative retention, withdrawal, or influence policy | No persistent external reference analysis before fail-closed eligibility architecture | Cinematic Observation / Film Learning ADR before source ingestion | Knowledge / Source Governance | 2026-08-09 / M5 checkpoint |
| ADRL-006 | Plan IR timing | `ARCHITECTURE_PRESSURE` | `WAIT_FOR_EVIDENCE` | M4/M5 contain inert options and semantic transitions but no executable graph, scheduling, retries, compensation, recovery, or durable state | Do not introduce Plan IR | Repeated implemented orchestration semantics after a future domain, before effectful Compute if evidence exists | Future Planning / Runtime Governance | 2026-08-09 / M5 checkpoint |
| ADRL-007 | Cross-language semantic conformance | `ARCHITECTURE_PRESSURE` | `WAIT_FOR_EVIDENCE` | ADR-0013, ADR-0018, and ADR-0023 require implementation-neutral boundaries and Python remains the current semantic/control default, but no equivalent Rust/native implementation has proven canonical cross-language semantic equivalence | No rewrite or interoperability framework; preserve implementation-neutral contracts | First Rust/native replacement or concurrent authoritative implementation of an existing semantic component | Architecture / Contract Governance | 2026-08-09 / ADR-0024 proposal |
| ADRL-008 | Knowledge promotion and semantic evolution lifecycle | `ARCHITECTURE_PRESSURE` | `RESOLVED` | ADR-0015 defines typed/versioned Knowledge Items, lifecycle, and provenance but did not distinguish Observation, Pattern, Lesson, Admitted Knowledge promotion, representation migration, evidence-state change, and semantic evolution | Accepted ADR-0024 defines explicit domain-owned, non-authorizing promotion and distinguishes representation, evidence/provenance state, confidence/calibration state, and semantic evolution without creating a service | Reopen only if implementation evidence shows the roles cannot be represented through ADR-0015 typed families or require a conflicting authority or lifecycle model | Knowledge / Cinematic Observation | 2026-08-15 / ADR-0024 acceptance |

## Entry discipline

New entries require current evidence, a present consequence, and a concrete
reconsideration trigger. Duplicate questions are consolidated. Resolve or
retire entries when the question is decided or evidence invalidates it;
resolved/retired entries remain historical but leave the active decision
surface. The active ledger stays intentionally small and does not seed
speculative product lists. No archival system is implied.
