# Creative Reality Check 1

This disposable development experiment compares the existing M8.2 projection for
`frame-55a9d7015fdf1f72571b74c5` with the same projection plus one fixed temporary
director brief. It is not M8.3 and introduces no reusable creative-context contract.

Before generation, one immutable six-slot plan is created with operating-system randomness,
exactly three condition A and three condition B slots, and six preassigned opaque candidate
labels. Each explicit invocation generates only the next unattempted planned candidate; the
caller cannot supply a condition or skip a slot. Attempt evidence is reserved before provider
access, so failed slots are not regenerated or replaced. Reinitialization reuses the exact valid
plan, while incomplete, malformed, or conflicting evidence fails closed. Random plan material
is non-semantic and does not enter the M8.2 or experimental semantic request identities.

The internal condition plan, attempt evidence, and reviewer plan are separated under
`.local/movie/creative-reality-check-1`. The reviewer plan contains only ordinal, opaque label,
image reference, and empty review fields; it contains no condition or prompt material. This is
development blinding by OS randomness and evidence separation, not cryptographic blinding.
Results
remain development review candidates with no production, selection, publication,
workflow, or autonomous authority.

The experimental provider is statically fixed to OpenAI's direct Images API at
`https://api.openai.com/v1/images/generations`, model snapshot
`gpt-image-2-2026-04-21`, PNG `1536x1024`, medium quality. Official documentation was
checked on 2026-08-23. The published medium-quality 1536×1024 image-output estimate is
US$0.041, plus text-input tokens. With the fixed prompts bounded at 3,006 UTF-8 bytes, the
experiment conservatively allows US$0.07 per call and US$0.42 for six calls, below the
user-approved US$2 ceiling.
Current pricing must still be checked before paid execution.

The key is read only from `VSS_EXPERIMENT_OPENAI_API_KEY` after Runtime authorizes the
experimental capability's exact provider, network, secrets, and filesystem permissions.
It is not an input, semantic projection, result, audit field, or evidence field. Canonical
tests inject a fake HTTPS transport and make no network calls.
The experimental transport denies every HTTP redirect before a second request can be constructed;
redirect responses receive a bounded `http_redirect` classification without retaining the
`Location` value. The credential is therefore sent only to the exact authorized OpenAI origin.

Failed external calls add only a bounded diagnostic envelope to the Runtime failure audit.
For HTTP failures it contains a response-present flag, status, closed classification, allowlisted
OpenAI error type/code, a fixed safe message, and a syntax-bounded `x-request-id` when available.
For failures without an HTTP response it contains only one of `dns`, `connect`, `tls`, `timeout`,
or `other_transport` plus a fixed safe message. Raw response bodies, provider messages, request
headers, credentials, request bodies, prompts, URLs, and arbitrary exception text are discarded.
Diagnostics grant no authority and add no retry or fallback behavior.

Successful HTTP responses retain the same safe boundary when later admission fails. Closed stages
distinguish response size, JSON/schema, image payload, base64, decoded-media size, PNG conformance,
and provider-result failures. Evidence is limited to HTTP status/response presence, safe request ID,
encoded and decoded byte counts, decoded SHA-256, and a payload-free PNG summary containing bounded
header values, allowlisted chunk names, and a closed rejection reason. Image/base64 content is never
failure evidence. Documented `revised_prompt` and `url` image-item fields are bounded and ignored;
`b64_json` remains required.

PNG diagnostics retain an encountered chunk type only when its exact four bytes form a conforming
ASCII alphabetic PNG type with the reserved third letter uppercase. Otherwise the type is recorded
as the fixed token `malformed`. Chunk payloads—including textual and color-profile contents—are
never inspected or retained by diagnostics. This observation rule does not broaden PNG acceptance.

Real GPT Image 2 evidence established that provider PNGs can carry a `caBX` chunk. The experimental
external-provider profile therefore accepts exactly one non-empty, CRC-valid `caBX` immediately
after `IHDR` and before the first `IDAT`, with an experimental 4 MiB chunk-data ceiling. Every other
previously disallowed chunk remains disallowed, and the M8.2 local PNG profile is unchanged. The
provider-returned PNG is preserved byte-for-byte, so its media SHA-256 covers the `caBX` chunk.
VSS records only presence and bounded chunk length; it does not separately retain or interpret the
payload. VSS preserves provider-returned Content Credentials metadata; its C2PA claims were not
cryptographically verified. The metadata grants no production, publication, asset-admission, provider,
review-decision, selection, workflow, or autonomous authority.

The 10 MiB decoded PNG limit is unchanged. Its HTTP response limit is derived as
`ceil(10 MiB / 3) * 4 + 64 KiB`: base64 expansion plus a fixed bounded JSON-envelope margin.

The accompanying multilingual probe demonstrates exact Unicode transport through the
applicable M4–M8 path and safe XML escaping. It also records existing limitations rather
than changing contracts: story language is fixed to `en`, canonical digests do not
normalize NFC/NFD, source spans currently use Python Unicode code-point offsets without a
declared contract unit, English semantic rules remain incomplete for other languages, and
SVG layout has no deliberate bidi presentation policy.

## Closure record

Generation is permanently closed. Exactly six planned real calls were attempted: five failed
and one succeeded. No retry or replacement candidate was used, and no further paid CRC1
execution is authorized. The comparison is operationally and statistically inconclusive.

The first failure exposed unrestricted diagnostic information loss. The second was a bounded
HTTP 400 `billing_hard_limit_reached` response and established the account-billing prerequisite.
The third exposed a separate successful-response blind spot: an HTTP 200 could fail after the
provider boundary without a retained closed stage. The resulting post-HTTP diagnostics now retain
only bounded counts, digests, structural PNG facts, and closed classifications. The original
12 MiB encoded-response ceiling also failed to account correctly for base64 expansion of the
10 MiB decoded-media ceiling; it was replaced by the bounded derivation documented above.

The fourth and fifth calls received technically conforming 1536×1024, 8-bit RGB provider PNGs
that were rejected because an ancillary chunk was initially unknown and then identified as
`caBX`. This established the narrow experimental compatibility rule above. VSS interprets `caBX`
only as opaque C2PA Content Credentials metadata, preserves the original provider bytes, and does
not separately persist or interpret its payload. C2PA claims were NOT cryptographically verified
and grant no authority.

The sole successful candidate was `candidate-7f90a4221c9f01d2`: 1536×1024, 2,106,398 bytes,
SHA-256 `3e43d23edb30cbdda9f8a2e8e70268adf217e4175d763f295c8896b4b84da163`, provider latency
37,426 ms, and Runtime duration 37,828 ms. Sanitized usage was 325 input tokens, 1,372 output
tokens, and 1,697 total tokens. Its preserved `caBX` payload length was 21,824 bytes; its claims
were not verified.

The human review remained blinded until analysis was complete. It recorded disposition
`REGENERATE`, narrative fidelity `PARTIAL`, cinematic usefulness `LOW`, visual quality `GOOD`,
unsupported factual invention `LOW`, and creative interpretation `TOO CONSERVATIVE`. Only after
that review was the candidate revealed as Condition A. Because five candidates failed and only
one survived, no conclusion can be drawn about A versus B.

The image demonstrated that semantic correctness and technical conformance do not imply cinematic
usefulness. Control-plane material was rendered into the depiction, the known relationship among
Mira, the lantern, and the locked gate was weakened during projection, and `UNKNOWN` was conflated
with conservative or neutral depiction. Future semantics need to distinguish an unknown canonical
fact, deliberate ambiguity, a permissible candidate-only creative choice, required visual
neutrality, omission, and a production unknown.

The recommended next correction is a narrow depiction-only projection with bounded candidate-only
creative freedom. No new permanent Creative Authority subsystem is justified, and M8.3 should
change scope accordingly. This experiment does not implement that correction or authorize another
generation.

OpenAI references: [image generation](https://developers.openai.com/api/docs/guides/image-generation),
[GPT Image 2](https://developers.openai.com/api/docs/models/gpt-image-2),
[pricing](https://developers.openai.com/api/docs/pricing), and
[API data controls](https://developers.openai.com/api/docs/guides/your-data). The `caBX` placement
rule follows the [C2PA PNG embedding specification](https://spec.c2pa.org/specifications/specifications/2.1/specs/C2PA_Specification.html#_embedding_manifests_into_png)
and the [PNG chunk structure rules](https://www.w3.org/TR/png-3/#5Chunk-layout).
