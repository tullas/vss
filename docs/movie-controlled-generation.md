# Controlled external storyboard review frame

M10.0 adds one development-only operation,
`generate_one_controlled_storyboard_review_frame/1`. Its version-2 generic request and
candidate contracts extend the real movie
demo artifacts through an exact Runtime/provider boundary and admits at most one
external PNG as quarantined local review media.

Version 3 adds an optional domain-neutral production visual-grounding route. It
does not change version-2 behavior. The grounded route requires all six additional
artifacts together: a `production_visual_grounding_profile/1`, grounded creative
decision and canon artifacts, and grounded shot-plan and storyboard overlays.
Partial grounding input is rejected. See
[Domain-neutral production visual grounding](movie-visual-grounding.md).

The ordinary `vss movie demo` command remains non-paid. The separate command is:

```text
vss movie controlled-review-frame --preflight ...
vss movie controlled-review-frame --approve --recorded-by <accountability-id> ...
vss movie controlled-review-frame --generate --approval <approval.json> ...
```

Every form requires the story, review decision and packet, option set, scene
breakdown, creative decision revision, canon snapshot, production canon binding,
shot-plan draft, storyboard specification, and exact frame ID. The service
reconstructs the story breakdown and canon artifacts rather than trusting
caller-supplied seals. Only public, approved-fixture story input declared
`original` or `explicitly_authorized` is eligible in this bounded slice.

Preflight reconstructs the request and checks exact registration, output state,
credential presence by environment-variable name, direct egress, DNS, and the
pinned price profile. It reads no secret value, reserves no attempt, writes no
artifact, and calls no provider. Approval is a separate short-lived HMAC-SHA256
credential action. Its `recorded_by` field is accountability metadata, not proof
of human identity. Runtime verifies the exact request/provider/model/cost binding,
current key epoch, expiry, kill switches, and create-once state.

The only external profile is provider `movie.storyboard-image.openai` version
`1.1.0`, implementation `vss.openai-gpt-image-2-opaque-cabx`, model snapshot
`gpt-image-2-2026-04-21`, and `POST /v1/images/generations`. It requests one
1280×720 medium opaque PNG with standard moderation and no streaming, retry,
redirect, proxy, fallback, image input, alternate model, or second candidate.
The approval and reservation ceiling is USD 0.10 under the pinned
`openai-gpt-image-2-standard-2026-08-24/1` profile. This is a pre-call bound,
not provider-side atomic billing enforcement.

Runtime creates `.local/movie/m10-0-controlled-review-frame/<request-digest>/`
with a create-once `attempt.json`. After strict untrusted-response and PNG
validation, it stages `image.png`, `review.json`, and
`generated-review-candidate.json`. Runtime audit is written before publication,
and the candidate JSON remains the admission commit point. A separate sealed
`attempt-outcome.json` records the terminal admitted, rejected, provider-failed,
or ambiguous state with bounded sanitized evidence. A failed or ambiguous
post-reservation attempt is consumed and never retried. Bytes without the
candidate admission record are inert.

The bounded PNG profile permits either no Content Credentials metadata or one
non-empty `caBX` chunk before `IDAT`, at most 4 MiB within the existing 10-MiB
image ceiling. Runtime reconstructs the chunk count, length, and opaque-payload
digest from the returned bytes and preserves the complete PNG unchanged. It
does not parse JUMBF/C2PA claims or verify signatures. Presence is recorded as
opaque, unparsed, unverified, externally supplied metadata and grants no VSS
identity, rights, ownership, trust, approval, or execution authority. A future
verifier requires a separately governed contract version.

The candidate is disposable development review media. It grants no production,
asset, publication, export, scheduling, workflow, provider, or further Runtime
authority. Pixel reproduction is not promised; the record preserves exact input,
provider, response, usage, content, and policy identities by digest and bounded
metadata. This milestone creates an empty review record but does not implement
review disposition recording; a later operation may seal `USE`, `REGENERATE`,
or `REJECT`, and that disposition must not authorize another provider call.

The request also seals exact capability/provider manifest and implementation
digests. Runtime revalidates those bindings before preflight, approval
verification, secret access, reservation, or transport.

Durable retention, deletion/legal hold, customer export, catalogs, databases,
queues, multi-candidate runs, reusable-asset admission, promotion, production
rights adjudication, general RBAC, commercial ledgers, and production-grade
identity or process isolation remain deferred.
