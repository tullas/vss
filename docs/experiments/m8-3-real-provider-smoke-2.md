# M8.3 one-image creative smoke validation

## Purpose and boundary

This disposable development experiment asks one question: does the unchanged M8.3
depiction-only projection produce a narratively useful cinematic image when consumed by a
real image generator? It binds the already-authoritative Mira detail frame to one provider,
one model snapshot, one request, and at most one returned image. There is no A/B plan,
selection, retry, fallback, regeneration, or replacement candidate. Any technical failure
ends generation without a creative conclusion. A successful generation also ends generation
and awaits immediate human review.

This code is experiment-specific and removable. It is not a mainline OpenAI provider, does
not change M8.2 media admission, and grants no production, asset, publication, workflow, or
autonomous authority.

## Fixed authoritative input

- Source: `Mira crosses a quiet courtyard at dawn and finds a lantern beside a locked gate.`
- M8.3 frame: `frame-55a9d7015fdf1f72571b74c5` (`detail_or_transition`, `close_detail`)
- Frame specification SHA-256: `019052d98e3db5862a8199993e29c5199b5df44c466aecda02f3128fa0867d7b`
- Unchanged M8.3 depiction projection SHA-256: `3aa69cfccff612188bfd8d5820be1e691891d583074aff1e5205be986ed4c554`

The public command accepts only the six upstream governed artifacts needed for authoritative
M8.3 reconstruction. Frame, provider, model, endpoint, output settings, and creative freedoms
are fixed internally and are not caller-selectable.

## Provider configuration and cost

Official OpenAI documentation checked on 2026-08-23 identifies `gpt-image-2` as the current
flagship image model, publishes snapshot `gpt-image-2-2026-04-21`, supports the Images API
generation endpoint, custom valid dimensions including `1280x720`, `medium` quality, and PNG
base64 output. The fixed request is:

- `POST https://api.openai.com/v1/images/generations`
- model `gpt-image-2-2026-04-21`
- size `1280x720`, quality `medium`, output format `png`, `n=1`

References: [model](https://developers.openai.com/api/docs/models/gpt-image-2),
[image generation guide](https://developers.openai.com/api/docs/guides/image-generation), and
[pricing](https://developers.openai.com/api/docs/pricing).

Published token rates are used only with sanitized returned usage: US$5/million text input,
US$8/million image input, US$2/million cached image input, and US$30/million image output.
Because exact custom-size output tokens are response-dependent, this experiment has a fixed
conservative one-call ceiling of US$0.07. Missing usage is reported as unavailable rather than
invented. A result whose computable estimate exceeds the ceiling fails closed.

Some accounts may require organization verification. Preflight does not validate provider accounts,
credentials, billing, quota, or model availability and makes no provider call.

## Security, media, and one-call state

Runtime must authorize `network`, `secrets`, and `filesystem_write` before it constructs the
experiment access object or reads the dedicated
`VSS_EXPERIMENT_M8_3_SMOKE_OPENAI_API_KEY` environment variable. The credential is not a CLI
or JSON input and may not enter prompts, digests, metadata, audit, diagnostics, or files.
Transport is pinned to the exact endpoint, denies all redirects, has no retry/fallback, bounds
request and response bytes, and retains only closed sanitized HTTP, transport, and post-HTTP
failure evidence.

After Runtime authorization and authoritative request derivation, a closed preflight checks the
unused fixed state root, output-root readiness, same-process credential-variable presence, absence
of routing proxy variables, and bounded DNS resolution for the exact endpoint hostname. It reads no
credential value, persists no resolved address, mutates no state, and makes no provider request.

After preflight succeeds and before credential retrieval or transport, create-once local attempt state is reserved under
`.local/movie/m8-3-real-provider-smoke-2/attempt.json`. Its presence permanently rejects later
normal-path execution, including after a failure or process interruption. Dry-run reads no
secret, runs no external preflight, reserves no state, and makes no provider call.

Decoded PNGs remain capped at 10 MiB. The encoded-response cap is the base64 expansion of that
maximum plus 64 KiB of bounded JSON envelope overhead. The experiment profile accepts strict
1280x720, 8-bit RGB/RGBA, non-interlaced PNG with `IHDR`, contiguous `IDAT`, and `IEND`, plus
at most one valid `caBX` immediately after `IHDR`. The original bytes, including `caBX`, are
published unchanged after audit and covered by the media SHA-256. A `caBX` payload is opaque,
is not separately persisted or interpreted, is not cryptographically verified, and grants no
authority.

## Human review after a successful call

Generation stops before review. The bounded reviewer record asks:

1. Is Mira / the required subject treatment appropriate for this detail shot?
2. Is the discovery relationship between lantern and locked gate visually legible?
3. Is the courtyard-at-dawn context perceptible where appropriate?
4. Did any review/control/UI/specification text enter the pixels?
5. Is the lantern's unresolved significance preserved rather than canonically resolved?
6. Is there meaningful bounded artistic interpretation rather than sterile neutrality?
7. Is there any contradiction of known canon?
8. Does the image feel motivated as a cinematic shot rather than merely an illustration?

Disposition is exactly `USE`, `REGENERATE`, or `REJECT`. Here `REGENERATE` means only that a
future experiment may be architecturally justified; it never authorizes a second call in this
experiment. No automated creative score or disposition exists.

## Implementation checkpoint

Implementation, preflight, and validation make zero provider calls. Paid execution requires a separate,
explicit one-call authorization after review of the pre-paid-call checkpoint.
