import copy
import unittest

from vss_reasoning_contracts import canonical_digest
from vss_resource_admission import (
    admit_storyboard_frame_to_universe,
    create_production_artifact,
    create_universe_admission,
)
from vss_resource_contracts import (
    admission_identity_material,
    admission_seal_material,
    validate_reusable_asset,
    validate_reusable_asset_admission,
)


CONTENT = b"\x89PNG\r\n\x1a\nreview-frame"


def source(**overrides):
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


def request(item, **overrides):
    values = dict(source_artifact=item, destination_tenant_id="tenant-one",
                  destination_universe_id="universe-one")
    values.update(overrides)
    return create_universe_admission(**values)


def reseal(value):
    value["admission_id"] = "asset-admission-" + canonical_digest(
        admission_identity_material(value))[:32]
    value["admission_sha256"] = canonical_digest(admission_seal_material(value))
    return validate_reusable_asset_admission(value)


class ResourceAdmissionServiceTests(unittest.TestCase):
    def test_complete_promotion_is_deterministic_and_bounded(self):
        item = source()
        admission = request(item)
        first = admit_storyboard_frame_to_universe(item, source_content=CONTENT,
                                                   admission_request=admission)
        second = admit_storyboard_frame_to_universe(item, source_content=CONTENT,
                                                    admission_request=admission)
        self.assertTrue(first.admitted)
        self.assertEqual("admitted", first.code)
        self.assertEqual(first.asset.digest, second.asset.digest)
        self.assertEqual(first.asset.to_json_value(), second.asset.to_json_value())
        value = first.asset.value
        self.assertEqual(["reuse_as_universe_visual_reference"], list(value["rights"]["permissions"]))
        self.assertEqual(list(item.value["rights"]["restrictions"]), list(value["rights"]["restrictions"]))
        self.assertEqual(item.value["artifact_sha256"], value["source"]["artifact_sha256"])
        validate_reusable_asset(first.asset.to_json_value())

    def test_changed_content_and_non_admission_do_not_promote(self):
        item = source()
        self.assertEqual("invalid_source_artifact", admit_storyboard_frame_to_universe(
            item, source_content=b"copied-but-changed", admission_request=request(item)).code)
        self.assertEqual("invalid_admission", admit_storyboard_frame_to_universe(
            item, source_content=CONTENT, admission_request=item.to_json_value()).code)

    def test_same_bytes_do_not_cross_tenant_or_universe(self):
        item = source()
        cross_tenant = request(item, destination_tenant_id="tenant-two")
        self.assertEqual("tenant_mismatch", admit_storyboard_frame_to_universe(
            item, source_content=CONTENT, admission_request=cross_tenant).code)
        cross_universe = request(item, destination_universe_id="universe-two")
        self.assertEqual("universe_mismatch", admit_storyboard_frame_to_universe(
            item, source_content=CONTENT, admission_request=cross_universe).code)
        other_tenant_source = source(tenant_id="tenant-two")
        self.assertEqual(item.value["content_sha256"], other_tenant_source.value["content_sha256"])
        self.assertNotEqual(item.value["artifact_id"], other_tenant_source.value["artifact_id"])

    def test_standalone_production_cannot_promote(self):
        item = source(universe_id=None)
        admission = request(item)
        self.assertEqual("source_has_no_universe", admit_storyboard_frame_to_universe(
            item, source_content=CONTENT, admission_request=admission).code)

    def test_source_revision_and_resealed_substitution_fail(self):
        item = source()
        value = request(item).to_json_value()
        value["source"]["resource_revision"] = 2
        substituted = reseal(value)
        self.assertEqual("source_binding_mismatch", admit_storyboard_frame_to_universe(
            item, source_content=CONTENT, admission_request=substituted).code)

    def test_changed_content_cannot_be_resealed_under_old_logical_identity(self):
        item = source()
        changed = item.to_json_value()
        changed["content_sha256"] = "f" * 64
        from vss_resource_contracts import artifact_seal_material, validate_production_resource_artifact
        changed["artifact_sha256"] = canonical_digest(artifact_seal_material(changed))
        with self.assertRaisesRegex(Exception, "logical identity mismatch"):
            validate_production_resource_artifact(changed)

    def test_rights_fail_closed(self):
        cases = [
            (source(rights_status="unknown"), "rights_not_confirmed"),
            (source(rights_status="conflicting"), "rights_not_confirmed"),
            (source(permissions=["use_in_source_production"]), "permission_not_granted"),
            (source(restrictions=["no_reuse"]), "reuse_restricted"),
        ]
        for item, code in cases:
            with self.subTest(code=code):
                self.assertEqual(code, admit_storyboard_frame_to_universe(
                    item, source_content=CONTENT, admission_request=request(item)).code)

    def test_validly_resealed_rights_and_restriction_substitutions_fail(self):
        item = source()
        value = request(item).to_json_value()
        value["rights_reference"] = "rights-reference-two"
        self.assertEqual("rights_reference_mismatch", admit_storyboard_frame_to_universe(
            item, source_content=CONTENT, admission_request=reseal(value)).code)
        value = request(item).to_json_value()
        value["carried_restrictions"] = ["no_training"]
        self.assertEqual("restriction_mismatch", admit_storyboard_frame_to_universe(
            item, source_content=CONTENT, admission_request=reseal(value)).code)

    def test_asset_lineage_tampering_fails_even_when_source_content_matches(self):
        item = source(ancestors=[{
            "resource_id": "resource-" + "a" * 32, "resource_revision": 1,
            "content_sha256": "a" * 64,
        }])
        result = admit_storyboard_frame_to_universe(item, source_content=CONTENT,
                                                    admission_request=request(item))
        value = result.asset.to_json_value()
        value["source"]["ancestors"][0]["resource_revision"] = 2
        with self.assertRaises(Exception):
            validate_reusable_asset(value)


if __name__ == "__main__":
    unittest.main()
