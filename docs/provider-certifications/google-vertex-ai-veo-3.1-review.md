# Google Vertex AI Veo 3.1 provider-specialist certification review

Review date: 2026-09-11. Scope is the exact VSS Film #1 image-to-video profile
listed below. This is provider conformance evidence, not permission to generate.
No generation request, paid operation, Shot 3 authorization, or Shot 3 package
repair is part of this record.

## Bounded profile and disposition

| Field | Value | Status |
| --- | --- | --- |
| Provider/model | Google Vertex AI; Veo 3.1 `veo-3.1-generate-001` | CERTIFIED |
| Model lifecycle | GA model; lifecycle page lists retirement November 17, 2026 or later | CERTIFIED (recheck before use) |
| Region | `us-central1` | CERTIFIED |
| Input mode | One image-to-video image (`image`), PNG, plus prompt | CERTIFIED |
| Reference-image mode (`referenceImages`) | Not supported by this exact model ID | UNSUPPORTED; not required by this profile |
| Requested outputs | `sampleCount: 1` | CERTIFIED |
| Duration | 8 seconds | CERTIFIED |
| Frame | 16:9, 720p (1280x720); 24 fps | CERTIFIED |
| Output media | `video/mp4` | CERTIFIED |
| Audio | Provider supports `generateAudio` boolean; VSS sends `false`; successful historical output has no audio stream | CERTIFIED for VSS no-audio profile |
| Authentication mechanism | OAuth 2.0 bearer access token; API enabled and project authorization required | CERTIFIED as contract; present token's current validity UNKNOWN |
| Current project/auth readiness | Current configured project is `vss-film-poc`, location is `us-central1`; read-only API calls returned HTTP 401 | UNKNOWN |
| Current effective quota | Historical evidence records fixed quota 50 requests/minute for the exact model/region; current read failed HTTP 401 and historical file has no timestamp | UNKNOWN |
| Current expected 8-second cost | Google pricing currently lists video-only 720p/1080p as `$0.20 / 1 count`, without defining that count in the cited row as a second or an 8-second video | UNKNOWN |
| Exact bounded profile certification | Requires current live readiness and authoritative cost calculation in addition to the certified contract facts | UNKNOWN; not certified |

The inability to establish current credentials/quota or calculate the price is
not evidence that the model or region is unsupported. Those facts remain
UNKNOWN. Reference-image support is explicitly UNSUPPORTED for this model but
is outside the VSS Film #1 profile and does not make the provider globally
ineligible.

## Authoritative evidence

Google's [Veo 3.1 model page](https://cloud.google.com/vertex-ai/generative-ai/docs/models/veo/3-1-generate)
identifies `veo-3.1-generate-001`, image-to-video, supported regions, 16:9,
720p/1080p, 24 FPS, MP4, the `generateAudio` control, and the 8-second
image-to-video limit. It explicitly distinguishes unsupported reference-image
input from ordinary image-to-video. The model-specific [API reference](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/veo-video-generation)
defines the image union (`bytesBase64Encoded` or `gcsUri` plus `mimeType`),
`durationSeconds`, `aspectRatio`, `resolution`, `sampleCount`, and
`generateAudio` request fields. The request produced by VSS selects 16:9,
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
The [pricing page](https://cloud.google.com/vertex-ai/generative-ai/pricing)
currently displays video-only Veo 3.1 at `$0.20 / 1 count` for 720p/1080p.
It does not define the count in that row as seconds or an eight-second output;
therefore neither `$1.60` from a historical estimate nor `$0.20` is adopted as
the certified expected cost. Expected 8-second cost is UNKNOWN; actual spend
in this certification work is `$0`.

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

The environment exposes project `vss-film-poc`, location `us-central1`, and a
configured `VSS_VERTEX_AI_ACCESS_TOKEN`. A read-only bearer-authenticated
Cloud Resource Manager project lookup, Service Usage API lookup for
`aiplatform.googleapis.com`, and Service Usage consumer quota lookup each
returned HTTP 401. Thus the configured token is present but **not established
as usable** for these Google APIs; current project lifecycle/API enablement
and effective quota could not be refreshed. The local `gcloud` configuration
also could not be used because its credential database is unavailable in this
read-only workspace. No publisher-model metadata endpoint was called. No
generation endpoint was called.

The preserved historical readiness record
`docs/reviews/m11-0-vertex-readiness-evidence.json` records the API enabled,
project number `1008607911742`, and Vertex service-agent role binding. The
historical quota evidence `.local/config/m11-0-veo-quota-evidence.json`
records metric `aiplatform.googleapis.com/long_running_online_prediction_requests_per_base_model`,
base model `veo-3.1-generate-001`, region `us-central1`, and default/effective
limit 50 per minute for `vss-film-poc`. Neither record contains a freshness
timestamp establishing it as current on this review date.

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
Google's current model/API/lifecycle/pricing/quota docs and these operation
records. It found and records these disagreements with the prior draft rather
than carrying them forward silently:

1. The prior draft listed reference-image-to-video as supported. The exact
   `-001` model page says reference-image input is unsupported; only ordinary
   image-to-video is in this profile. The separate preview model identifier
   is not substituted.
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

The narrow contract facts supported by current docs and historical operations
are CERTIFIED. `referenceImages` is UNSUPPORTED. Current auth readiness,
effective quota/freshness, and the expected eight-second cost remain UNKNOWN.
Therefore the exact bounded Film #1 execution profile is **not yet
CERTIFIED**. No generation call was made; actual cost is `$0`.
