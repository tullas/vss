# Secure development

## Required flow

1. Threat-model security-relevant changes and update the component inventory.
2. Regenerate locks only with `scripts/security/regenerate-locks.sh` on a
   trusted developer host; review the complete diff.
3. Run `scripts/security/validate-supply-chain.py`, all tests, vulnerability,
   license, static, IaC, container, and secret gates.
4. Generate and validate the CycloneDX SBOM and release-candidate provenance.
5. Obtain independent review for workflows, policies, exceptions, privilege,
   dependency admission, or release controls.

Commands use argv arrays, fixed timeouts, least privilege, and fixed diagnostic
summaries. Secrets, environment values, tfvars, state, tokens, and raw child
output must not enter logs or artifacts. Future agents/plugins/workflows are
deny-by-default and require schema-bound capabilities plus human authorization
for privileged or network effects.

## NIST SSDF 1.1 support mapping

| Practices | Repository evidence |
| --- | --- |
| PO.1, PO.2, PO.4 | security/OSS/dependency/exception/upgrade policies; separated roles; release evidence |
| PO.3, PO.5 | approved toolchain registry; least-privilege pinned workflows |
| PS.1–PS.3 | reviewed workflow pins, immutable digests, locks, SBOM, provenance and retained evidence |
| PW.1, PW.2 | threat model and architecture review |
| PW.4, PW.5 | component admission and deterministic hash locks |
| PW.6–PW.9 | secure coding guidance, SAST/IaC/container/secret gates, tests and safe defaults |
| RV.1–RV.3 | scheduled lifecycle reporting, severity SLAs, remediation and rollback |

This mapping describes supporting controls, not SSDF compliance or
certification. Organizational branch rules, approvals, incident operations,
and release retention require evidence outside this repository.

## Continuing agent governance

- OSS Governance Agent: inventory, license/upstream analysis, issues and PRs;
  never approves license exceptions or its own work.
- Product Security Agent: threat/vulnerability analysis and remediation PRs;
  never waives findings or changes severity/risk policy.
- Dependency Upgrade Steward: dedicated update PRs, advisory/release context,
  regenerated locks/SBOM and rollback evidence; never auto-merges majors.
- Security Verification Agent: independently reruns gates and reports evidence;
  does not author the implementation it verifies.

Agents may analyze, create issues, and prepare PRs. They may not approve their
own changes, waive vulnerabilities, approve license exceptions, weaken required
controls, merge critical security changes, or change organizational risk
tolerance. Those decisions belong to named human risk owners.

## SLSA build assurance

The hosted security workflow scripts the source release candidate, records its
SHA-256 subject, and emits a validated in-toto statement using the SLSA
provenance v1 predicate. This is described as **SLSA Build Level 1-compatible
provenance**, not certification. It does not provide a signed trusted-builder
attestation.

The Level 2 path is intentionally deferred: use an isolated hosted builder,
platform-signed provenance, protected builder/workflow identity, immutable
published artifact digests, and a consumer command that verifies signature,
identity, provenance source and subject digest. Level 2 must not be claimed
until consumer verification and tamper tests pass end to end.

Required release evidence is the source revision, all dependency/provider
locks, component approvals and unexpired exceptions, vulnerability/license/
SAST/IaC/container/secret results, complete tests, CycloneDX SBOM and dependency
diff, artifact digest, provenance statement/validation, human approvals and
rollback revision. CI artifacts contain only the explicit allowlist.
