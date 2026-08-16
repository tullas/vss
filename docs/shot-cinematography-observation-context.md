# M6.2 Shot Observation Set and Context

`shot_cinematography_observation_set/1` is an immutable, exact collection of
two through eight independently validated
`shot_cinematography_observation/1` artifacts. One set has one project, one
scene, and one classification. Observation and shot identities are unique.
Entries bind the exact observation identity, version, content digest, and shot
identity.

The set is unordered. Sorting by observation identity is canonical
representation only; it establishes no shot, edit, capture, or narrative
chronology. Eight observations fit the repository's existing Context item and
canonical-node bounds. The bound also limits any future, separately admitted
pairwise analysis to at most 28 comparisons; M6.2 performs none.

`shot_cinematography_context/1` is a deterministic immutable projection for the
exact non-authorizing purpose `shot_cinematography_local_analysis`. Assembly
revalidates every raw observation and the exact set bindings, then preserves
attributes, qualification states, evidence-reference identity, manual or
synthetic provenance, and limitations. Mixed projects, scenes, or
classifications fail closed; no classification combination or downgrade rule
is invented.

Observation remains non-truth. Context is not a Knowledge store, and Context
Assembly is not synchronization, reasoning, recommendation, promotion, or
execution. The Context contains no raw media, Runtime capability, registry,
provider, path, callback, external URL, Pattern, Lesson, or Admitted Knowledge
artifact. Automated observation and future deterministic Pattern analysis
remain deferred and require separate contracts and admission.
