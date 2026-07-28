# Security gate adversarial acceptance mapping

The merged supply-chain policy already has repository-local adversarial tests
for each requested rejection. Each test creates a temporary fixture under
`tempfile.TemporaryDirectory()` and invokes the existing policy validator; no
production manifest, registry, workflow, or policy file is modified.

| Adversarial input | Existing test | Existing control |
| --- | --- | --- |
| Unpinned GitHub Action (`actions/checkout@v5`) | `test_unpinned_action_fails` | `supply_chain.validate_actions` rejects references that are not 40-character commit SHAs. |
| Mutable production image (`object-storage:latest`) | `test_mutable_production_image_fails` | `supply_chain.validate_images` requires an immutable SHA-256 image reference. |
| Expired security exception | `test_expired_exception_fails` | `supply_chain.validate_exceptions` rejects an expiry date before the supplied evaluation date. |
| Unreviewed direct dependency | `test_unreviewed_direct_dependency_fails` | `supply_chain.validate_direct_dependencies` rejects a pinned package absent from the approved PyPI component registry. |
| Prohibited license | `test_prohibited_license_fails` | `supply_chain.validate_licenses` rejects licenses in the prohibited set. |

The focused tests are in `tests/security/test_supply_chain.py`; the full
security suite runs them together with lock, vulnerability, workflow-invariant,
SBOM, and artifact-control tests. No duplicate adversarial tests were added.
