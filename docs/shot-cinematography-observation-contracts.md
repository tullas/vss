# Shot Cinematography Observation v1

`shot_cinematography_observation/1` is an inert Movie-domain artifact for a
manually supplied or synthetic description of directly observable properties
of one identified shot and one evidence reference. It preserves exact project,
scene, shot, observer, method, provenance, classification, purpose, and content
integrity bindings.

Every attribute explicitly states `observed`, `uncertain`, `unknown`,
`not_observed`, or `not_applicable`. Only `observed` and `uncertain` carry a
value. Missing values are never inferred, numeric confidence is not used, and
the closed vocabulary cannot be extended with arbitrary strings.

Observation is not truth. This contract performs no image or video analysis,
decoding, model inference, recommendation, creative-intent interpretation, or
runtime execution. It establishes no emotion, audience effect, quality,
symbolism, narrative intent, or psychological meaning. It does not promote an
Observation to a Pattern, Lesson, or Admitted Knowledge item and grants no
authority. Automated and model-derived observation, external-source rights
workflows, and persistent evidence storage remain deferred.
