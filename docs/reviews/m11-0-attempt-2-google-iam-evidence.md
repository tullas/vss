# M11.0 Attempt 2 Google Cloud IAM Evidence

This record preserves the recovered provider-side evidence supplied from
project `vss-film-poc` for the permanently consumed corrected attempt
`9a7fb8229afabd087db5128efc4a1cb788a0a1fe4d8e34aec09185854320e76b`.

| Field | Evidence |
| --- | --- |
| Timestamp | `2026-09-10T21:12:37.762713Z` |
| Log | `cloudaudit.googleapis.com/activity` |
| Service | `cloudresourcemanager.googleapis.com` |
| Method | `SetIamPolicy` |
| Actor | `service-agent-manager@system.gserviceaccount.com` |
| Delta | `ADD` |
| Member | `serviceAccount:service-1008607911742@gcp-sa-aiplatform.iam.gserviceaccount.com` |
| Role | `roles/aiplatform.serviceAgent` |
| Project number | `1008607911742` |

The resulting binding is confirmed by the recovered response. This strongly
correlates first-use Vertex service-agent provisioning with attempt 2, but it
does not prove that provisioning caused the Veo failure. No
`aiplatform.googleapis.com` audit entry, operation ID, HTTP diagnostic, or
actual-cost record was recovered. The event is evidence only and grants no
retry, regeneration, provider, Runtime, production, or publication authority.
