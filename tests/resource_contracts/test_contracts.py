import copy
import unittest

from vss_resource_admission import create_production_artifact, create_universe_admission
from vss_resource_contracts import (
    ResourceContractError,
    ResourceContractRegistry,
    validate_production_resource_artifact,
    validate_reusable_asset_admission,
)


CONTENT = b"\x89PNG\r\n\x1a\nreview-frame"


def artifact(**overrides):
    values = dict(
        resource_revision=1,
        tenant_id="tenant-one", universe_id="universe-one", production_id="production-one",
        activity_id="activity-one", content=CONTENT, ownership_class="customer_owned",
        rights_status="confirmed",
        permissions=["use_in_source_production", "reuse_as_universe_visual_reference"],
        restrictions=["no_training", "no_redistribution", "no_publication"],
        rights_reference="rights-reference-one",
    )
    values.update(overrides)
    return create_production_artifact(**values)


class ResourceContractTests(unittest.TestCase):
    def test_registry_is_exact_and_deterministic(self):
        first = ResourceContractRegistry.built_in()
        second = ResourceContractRegistry.built_in()
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(3, len(first.registrations))
        for invalid in ("reusable_asset/latest", "reusable_asset/*", "unknown/1"):
            with self.assertRaises(ResourceContractError):
                first.resolve(invalid)

    def test_artifact_is_immutable_and_not_an_asset(self):
        value = artifact()
        self.assertEqual("production_resource_artifact", value.value["contract_identity"])
        self.assertNotIn("asset_id", value.value)
        with self.assertRaises(TypeError):
            value.value["resource_revision"] = 2

    def test_content_and_resealed_tampering_fail(self):
        value = artifact()
        with self.assertRaisesRegex(ResourceContractError, "content digest"):
            validate_production_resource_artifact(value.to_json_value(), content=b"changed")
        tampered = value.to_json_value()
        tampered["resource_revision"] = 2
        with self.assertRaisesRegex(ResourceContractError, "identity mismatch"):
            validate_production_resource_artifact(tampered, content=CONTENT)

    def test_extra_nested_fields_and_malformed_values_fail(self):
        value = artifact().to_json_value()
        value["scope"]["storage_path"] = "/tmp/frame.png"
        with self.assertRaises(ResourceContractError):
            validate_production_resource_artifact(value)
        for field, invalid in (("resource_id", "latest"), ("content_sha256", "abcd"),
                               ("resource_revision", 0)):
            with self.subTest(field=field):
                value = artifact().to_json_value()
                value[field] = invalid
                with self.assertRaises(ResourceContractError):
                    validate_production_resource_artifact(value)

    def test_unknown_and_conflicting_rights_are_valid_facts(self):
        for status in ("unknown", "conflicting"):
            with self.subTest(status=status):
                self.assertEqual(status, artifact(rights_status=status).value["rights"]["status"])

    def test_admission_contract_rejects_open_fields_and_bad_seal(self):
        source = artifact()
        admission = create_universe_admission(
            source_artifact=source, destination_tenant_id="tenant-one",
            destination_universe_id="universe-one")
        value = admission.to_json_value()
        value["destination"]["path"] = "shared/frame.png"
        with self.assertRaises(ResourceContractError):
            validate_reusable_asset_admission(value)
        value = admission.to_json_value()
        value["source"]["resource_revision"] = 2
        with self.assertRaisesRegex(ResourceContractError, "identity mismatch"):
            validate_reusable_asset_admission(value)

    def test_ancestor_duplicates_and_order_fail(self):
        ancestor_a = {"resource_id": "resource-" + "a" * 32, "resource_revision": 1,
                      "content_sha256": "a" * 64}
        ancestor_b = {"resource_id": "resource-" + "b" * 32, "resource_revision": 1,
                      "content_sha256": "b" * 64}
        value = artifact(ancestors=[ancestor_a, ancestor_b]).to_json_value()
        duplicate = copy.deepcopy(value)
        duplicate["lineage"]["ancestors"] = [ancestor_a, ancestor_a]
        with self.assertRaises(ResourceContractError):
            validate_production_resource_artifact(duplicate)


if __name__ == "__main__":
    unittest.main()
