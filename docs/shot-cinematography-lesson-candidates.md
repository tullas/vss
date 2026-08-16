# M6.4 Deterministic Cinematic Lesson Candidates

M6.4 consumes one exact, independently revalidated
`shot_cinematography_pattern_set/1` and produces the inert
`shot_cinematography_lesson_candidate_set/1`. The executable task is
`derive_shot_cinematography_lesson_candidates/1`, with purpose
`shot_cinematography_local_lesson_candidate_derivation`.

A Lesson Candidate is a structured, evidence-backed proposition scoped only to
the exact source Context. `repeated_value` maps to
`recurrence_lesson_candidate`; `variation` maps to
`variation_lesson_candidate`. Each admitted source Pattern produces exactly one
candidate. No absent Pattern produces a candidate, and no cross-Pattern
synthesis occurs.

The structured proposition contains only the admitted attribute, exact values,
and occurrence count. It binds the source Pattern identity, Pattern digest,
supporting-evidence digest, Pattern Set digests, and source Context identity and
digests. It preserves these fixed limitations: exact Context scope,
observed-only source semantics, exclusion of uncertain and unavailable values,
no causal or evaluative interpretation, no recommendation, no generalization,
and no Admitted Knowledge status.

Lesson Candidate is not Truth, Recommendation, creative approval, execution
instruction, universal principle, or Admitted Knowledge. Frequency is not
confidence or authority. The local deterministic provider has no media, AI,
model, network, Runtime, or production effect. Dry-run validates and binds the
route but invokes zero providers. Any future Knowledge admission requires a
separate explicit architectural decision and milestone.
