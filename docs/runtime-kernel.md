# Runtime Kernel M2.1

VSS M2.1 introduced a minimal capability-oriented execution path beside the
existing command engine. M2.3 added the SDK-authored `runtime.echo` capability,
and M2.5 migrates only the read-only `bootstrap.check` operation. All existing command names,
CLI forms, response fields, correlation-ID behavior, and existing handlers
remain compatible; the current command registry is still authoritative for CLI
command discovery.

## Boundaries and discovery

The Runtime Controller coordinates capability resolution, manifest and input
validation, policy authorization, handler invocation, response normalization,
and audit. Domain behavior stays in built-in handlers. Provider, workflow,
remote installation, and CLI presentation concerns stay outside the kernel.

Built-ins are discovered only as direct directories under the repository's
`capabilities/` root. Each directory has a `manifest.yaml` and a constrained
local entry point in `file.py:function` form. Discovery does not inspect user
paths, installed Python entry points, or network sources. Resolved manifest and
handler paths must remain inside the built-in root; path and symlink escapes are
rejected. The validated manifest SHA-256 is checked again before handler import.

## Manifest and runtime API

Authored manifests use safe-loaded YAML and are validated against
`schemas/capability-manifest-v1.schema.json`. M2.1 supports manifest schema
version `1` and runtime API version `1`. Required metadata covers identity,
version, description, entry point, commands and their schemas, permissions,
compatibility, and lifecycle status. Unknown fields, unsupported versions,
unsafe entry points, duplicate identities, duplicate commands, and unknown
permission categories fail closed.

## Authorization

Runtime policy is independent of manifest declarations. The effective
permission set is the intersection of known declarations and permissions
explicitly allowed by policy. Capability-specific policy admits
`filesystem_read` and `subprocess` only for the trusted `bootstrap.check`
built-in; generic policy does not grant them. `system.info` still declares
none. Known but
unapproved permissions return named exit code `PERMISSION_DENIED` (`13`) before
handler execution. Unknown permissions make the manifest invalid.

## Audit and integrity

Every attempted runtime execution appends one structured JSON Lines record to
`.local/runtime/audit/executions.jsonl`. The directory is ignored by Git and is
mode `0700`; the file is mode `0600` where supported. Records contain UTC time,
correlation and execution IDs, capability and command identities, outcome, exit code, duration,
declared permissions, authorization result, validated manifest digest, and the
current source commit when Git metadata is available. Inputs, configuration,
environment-variable values, secrets, raw exceptions, and unnecessary host
identity are excluded. An audit write failure cannot produce a successful
runtime response.

This binds M2.1 built-ins to repository-controlled paths, the validated
manifest contents observed for the invocation, and source revision metadata.
It is not cryptographic plugin signing. Signed bundles, revocation, external
trust roots, third-party provenance, and isolation for external code are
deferred, and dynamic third-party capability installation is not supported.

## Reference invocation

The existing forms continue to exercise the `system.info` capability:

```bash
vss run system.info --environment development
vss run system.info --environment development --correlation-id example-id
```

The built-in handler adapts the existing `system.info` command handler, so its
domain output remains unchanged while execution passes through discovery,
validation, authorization, invocation, normalization, and audit.

The SDK reference capability uses the same controller and envelope:

```bash
vss run runtime.echo --environment development --input input.json
```

See `docs/capability-sdk.md` for the supported built-in authoring contract.

M2.4 adds the provider-neutral `runtime.time` capability without changing the
existing envelope or command engine:

```bash
vss run runtime.time --environment development
```

Its provider requirement is resolved statically, independently authorized, and
exposed only through the narrow SDK context accessor described in
`docs/provider-abstraction.md`.

M2.5 supports both the unchanged legacy CLI and direct runtime form:

```bash
vss bootstrap check --environment development
vss run bootstrap.check --environment development
```

Both resolve the same SDK-authored built-in and produce one capability audit
record. The handler receives a narrow runtime-owned host-inspection contract;
it never receives a generic subprocess launcher, filesystem handle, environment
mapping, Docker socket, or provider registry. `bootstrap.local`,
`bootstrap.verify`, platform, secrets, and other privileged operations remain
on the legacy command engine.

## Deferred functionality

The runtime does not include autonomous or multi-agent planning, provider
implementations, SDK scaffolding, remote or third-party plugins,
package downloads, distributed events, persistent databases, marketplace
behavior, or media-production functionality.
