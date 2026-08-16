# Shot Cinematography Observation v1

`shot_cinematography_observation/1` is an inert Movie-domain artifact for a
manually supplied or synthetic description of directly observable properties
of one identified shot and one evidence reference. It preserves exact project,
scene, shot, observer, method, provenance, classification, purpose, and content
integrity bindings.

Every attribute explicitly states `observed`, `uncertain`, `unknown`,
`not_observed`, or `not_applicable`. Only `observed` and `uncertain` carry a
value. Missing values are never inferred, numeric confidence is not used, and
the closed vocabulary cannot be extended with arbitrary strings. `Uncertain`
means that the concrete value is the observer's supplied, qualified report; it
is not a probability, calibrated confidence, or less-authoritative truth claim.

Camera angle describes camera orientation relative to the subject; camera
elevation describes camera height. `Overhead` therefore exists only as an
elevation. Movement values describe camera motion, not support or stabilization
equipment. Composition is limited to directly describable placement. A facing
screen direction is admitted only for one explicitly observed subject. A focal
length value means only that millimetres were explicitly supplied; it is never
estimated from framing. A subject count of zero represents an explicitly
observed shot with no admitted subject, not a missing count.

Observation is not truth. This contract performs no image or video analysis,
decoding, model inference, recommendation, creative-intent interpretation, or
runtime execution. It establishes no emotion, audience effect, quality,
symbolism, narrative intent, or psychological meaning. It does not promote an
Observation to a Pattern, Lesson, or Admitted Knowledge item and grants no
authority. Automated and model-derived observation, external-source rights
workflows, and persistent evidence storage remain deferred.
