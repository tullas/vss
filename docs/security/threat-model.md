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

Residual risks include hosted-runner administration, repository ruleset
configuration, mutable APT repository contents, Docker group privilege,
scanner-database availability, and unsigned provenance consumer verification.
Signed capability bundles, revocation, external trust roots, isolation for
third-party code, and third-party capability provenance remain deferred;
dynamic third-party capability installation is prohibited until those controls
are designed and validated.
