# Internal Capability SDK M2.3

The internal `vss_capabilities` package is the supported authoring contract for
trusted, repository-owned built-in capabilities. It standardizes handler input,
results, validation, compatibility metadata, and controller-backed tests. It is
not published externally and does not install or discover third-party code.

## Handler contract

An SDK handler is a plain callable:

```python
execute(context, input_data, dry_run) -> CapabilityResult
```

The `dry_run` argument preserves Runtime API v1 compatibility. SDK handlers
declare `sdk_api_version`, `capability_identity`, and `command_identity`
attributes. The loader checks those attributes against the validated manifest
before invocation. Handlers return `CapabilityResult.success()` with a JSON
object or `CapabilityResult.failure()` with a `SafeCapabilityError` and named
exit code. They never construct the external VSS response envelope; the Runtime
Controller owns status, timestamps, correlation, exit-code normalization, and
audit.

Raw exceptions become the fixed `capability execution failed` diagnostic.
`CapabilityResult` rejects unsafe output at construction, and the Runtime
Controller independently validates it again against the command output schema.
Arbitrary Python objects, non-finite numbers, oversized strings or documents,
excessive nesting, excessive item counts, and schema-invalid output fail closed.
Audit records never contain capability input or output.

## Execution context

`CapabilityExecutionContext` is frozen and exposes only:

- environment;
- correlation and execution IDs;
- capability and command identities;
- the immutable tuple of authorized permissions; and
- an immutable safe-configuration view.
- a narrow, non-enumerable provider accessor containing only independently
  authorized provider contracts.

M2.3 supplies an empty configuration view because no capability-specific safe
configuration contract has been admitted. The context does not expose
`os.environ`, raw secrets, provider credentials, filesystem handles, the Docker
socket, repository writes, subprocess launchers, or audit sinks.

M2.4 adds `context.providers.get_clock()` for capabilities whose manifest
declares the exact clock requirement and whose execution policy independently
approves it. The accessor does not expose the provider registry, selection,
configuration, implementation paths, credentials, or unrelated providers.

Python cannot sandbox trusted code running in the same process. A malicious
built-in can import Python modules and circumvent object-level conventions.
The SDK and runtime policy protect against defective or accidentally
over-privileged code; they are not an isolation boundary. Third-party code is
unsupported until signing, provenance, trust policy, revocation, and process
isolation are designed together.

## Manifest and permissions

SDK capabilities use manifest schema version `1`, Runtime API version `1`, and
SDK API version `1`. The optional `sdk_api_version` field distinguishes SDK
handlers from legacy built-ins without invalidating the M2.1 `system.info`
manifest. Existing schema strictness and safe YAML loading remain unchanged.

Permissions remain deny by default. A manifest declaration is only a request;
`RuntimePolicy` independently authorizes it before loading the handler. The
reference capability declares no permissions.

## Reference capability

`capabilities/runtime/` defines `runtime.echo`. Its input is exactly one `value`
field containing bounded JSON data, and its output is the same value:

```json
{"value":{"message":"hello"}}
```

Invoke it through the existing input-file mechanism:

```bash
vss run runtime.echo --environment development --input input.json
```

Unknown fields, unsupported Python values, documents over 4096 serialized
bytes, nesting beyond five levels, containers over 32 entries, more than 128
total nodes, and strings over 1024 characters are rejected. It performs no
filesystem, environment, network, subprocess, secret, provider, or Docker
access. `runtime-smoke` is unchanged and workflows do not allow `runtime.echo`
in M2.3.

## Testing harness

`vss_capabilities.testing.CapabilityTestHarness` copies one authored built-in
and the production manifest schema into an isolated temporary repository. Its
`manifest()`, `execute()`, `audit_records()`, and `deterministic_outcome()`
helpers cover manifest admission, valid and invalid input, policy denial,
normalized results, audit-safe behavior, deterministic outcomes, and handler
failure. `execute()` always calls the production `RuntimeController`; it does
not provide a direct-handler shortcut.

Authors should pair harness acceptance tests with small unit tests for pure
domain helpers when needed. Direct handler calls are not runtime acceptance
tests and do not demonstrate manifest, policy, output, or audit enforcement.

## Deferred scope

Automatic scaffolding is deferred to keep M2.3 narrow and avoid repository
write semantics. Authors manually add a directory, manifest, handler, and
controller-backed test. External SDK publication, dependency resolution, hot
reload, dynamic downloads, remote plugins, marketplaces, signed bundles,
providers, workflow retries or parallelism, and command migrations are also
deferred.
