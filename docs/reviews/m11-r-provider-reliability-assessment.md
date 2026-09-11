# M11.R Provider Reliability Foundation Assessment

## Decision

Implement a thin provider-neutral reliability package for advisory diagnosis,
bounded deterministic flight-recorder evidence, readiness assessment, and
offline digital-twin rehearsal. It owns no provider access, credentials,
retry, spending, publication, production, or Runtime authority.

## Existing capabilities reused

Runtime remains the effect boundary. The foundation reuses the existing
provider registry and handles, `ExternalExecutionPreflight`, provider failure
diagnostics, attempt ledgers, bounded operation evidence, canonical JSON
digests, and isolated unittest discovery. Veo remains the first adopter; its
existing adapter is not redesigned.

## Gaps found

Failure classes were scattered strings, lifecycle evidence was adapter-owned,
there was no common deterministic readiness result, and fake transports did
not form a named cross-provider scenario corpus. Attempts 1–5 had no shared
machine-readable lesson index.

## Reliability rule

No paid or externally side-effecting provider capability should be admitted
unless request, asynchronous lifecycle, terminal response, artifact admission,
and failure evidence can first be exercised deterministically without the
provider. This is an admission rule, not an execution mechanism.

## Attempt lessons

`docs/reviews/m11-r-attempt-lessons.json` indexes the five consumed attempts
without copying or modifying their evidence. Missing historical fields remain
explicitly unknown. Each entry binds a classification to a regression and a
readiness check; future novel failures follow the same classification →
regression → readiness → knowledge path.
