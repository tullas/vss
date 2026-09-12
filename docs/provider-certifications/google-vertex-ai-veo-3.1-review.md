# Google Vertex AI Veo 3.1 provider-specialist certification review

Review date: 2026-09-12 UTC. Scope is the exact VSS Film #1 image-to-video profile
listed below. This is provider conformance evidence, not permission to generate.
No generation request, paid operation, Shot 3 authorization, or Shot 3 package
repair is part of this record.

## Bounded profile and disposition

| Field | Value | Status |
| --- | --- | --- |
| Provider/model | Google Vertex AI; Veo 3.1 `veo-3.1-generate-001` | CERTIFIED |
| Model lifecycle | GA model; lifecycle page lists retirement November 17, 2026 or later | CERTIFIED (recheck before use) |
| Region | `us-central1` | CERTIFIED |
| Primary image-to-video input | One primary image in `instances[0].image`, PNG, plus prompt | CERTIFIED; used by Film #1 |
| Subject/reference-image conditioning | Up to three subject images are supported by `veo-3.1-generate-001` | CERTIFIED; not used by Film #1 |
| REST subject-reference form | `instances[0].referenceImages[]`, each with `image` and `referenceType: "asset"`; image bytes may be Base64 or GCS URI | CERTIFIED by Google's reference-to-video REST documentation |
| SDK subject-reference form | Google shows `reference_images` and `VideoGenerationReferenceImage` in an SDK example using the separate preview model ID | UNKNOWN for exact SDK transport with `veo-3.1-generate-001` |
| Requested outputs | `sampleCount: 1` | CERTIFIED |
| Duration | 8 seconds | CERTIFIED |
| Frame | 16:9, 720p (1280x720); 24 fps | CERTIFIED |
| Output media | `video/mp4` | CERTIFIED |
| Audio | Provider supports `generateAudio` boolean; VSS sends `false`; successful historical output has no audio stream | CERTIFIED for VSS no-audio profile |
| Authentication mechanism | OAuth 2.0 bearer access token; API enabled and project authorization required | CERTIFIED as contract |
| Current principal/project/API/IAM readiness | OAuth userinfo identified `t.ullas@gmail.com`; project `vss-film-poc` is active; `aiplatform.googleapis.com` is enabled; `testIamPermissions` returned `aiplatform.endpoints.predict`, `serviceusage.services.use`, and `serviceusage.quotas.get` | CERTIFIED for technical readiness; checked 2026-09-12T01:09:04Z–01:10:10Z |
| Current effective quota | Service Usage reports 50 requests/minute for `veo-3.1-generate-001` in `us-central1` | CERTIFIED; refreshed 2026-09-12T01:10:38Z–01:10:41Z |
| Current expected 8-second cost | Google pricing currently lists video-only 720p/1080p as `$0.20 / 1 count`, without defining that count in the cited row as a second or an 8-second video | UNKNOWN |
| TECHNICAL_EXECUTION | Existing Film #1 primary-image profile, provider conformance, current OAuth/project/API/IAM, and exact model/region quota are established | CERTIFIED; 2026-09-12T01:10:41Z |
| PRICING | The official `$0.20 / 1 count` rate is known, but its mapping to one 8-second output is not | UNKNOWN; historical 8-second cost remains `$1.60`, `HISTORICAL_OBSERVED` |

Technical provider certification is independent of pricing certification:
the Film #1 provider profile is technically certified for execution, while
pricing certification remains UNKNOWN. This does not approve, authorize, or
reserve any execution or spend; no human spend ceiling is established here.
Provider subject-reference conditioning is supported, but is a separate input
mode from the Film #1 primary-image mode. Google's REST type states that
`image` and `referenceImages` cannot both be supplied in the same instance.
The VSS Film #1 request stays on `image`; its adapter is not evidence for or
against the provider's separate reference capability. The exact GA SDK
subject-reference transport remains UNKNOWN and is outside this bounded
primary-image profile, so it does not block its technical certification.

## Authoritative evidence

Google's [current Veo 3.1 model page](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/veo/3-1-generate)
identifies `veo-3.1-generate-001`, primary image-to-video, subject reference
images, supported regions, 16:9,
720p/1080p, 24 FPS, MP4, the `generateAudio` control, and the 8-second
image-to-video limit. The separate [generate-videos-from-references guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-references)
explicitly lists `veo-3.1-generate-001` and `veo-3.1-fast-generate-001` as
supporting up to three subject images. Its REST example uses
`instances[].referenceImages[].image` with `referenceType: "asset"` and lists
both `-001` models as supported. The model-specific [API reference](https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rest/Shared.Types/VideoGenerationModelInstance)
defines the image union (`bytesBase64Encoded` or `gcsUri` plus `mimeType`),
`durationSeconds`, `aspectRatio`, `resolution`, `sampleCount`, and
`generateAudio` request fields. This API type says `image` and
`referenceImages` are mutually exclusive on one instance. The guide's SDK
example spells the field `reference_images` and uses
`VideoGenerationReferenceImage`, but its example selects
`veo-3.1-generate-preview`; therefore this review does not certify that SDK
call form for `veo-3.1-generate-001`. The Film #1 request uses only the primary
`image` field and selects 16:9,
720p, eight seconds, one sample, and `generateAudio: false`.

Google documents the model in `us-central1` in the [Veo 3.1 availability
page](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/veo/3-1-generate).
The [Veo generation API reference](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation)
documents POST `:predictLongRunning`, an accepted full operation name, and
POST `:fetchPredictOperation` with `operationName`. Pending operations report
`done: false`; a terminal operation reports `done: true` with either
`response` or `error`. A successful video response can carry
`videos[].bytesBase64Encoded` or `videos[].gcsUri`; omitting `storageUri`
selects inline bytes. The API documents the two artifact forms; VSS currently
admits only inline Base64 and rejects a GCS URI because its integration has no
URI fetch/admission path. VSS persists the accepted operation before polling
and recovery fetches that same name; it never submits again during recovery.

The [Veo lifecycle page](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions)
lists the model as released November 17, 2025 with retirement November 17,
2026 or later. Google release notes record Veo 3.1 GA and migration from the
separate `veo-3.1-generate-preview` identifier. The [quota documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/quotas)
names Veo's `long_running_online_prediction_requests_per_base_model` metric.
The [pricing page](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)
currently displays video-only Veo 3.1 at `$0.20 / 1 count` for 720p/1080p.
It does not define the count in that row as seconds or an eight-second output;
therefore neither `$1.60` from a historical estimate nor `$0.20` is adopted as
the certified expected cost. Google's [Cloud Billing Catalog documentation](https://docs.cloud.google.com/billing/v1/how-tos/catalog-api)
states that SKU records expose `usageUnit`, `usageUnitDescription`,
`baseUnit`, and `baseUnitConversionFactor`, which would establish a billable
unit. Its public Catalog API requires an API key; a prior OAuth catalog
refresh attempt was rejected with HTTP 401. Google's public [Gen AI video SKU group](https://cloud.google.com/skus/sku-groups/gen-ai-video-models)
does not expose the Veo 3.1 SKU's usage-unit mapping. Thus current authoritative
count-to-duration mapping remains UNKNOWN. Historical Shot 2 VSS operation
evidence records `actual_cost_usd: 1.600000` for one 8-second 720p no-audio
output; classify this as `HISTORICAL_OBSERVED` operational evidence, not an
authoritative current price or billing-export verification. Expected
8-second cost remains UNKNOWN; spend for this certification amendment is `$0`.

Google's request examples use OAuth bearer access tokens, including
`gcloud auth print-access-token`; the [Vertex authentication overview](https://cloud.google.com/vertex-ai/docs/authentication)
describes Application Default Credentials and IAM. API enablement and project
authorization are also required. No caller identity is inferred from a
configured token.

## Submission, acceptance, operation, and media contract

For the bounded profile, VSS submits one POST to
`https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/veo-3.1-generate-001:predictLongRunning`
with one instance containing the prompt and PNG image, and parameters
`aspectRatio: "16:9"`, `resolution: "720p"`, `durationSeconds: 8`,
`generateAudio: false`, and `sampleCount: 1`. The documented accepted
response contains a full operation `name`; VSS persists it before polling.
Polling POSTs `{"operationName": <full name>}` to the same resource's
`:fetchPredictOperation` endpoint. Recovery is a fetch of the same operation,
not a repeated generation submission. VSS tests its bounded poll count and
uses provider status, not an inferred maximum processing time. Google does
not document a fixed maximum processing duration in the cited API contract.

For this integration, the supported successful terminal artifact is exactly
one inline Base64 video with MIME `video/mp4`. Provider GCS output is
documented but not fetch-supported by this VSS integration. A terminal
`error` is failure; it does not authorize another submission. The VSS media
admission path validates MP4 container bytes and reports 1280x720. Historical
media inspection establishes H.264, 24/1 fps, eight seconds, and no audio for
the successful artifacts cited below; codec and actual output stream shape
are historical observations, not guarantees implied by Google's request
contract.

## Non-generation live checks and evidence freshness

All live checks used the freshly inherited OAuth bearer token and were
read-only. OAuth userinfo returned HTTP 200 and principal
`t.ullas@gmail.com` at 2026-09-12T01:09:04Z–01:09:06Z. Cloud Resource Manager
returned HTTP 200 for active project `vss-film-poc` (project number
`1008607911742`) at 2026-09-12T01:09:04Z–01:09:06Z. Service Usage returned
HTTP 200 and state `ENABLED` for `aiplatform.googleapis.com` at
2026-09-12T01:10:05Z–01:10:10Z. Project-level `testIamPermissions` returned
`aiplatform.endpoints.predict`, `serviceusage.services.use`, and
`serviceusage.quotas.get`, establishing the permissions needed for the
existing request path and this quota read. The quota metric
`aiplatform.googleapis.com/long_running_online_prediction_requests_per_base_model`
was read from Service Usage `consumerQuotaMetrics` at
2026-09-12T01:10:38Z–01:10:41Z. Its exact bucket for
`base_model=veo-3.1-generate-001`, `region=us-central1` has effective and
default limits of 50 requests/minute. These timestamps are the freshness bound
for this evidence. No publisher-model metadata endpoint or generation
endpoint was called. Generation submissions remain zero and cost remains $0.

The preserved historical readiness record
`docs/reviews/m11-0-vertex-readiness-evidence.json` records the API enabled,
project number `1008607911742`, and Vertex service-agent role binding. The
historical quota evidence `.local/config/m11-0-veo-quota-evidence.json`
records metric `aiplatform.googleapis.com/long_running_online_prediction_requests_per_base_model`,
base model `veo-3.1-generate-001`, region `us-central1`, and default/effective
limit 50 per minute for `vss-film-poc`. That historical record has no
freshness timestamp; the timestamped Service Usage read above is the current
quota evidence and supersedes it for live readiness.

## Historical conformance evidence and independent review

Evidence was read without editing or resealing it:

- Shot 1 Attempt 5 operation `.../operations/aa6b2f4a-f242-40ca-ae85-1ec420b653f8`
  was accepted, completed successfully with one inline Base64 MP4, and was
  subsequently fetched/recovered from that same operation without a new
  generation. The initial local media admission failed; the preserved
  correction in `docs/reviews/m11-0-attempt-5-recovery.json` documents the
  valid recovered 8-second 1280x720 H.264 MP4, 24 fps, no audio. This is
  provider conformance, not a claim that the original VSS admission succeeded.
- Shot 2 operation `.../operations/0f704ef2-e5e4-442a-90d2-c29f59123d4e`
  was accepted (HTTP 200), polled 13 times, and completed with exactly one
  `response.videos[0].bytesBase64Encoded`, `mimeType: video/mp4`. Preserved
  local output evidence records 8 seconds, 1280x720, 24/1 fps, no audio, and
  same-operation recovery. This is successful historical integration
  conformance; it is not current credential/quota evidence.

Independent provider-specialist review compared the certification against
Google's current model/API/lifecycle/pricing/quota and billing-catalog docs
and these operation records. It found and records these disagreements with
the prior draft rather than carrying them forward silently:

1. The prior review incorrectly said subject/reference images were
   unsupported for `veo-3.1-generate-001`, relying on older/conflicting
   documentation. Current Google model and reference-to-video docs establish
   that up to three subject images are supported. This capability is recorded
   as supported but unused by the Film #1 profile.
2. The prior draft listed first-and-last-frame-to-video among the certified
   generation modes. That optional mode is excluded from this profile; this
   record does not certify it.
3. The prior draft implied inline and Cloud Storage outputs were both
   integration-supported. Google supports both response forms, but VSS only
   admits inline output and rejects URI output. The profile omits `storageUri`.
4. The prior `$1.60` expected-cost claim used a per-second basis not
   established by the current pricing row. Current pricing's `$0.20 / 1
   count` is retained verbatim, with the count-to-duration mapping UNKNOWN.
5. The prior draft had no current lifecycle date. The lifecycle source now
   gives November 17, 2026 or later; it is a material near-term version risk.
6. The provider's subject-reference feature does not mean it can be combined
   with the profile's primary `image` field: Google's REST type states those
   fields are mutually exclusive. The SDK spelling is documented in an
   example against the preview model, so exact SDK behavior for the GA model
   remains UNKNOWN; the REST form is documented for the exact `-001` model.
7. Public pricing and the public SKU-group page do not map the `$0.20 / count`
   label to seconds or one 8-second video. A prior Cloud Billing catalog
   refresh attempt returned 401; this evidence refresh did not retry catalog
   lookup because the unresolved public unit mapping does not block technical
   certification.

The primary-image contract and the provider's separate subject-reference
conditioning capability are CERTIFIED; only the primary image is used by
Film #1. The exact REST subject-reference form is documented; exact SDK
behavior for the GA model is UNKNOWN. The bounded Film #1 profile is
**technically CERTIFIED for execution** based on current token, principal,
project, API, IAM, quota, and historical conformance evidence. Pricing
certification remains UNKNOWN: the official `$0.20 / 1 count` rate still has
no authoritative mapping to one 8-second output. The historical Shot 2 cost
of `$1.60` remains `HISTORICAL_OBSERVED`. This refresh does not establish a
human-approved spend ceiling or execution authority. No generation call was
made; actual cost of this amendment is `$0`.
