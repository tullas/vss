from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from vss_context import ContextAssembler
from vss_context_contracts import ContextContractRegistry, ContextContractError, validate_context

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "tests/fixtures/context/context-assembly-request-valid.json"
PACKAGE = ROOT / "tests/fixtures/knowledge/knowledge-package-valid.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class ContextAssemblyTests(unittest.TestCase):
    def test_registry_is_deterministic_and_exact(self):
        first = ContextContractRegistry.built_in()
        second = ContextContractRegistry.built_in()
        self.assertEqual(first.digest, second.digest)
        self.assertEqual({(item.identity, item.version) for item in first.registrations}, {
            ("context_assembly_request", "1"), ("context_object", "1"),
            ("generate_options_context", "1"), ("context_assembly_report", "1"),
            ("scene_breakdown_context", "1"),
            ("scene_production_options_context", "1"),
        })
        with self.assertRaises(ContextContractError):
            first.resolve("context_object", "2")

    def test_assembly_is_bounded_and_deterministic_in_content(self):
        request = load(REQUEST)
        package = load(PACKAGE)
        assembler = ContextAssembler()
        one = assembler.assemble(request, [package], correlation_id=request["correlation_id"])
        two = assembler.assemble(request, [package], correlation_id=request["correlation_id"])
        self.assertEqual(one.context.value["context_content_digest"], two.context.value["context_content_digest"])
        self.assertEqual(one.context.value["selection_digest"], two.context.value["selection_digest"])
        self.assertEqual(one.context.value["payload"]["selected_notes"][0]["item_id"], "local-validation-principle")

    def test_context_fixture_validates(self):
        value = load(ROOT / "tests/fixtures/context/context-object-valid.json")
        validated = validate_context(value, ContextContractRegistry.built_in())
        self.assertEqual(validated.value["context_family"], "generate_options_context")
        exported = validated.to_json_value()
        exported["payload"]["selected_notes"][0]["body"] = "changed"
        self.assertNotEqual(exported["payload"]["selected_notes"][0]["body"], validated.value["payload"]["selected_notes"][0]["body"])

    def test_input_order_does_not_change_selection(self):
        request = load(REQUEST)
        package = load(PACKAGE)
        assembler = ContextAssembler()
        first = assembler.assemble(request, [package], correlation_id=request["correlation_id"])
        second = assembler.assemble(request, list(reversed([package])), correlation_id=request["correlation_id"])
        self.assertEqual(first.summary["context_content_digest"], second.summary["context_content_digest"])

    def test_purpose_substitution_fails_closed(self):
        request = load(REQUEST)
        request["purpose"] = "other-purpose"
        with self.assertRaises(ContextContractError):
            ContextAssembler().assemble(request, [load(PACKAGE)], correlation_id=request["correlation_id"])

    def test_correlation_binding_is_required(self):
        request = load(REQUEST)
        with self.assertRaises(ContextContractError):
            ContextAssembler().assemble(request, [load(PACKAGE)], correlation_id="different")

    def test_dry_run_does_not_construct_context(self):
        request = load(REQUEST)
        readiness = ContextAssembler().assemble(request, [load(PACKAGE)], correlation_id=request["correlation_id"], dry_run=True)
        self.assertTrue(readiness["readiness"]["eligible"])
        self.assertNotIn("context_content_digest", readiness["readiness"])

    def test_validation_clock_is_not_caller_selectable(self):
        request = load(REQUEST)
        request["validation_time"] = "2020-01-01T00:00:00Z"
        result = ContextAssembler().assemble(request, [load(PACKAGE)], correlation_id=request["correlation_id"])
        self.assertEqual(result.context.value["context_content_digest"], "18407e80203f3fd2716d1eac8afb1659478c0bbbe15166d00605f237bd8f2666")

    def test_required_item_missing_fails_closed(self):
        request = load(REQUEST)
        request["item_requirements"] = [{
            "item_id": "required-not-present",
            "item_family": "reference_note",
            "item_family_version": "1",
            "item_content_sha256": "0" * 64,
            "requirement": "required",
        }]
        with self.assertRaises(ContextContractError):
            ContextAssembler().assemble(request, [load(PACKAGE)], correlation_id=request["correlation_id"])

    def test_duplicate_requirements_fail_closed(self):
        request = load(REQUEST)
        requirement = dict(request["package_requirements"][0])
        request["package_requirements"].append(requirement)
        with self.assertRaises(ContextContractError):
            ContextAssembler().assemble(request, [load(PACKAGE)], correlation_id=request["correlation_id"])

    def test_package_mutation_fails_digest_revalidation(self):
        request = load(REQUEST)
        package = load(PACKAGE)
        package["items"][0]["payload"]["body"] = "tampered"
        with self.assertRaises(ContextContractError):
            ContextAssembler().assemble(request, [package], correlation_id=request["correlation_id"])

    def test_context_content_digest_is_verified(self):
        value = load(ROOT / "tests/fixtures/context/context-object-valid.json")
        value["context_content_digest"] = "0" * 64
        with self.assertRaises(ContextContractError):
            validate_context(value, ContextContractRegistry.built_in())


if __name__ == "__main__":
    unittest.main()
