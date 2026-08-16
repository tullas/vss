# M6.3 Deterministic Cinematic Pattern Analysis

M6.3 analyzes one exact `shot_cinematography_context/1` through the executable
task `analyze_shot_cinematography_patterns/1` and returns one
`shot_cinematography_pattern_set/1`. The result is an inert, Context-scoped
description of explicit recurrence and variation. Pattern is not Truth,
Lesson, recommendation, approval, or Admitted Knowledge. Frequency is an
integer occurrence count, not confidence or authority.

The repository-owned catalogue
`vss.shot-cinematography.patterns.deterministic/1.0.0` admits exactly the eight
M6.1 attributes. A `repeated_value` requires at least two `observed` values.
A `variation` requires at least two distinct `observed` values. `uncertain`,
`unknown`, `not_observed`, and `not_applicable` remain exact evidence-bound
exclusions and never supply a value to either rule. Every summary identifies
the eligible population, every pattern binds its supporting observation IDs
through a canonical digest of their exact ID/content-digest/shot bindings, and
all excluded observations retain their qualification.

The catalogue scans attributes independently in bounded
O(observations × attributes) work over the M6.2 limit of eight observations.
Numeric attributes use exact JSON-number equality: no tolerance, bucketing,
range inference, or rounding is applied; integer-valued decimal spellings have
one canonical integer representation.
It performs no combinations, pairwise comparisons, chronology inference,
causal or emotional interpretation, quality judgment, prediction, or advice.
The local strategy invokes one deterministic provider; dry-run invokes none.
The Gateway validates exact task, Context, catalogue, invocation, and result
bindings but grants no Runtime or production authority.

Raw media, AI/CV/model inference, external learning, Lesson creation, Knowledge
promotion, and richer pattern reasoning remain deferred.
