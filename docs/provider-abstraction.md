# Provider Abstraction M2.4

M2.4 gives trusted built-in capabilities a provider-neutral service contract
without allowing workflow or CLI input to select implementations. The initial
vertical slice contains only a standard-library local clock and the
SDK-authored `runtime.time` capability.

## Contract and identity

Provider API version `1` defines `ClockProvider`:

```python
now_utc() -> UtcTimestamp
monotonic_time() -> MonotonicReading
```

Both results are frozen typed values. UTC timestamps use normalized
millisecond-precision `YYYY-MM-DDTHH:MM:SS.sssZ`; monotonic readings are finite,
non-negative numbers. A safe runtime handle validates both methods and converts
provider exceptions into fixed provider failures.

The initial clock implementation is:

- type: `clock`;
- identity: `system.clock.local`;
- version: `1.0.0`;
- implementation identity: `vss.local-clock`;
- lifecycle: `active`; and
- source/trust class: `trusted_builtin`.

It uses only `datetime` and `time` from the Python standard library and has no
configuration, network, credentials, secrets, filesystem, or subprocess use.

## Registry and static selection

Provider manifests live only under `providers/builtin/` and are safe-loaded and
validated against `schemas/provider-v1.schema.json`. Discovery rejects unknown
fields and types, duplicates, unsafe implementation references, path traversal,
symlink escape, unsupported API versions, missing implementations, and
unapproved source or implementation identities. Manifest and implementation
digests are checked immediately before initialization.

Selection is static: clock requirements resolve only to
`system.clock.local`. Environment variables, CLI arguments, user paths,
installed package entry points, remote configuration, downloads, fallback
chains, and dynamic imports are not selection mechanisms. A future selector
may consume reviewed configuration, but that extension is not implemented.

## Capability authorization

Capability manifest schema version `1` has the optional backward-compatible
`required_providers` field. `runtime.time` declares:

```yaml
permissions: [provider_access]
required_providers:
  - type: clock
    identity: system.clock.local
    api_version: "1"
```

The permission and scoped requirement must appear together. Wildcards,
implementation paths, duplicate requirements, unknown types, and malformed
identities are rejected. A declaration requests access but does not grant it:
runtime policy must independently allow the exact provider identity before the
provider is initialized or exposed.

The immutable SDK context receives a `ProviderAccess` containing only approved
handles. `runtime.time` calls `context.providers.get_clock()` and does not
import `time`, `datetime`, provider implementations, registries, or vendor SDKs.
The accessor offers no provider enumeration or arbitrary lookup method.

## Invocation and audit

Invoke the vertical slice through the existing command path:

```bash
vss run runtime.time --environment development
```

The response uses the existing VSS envelope and contains only normalized UTC
time in `output.utc`. Runtime audit records add provider type, identity,
version, and authorization result. They exclude provider output, configuration,
environment values, credentials, and capability input. Initialization,
execution, normalization, or audit failure cannot return success.

Tests can replace the repository-local implementation inside an isolated test
root with a deterministic fake implementing the same contract. Acceptance tests
still invoke the production Runtime Controller, provider registry, selector,
policy, safe handle, result normalization, and audit path.

## Trust boundary and deferred scope

Built-in providers and capabilities are trusted Python running in the runtime
process. Python object restrictions prevent accidental access and make approved
contracts explicit; they are not a sandbox against deliberately malicious
reviewed code, which could import implementation modules directly. Third-party
providers require process isolation, signing, provenance, revocation, and trust
policy that M2.4 does not design.

Vendor and AI providers, clouds, object storage, network calls, credentials,
secrets, dynamic installation or discovery, marketplaces, fallback, load
balancing, cost optimization, retries, workflow provider configuration,
provider CLI management, and media-production providers are intentionally
deferred.

Later movie POC slices add two separate provider-neutral review-media contracts:
the three-panel deterministic SVG storyboard renderer and the one-frame pictorial
PNG generator. Both have one exact statically selected repository-owned local
implementation, are authorized through Runtime, and use no network, credentials,
vendor parameters, retries, or fallback. The PNG request exposes only the admitted
selected-frame projection and separates its deterministic semantic identity from
the execution attempt and output content digest.

M10.0 adds one deliberately non-general external provider type,
`controlled_storyboard_image_generation`, with the sole statically selected
identity `movie.storyboard-image.openai`. It is available only to the controlled
review-frame capability. Runtime wraps it in a one-use handle that retains the
credential reader and transport; the capability can neither retrieve the secret
nor make a second call. Exact model, endpoint, request settings, price policy,
and data policy are part of the authoritative request and approval. There is no
alias, fallback, retry, provider choice, or provider enumeration. This does not
open the local `storyboard_image_generation` contract or create a general vendor
catalog. See `docs/movie-controlled-generation.md`.

The provider's version-1.1 output boundary independently reconstructs a bounded
opaque PNG `caBX` summary from returned bytes. It preserves the complete PNG and
records metadata presence without parsing, verifying, trusting, or converting
an external provenance claim into VSS authority. A separate sealed terminal
attempt outcome records sanitized evidence even when no candidate is admitted.
