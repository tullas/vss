from __future__ import annotations

import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = ROOT / "docs/adr"
ADR_25 = ADR_DIR / "ADR-0025-scoped-studio-resources-rights-canon-provenance.md"
ADR_26 = ADR_DIR / "ADR-0026-studio-governance-principal-identity-lifecycle-operations.md"
ADR_27 = ADR_DIR / "ADR-0027-portable-authoritative-state-storage-evolution.md"
REVIEW = ROOT / "docs/architecture-boundary-review.md"
DOCUMENTS = (ADR_25, ADR_26, ADR_27, REVIEW)


class StudioArchitectureGuardrailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = {path: path.read_text(encoding="utf-8") for path in DOCUMENTS}

    def test_exact_accepted_adr_identity_and_boundary_ownership(self) -> None:
        expected = {
            ADR_25: "# ADR-0025: Scoped Studio Resources, Rights, Canon, and Provenance",
            ADR_26: "# ADR-0026: Studio Governance, Principal Identity, and Lifecycle Operations",
            ADR_27: "# ADR-0027: Portable Authoritative State and Storage Evolution",
        }
        for path, title in expected.items():
            with self.subTest(path=path.name):
                text = self.text[path]
                self.assertTrue(text.startswith(title + "\n"))
                self.assertIn("## Status\n\nAccepted", text)
                self.assertIn("## Decision", text)
                self.assertIn("## Deferred", text)
                self.assertIn("## Acceptance criteria", text)
        self.assertIn("Runtime remains the sole execution", self.text[ADR_26])
        self.assertIn("ADR-0023", self.text[ADR_27])
        self.assertIn("ADR-0022", self.text[ADR_25])

    def test_scope_promotion_rights_canon_and_incremental_rules_are_closed(self) -> None:
        text = " ".join(self.text[ADR_25].split())
        required = (
            "Tenant isolation is deny-by-default",
            "never implies discovery, access, rights, or reuse across tenants",
            "Scope promotion is asymmetric",
            "Generation is not ownership. Storage is not ownership. Access is not",
            "Derived rights compose by intersection",
            "Negative rights are first-class",
            "legal interpretation are distinct",
            "no inferred training, reuse, publication, sale, or cross-customer rights",
            "Canon is a versioned decision set or snapshot",
            "never silently rewrites historical",
            "incremental dependency graph",
            "Reuse is considered before adaptation, and adaptation before generation",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for rights_class in (
            "customer_owned", "vss_owned", "third_party", "public_domain",
            "open_licensed", "joint",
        ):
            self.assertIn(f"`{rights_class}`", text)

    def test_media_bom_and_provenance_are_exportable_but_non_authorizing(self) -> None:
        text = " ".join(self.text[ADR_25].split())
        for phrase in (
            "Media Bill of Materials", "provider, model, model version", "preservation class",
            "reproducibility level", "Provenance remains portable and exportable",
            "never become VSS policy or Runtime authority",
        ):
            self.assertIn(phrase, text)

    def test_governance_domains_principals_and_lifecycle_are_complete(self) -> None:
        text = " ".join(self.text[ADR_26].split())
        for principal in ("human", "agent", "service", "provider", "organization"):
            self.assertIn(f"`{principal}`", text)
        for domain in (
            "Creative authority", "Runtime/effect authority", "Rights/legal policy",
            "Commercial/budget policy", "Platform/SRE change authority", "Security authority",
            "Data governance", "Audit/break-glass",
        ):
            self.assertIn(domain, text)
        for stage in (
            "detect / recommend", "plan", "preflight", "approval", "Runtime-authorized execution",
            "verification", "evidence", "forward recovery",
        ):
            self.assertIn(stage, text)
        for lifecycle_class in (
            "OS patches", "base images", "database engine", "storage formats",
            "workflow-engine", "model/provider deprecation", "certificate, key",
            "CVE remediation", "disaster-recovery", "capacity changes", "end-of-life",
        ):
            self.assertIn(lifecycle_class, text)
        self.assertIn("Drift in any material binding invalidates approval", text)
        self.assertIn("Database rollback is never presumed possible", text)
        self.assertIn("not agent self-authorization", text)

    def test_portability_allows_features_without_vendor_authority(self) -> None:
        text = " ".join(self.text[ADR_27].split())
        for phrase in (
            "not SQL dialect", "cannot replace or silently alter canonical identity",
            "not a generic CRUD abstraction", "vendor-specific features",
            "adapter conformance tests", "feature suppression",
            "Logical export formats", "Physical backups", "periodic bounded drill",
            "derived and rebuildable", "never authoritative for rights",
        ):
            self.assertIn(phrase, text)
        self.assertIn("no database, storage, queue, policy, orchestration, or identity product is selected", text)

    def test_unknown_unknown_review_is_bounded_material_risk_only(self) -> None:
        text = self.text[REVIEW]
        compact = " ".join(text.split())
        self.assertTrue(text.startswith("# UNKNOWN_UNKNOWN_REVIEW\n"))
        self.assertIn("major architecture boundary", text)
        self.assertIn("not recurring ceremony", compact)
        self.assertIn("Maximum 20 findings", compact)
        self.assertIn("not a feature brainstorm", compact)
        for scenario in range(1, 14):
            self.assertRegex(text, rf"(?m)^{scenario}\. ")
        for disposition in ("block", "mitigate_before_acceptance", "accept_with_bound", "defer_with_trigger"):
            self.assertIn(f"`{disposition}`", text)
        self.assertIn("grants no Runtime", text)

    def test_adrs_apply_review_to_material_new_seams_only(self) -> None:
        expected = {
            ADR_25: ("Rights may be invalidated after many derivatives exist", "automatic mass regeneration"),
            ADR_26: ("compromised agent/service credential", "interpret silence/timeout as approval"),
            ADR_27: ("resurrect deleted, revoked, expired", "restore success is not production admission"),
        }
        for path, phrases in expected.items():
            with self.subTest(path=path.name):
                text = self.text[path]
                self.assertEqual(text.count("## UNKNOWN_UNKNOWN_REVIEW findings"), 1)
                self.assertIn("three material missing seams", text)
                for phrase in phrases:
                    self.assertIn(phrase, text)
                self.assertIn("No ", text.partition("## UNKNOWN_UNKNOWN_REVIEW findings")[2])

    def test_all_relative_markdown_links_resolve(self) -> None:
        missing: list[str] = []
        for document, text in self.text.items():
            for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (document.parent / target.partition("#")[0]).resolve()
                if not resolved.exists():
                    missing.append(f"{document.relative_to(ROOT)} -> {target}")
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
