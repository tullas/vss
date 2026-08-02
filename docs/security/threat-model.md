# VSS security threat model

## Scope, assets and adversaries

Assets include source/review history, workflow identities, credentials,
developer/root boundaries, Docker socket, IaC state, dependency locks,
approvals/exceptions, release artifacts, SBOMs and provenance. Adversaries
include compromised upstreams/accounts/actions/images/providers, malicious PRs
or dependencies, local unprivileged users, and mistaken or over-privileged
operators/agents.

## Trust boundaries and abuse cases

- Developer shell to bootstrap, then validated developer identity across sudo
  to root Ansible. Abuse: repository/path substitution or malicious package
  scripts. Mitigation: owner/passwd validation, single sudo boundary, signed
  repositories, recorded key fingerprints and independent review.
- Repository/PR to GitHub-hosted runner and third-party Actions. Abuse: tag
  retargeting, token exfiltration, gate deletion. Mitigation: SHA pins,
  read-only permissions, CODEOWNERS, policy invariants and external required
  rulesets.
- PyPI/APT/registries to build/bootstrap. Abuse: dependency confusion or
  compromised release/key. Mitigation: exact hashed Python locks, component
  admission, provider/image digests, vulnerability/license scans. APT snapshot
  reproducibility remains deferred.
- OpenTofu core to executable provider, then Docker socket. Abuse: provider or
  container obtains host-root-equivalent control. Mitigation: checksum lock,
  exact provider pin, approved image digest, named local developer only, never
  expose the socket to untrusted CI workloads.
- Secrets to process/OpenTofu/container/state/log/artifact. Abuse: diagnostics
  or generated evidence leaks values. Mitigation: ignored state/tfvars, fixed
  summaries, artifact allowlist and secret-canary tests.
- VSS agent/command execution and future plugins/workflows. Abuse: shell/argv
  injection, capability escalation or autonomous risk acceptance. Mitigation:
  argv execution, schemas, timeouts, explicit capability authorization,
  independent approval and deny-by-default future plugin admission.
- Repository-controlled capability manifest to the M2.1 Runtime Kernel and
  built-in handler. Abuse: unsafe YAML construction, malformed or substituted
  manifests, path/symlink escape, arbitrary module import, permission
  escalation, secret disclosure, or audit injection/tampering. Mitigation:
  safe YAML loading, strict versioned schemas, fixed built-in discovery root,
  canonical containment checks, constrained local entry points, manifest
  digest revalidation before import, deny-by-default runtime policy, input
  schemas, append-only structured audit records, and adversarial tests. Local
  audit files are not tamper-proof and remain a residual risk.
- Repository-controlled workflow YAML to the M2.2 sequential interpreter and
  operation adapters. Abuse: unsafe YAML construction, path or symlink escape,
  expression/shell injection, arbitrary operation selection, recursive or
  excessive execution, secret-bearing audit data, or bypass of per-operation
  controls. Mitigation: safe YAML loading, a strict versioned schema, fixed
  built-in discovery root, canonical containment and digest revalidation, a
  two-operation code allowlist, bounded step counts and timeouts, no
  interpolation/includes/conditions, stop-on-failure semantics, M2.1 policy
  enforcement for both allowlisted capabilities, bounded result normalization,
  and structured input-free audit events.
- Repository-controlled SDK-authored capability code to the in-process M2.3
  handler contract. Trusted code may still be defective: it can return unsafe
  objects, raise exceptions, accidentally disclose data, or assume permissions
  it was not granted. Mitigation: immutable bounded contexts, an empty safe
  configuration view by default, typed results and errors, strict JSON size and
  depth limits, input/output schemas, manifest-to-handler identity/version
  binding, deny-by-default policy, controller-only acceptance tests, filtered
  exceptions, and input-free audit records. These contracts reduce accidental
  privilege and disclosure; they are not process isolation and cannot contain
  malicious built-in Python.
- Repository-controlled provider metadata and implementation code to the M2.4
  provider boundary. Abuse: provider substitution, malicious or defective
  implementation code, compromised dependencies, credential misuse, overbroad
  capability access, unsafe provider output, or direct implementation
  instantiation. Mitigation: strict safe-loaded manifests, fixed built-in roots,
  path and symlink containment, manifest and implementation digests, approved
  implementation identity and source classification, static selection, exact
  provider requirements, independent deny-by-default authorization,
  non-enumerable narrow handles, output normalization, input-free provider audit
  metadata, and adversarial tests. The local clock has no dependencies or
  credentials. Built-in Python providers remain trusted in-process code and are
  not sandboxed; these controls do not contain a malicious reviewed provider or
  capability that deliberately imports implementation modules.
- Runtime-owned M2.5 host inspection to approved local executable and socket
  probes. Abuse: arbitrary executable or argument selection, shell injection,
  PATH substitution, permission inflation, raw subprocess disclosure, or
  capability bypass of audit. Mitigation: a single non-enumerable
  `bootstrap_check()` context method, exact capability-scoped permissions,
  fixed executable and argument allowlists, resolved approved system paths,
  empty subprocess environments, fixed loopback ports, bounded normalized
  version output, controller-only invocation, and input/output-free audit
  records. This boundary constrains defective trusted code; in-process Python
  remains unsandboxed.
- Repository-owned M3.1 semantic schemas and fixed registry metadata to inert
  validated request/result objects. Abuse: contract or schema substitution,
  version downgrade, universal-object growth, extension-bag or multiple-payload
  injection, identity/payload mismatch, dynamic registration or arbitrary
  schema/module loading, provider-native or prompt-field injection, oversized
  or recursive objects, post-validation mutation, false confidence authority,
  evidence references treated as source access, registration treated as
  authorization, or sensitive error disclosure. Implemented mitigation: four
  exact repository-contained non-symlink schema paths; Draft 2020-12 schema and
  identity checks; no external references, imports, plugins, environment or CLI
  schema overrides; immutable registry/schema snapshots and validated values;
  exact-version task/family resolution; one typed payload; strict unknown-field,
  size, depth, node, integer and JSON-type bounds; deterministic canonical
  digests; qualified non-authorizing confidence; inert evidence identifiers;
  safe payload-free errors; and adversarial tests. Schema and registry digests
  prove recorded integrity, not signatures, authenticity, authorization, or
  truth. Provider invocation, Knowledge Package resolution, Plan IR, approval,
  execution, signing, third-party registration and production audit are not
  implemented and remain governed by later milestones and accepted ADRs.

Residual risks include hosted-runner administration, repository ruleset
configuration, mutable APT repository contents, Docker group privilege,
scanner-database availability, and unsigned provenance consumer verification.
Signed capability bundles, revocation, external trust roots, isolation for
third-party code, and third-party capability provenance remain deferred;
dynamic third-party capability installation is prohibited until those controls
are designed and validated.
