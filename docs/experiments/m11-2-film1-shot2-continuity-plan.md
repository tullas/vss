# Film #1 Shot 2 continuity experiment plan

This is an offline package for exactly one adjacent Shot 2. The human creative
decision is `APPROVE` for the proposed beat. It does not invoke
Veo, reserve a paid attempt, create Attempt 6, or grant production authority.
The machine-readable package is
`m11-2-film1-shot2-continuity-plan.json`.

## Proposed Shot 2

Shot `shot-024b0d6352149eabb74df544` is the next shot in
`scene-91f5c8634519d8264e2dd5f8`: on the same dawn banyan-road axis,
Vikramaditya turns toward the already-present Vetala and takes one measured
step toward him. The riddle remains interrupted and unresolved. This is one
adjacent narrative beat, not a second scene or a new creative candidate set.

## Continuity contract

The accepted Attempt 5 artifact remains the Shot 1 review anchor:
`.local/recovery/attempt-5/attempt-5-recovered.mp4`, digest
`1008b512047b98451cf6b3760eb7b18d1909ed319474a24c103b4db2e6e0bda3`.
The later provider request uses the authoritative storyboard PNG digest
`4ff4ddc7ef42122d935ce5c1cfbe5bed68fd4e157789862a1597943eebcb02bb` as its
image input. It inherits the scene, dawn, banyan-road, character presence,
camera axis, screen direction, 16:9 framing, live-action grounding, and
restrained style. It must not introduce a character, location, prop, time
jump, magic, crowd, or control-plane text.

## Request and cost

The request is fixed to the existing moving-shot contract: Veo
`veo-3.1-generate-001`, `us-central1`, one 8-second 720p output, PNG input, and
audio disabled. The corrected estimate is `$1.600000` (8 × $0.20/billable
second); the hard ceiling is `$5.000000`, inherited from the existing bounded
moving-shot mechanism. Exactly one output video and one provider submission
are permitted only after separate authorization; there is no retry, fallback,
or fan-out. The rate still requires confirmation against the live quote before
execution.

The deterministic provider request digest remains
`c697e9c9455bc89cbb4a0ebb63075e3f7cefb496b6209aec9d107b26dffc1651`; pricing
is not a provider-request field. The package digest, which includes the
approved pricing evidence, is
`d41a309bd0c35bc5cba5d23568926181bc01361f2ae8ce49e41c11d8923eea9c`.

## Rehearsal

The focused rehearsal passed with zero provider calls, zero paid attempts, no
Runtime invocation, no credentials, no network transport, and no attempt-ledger
write. It only validates the package’s identity, source digests, continuity
constraints, cost bound, and deterministic request seal.

## Human decisions required before provider execution

1. The accountable owner must confirm the current Veo price, authorize one
   paid attempt at no more than `$5.000000`, and explicitly approve external
   provider processing of the selected reference.
2. The rights/production owner must confirm that the selected storyboard
   reference and Film #1 scope are eligible for that provider call; this plan
   itself makes no rights or production determination.
3. After a candidate exists, a human must record `USE`, `REGENERATE`, or
   `REJECT`; that decision is review evidence only and cannot authorize
   production, publication, or workflow activation.
