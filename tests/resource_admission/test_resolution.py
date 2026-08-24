import unittest

from vss_reasoning_contracts import canonical_digest
from vss_resource_admission import (
    admit_storyboard_frame_to_universe,
    create_production_artifact,
    create_resource_resolution_request,
    create_universe_admission,
    resolve_universe_visual_reference,
)
from vss_resource_contracts import (
    asset_identity_material,
    asset_seal_material,
    resolution_request_identity_material,
    resolution_request_seal_material,
    validate_reusable_asset,
    validate_resource_resolution_request,
    validate_resource_resolution_result,
)
from tests.resource_test_support import admitted_pictorial_frame, pictorial_png


CONTENT = pictorial_png()


def authoritative_chain(*, restrictions=None):
    source = create_production_artifact(
        pictorial_frame=admitted_pictorial_frame(), resource_revision=1,
        tenant_id="tenant-one", universe_id="universe-one", content=CONTENT,
        ownership_class="customer_owned", rights_status="confirmed",
        permissions=["use_in_source_production", "reuse_as_universe_visual_reference"],
        restrictions=restrictions or ["no_training", "no_redistribution", "no_publication"],
        rights_reference="rights-reference-one",
    )
    admission = create_universe_admission(
        source_artifact=source, destination_tenant_id="tenant-one",
        destination_universe_id="universe-one")
    admitted = admit_storyboard_frame_to_universe(
        source, source_content=CONTENT, admission_request=admission)
    assert admitted.admitted
    return source, admission, admitted.asset


def request(source, admission, asset, **overrides):
    values = dict(
        source_artifact=source, admission=admission, asset=asset, source_content=CONTENT,
        tenant_id="tenant-one", universe_id="universe-one", production_id="production-two",
    )
    values.update(overrides)
    return create_resource_resolution_request(**values)


def resolve(source, admission, asset, resolution_request, **overrides):
    values = dict(
        source_artifact=source, admission=admission, asset=asset, source_content=CONTENT,
        request=resolution_request, tenant_id="tenant-one", universe_id="universe-one",
        production_id="production-two",
    )
    values.update(overrides)
    return resolve_universe_visual_reference(**values)


def reseal_request(value):
    value["request_id"] = "resource-resolution-" + canonical_digest(
        resolution_request_identity_material(value))[:32]
    value["request_sha256"] = canonical_digest(resolution_request_seal_material(value))
    return validate_resource_resolution_request(value)


class ResourceResolutionTests(unittest.TestCase):
    def test_real_upstream_resolution_is_deterministic_inert_and_preserves_lineage(self):
        source, admission, asset = authoritative_chain()
        resolution_request = request(source, admission, asset)
        first = resolve(source, admission, asset, resolution_request)
        second = resolve(source, admission, asset, resolution_request)
        self.assertTrue(first.resolved)
        self.assertEqual("resolved", first.code)
        self.assertEqual(first.resource.to_json_value(), second.resource.to_json_value())
        result = first.resource.value
        self.assertEqual(asset.value["source"], result["source"])
        self.assertEqual(asset.value["admission"], result["admission"])
        self.assertEqual(list(asset.value["rights"]["restrictions"]),
                         list(result["rights"]["restrictions"]))
        self.assertEqual("reuse_as_universe_visual_reference", result["rights"]["permission"])
        self.assertIn("not_runtime_authority", result["limitations"])
        validate_resource_resolution_result(
            first.resource.to_json_value(), request=resolution_request,
            source_artifact=source, admission=admission, asset=asset,
            source_content=CONTENT)

    def test_consumer_scope_tenant_universe_and_purpose_are_exact(self):
        source, admission, asset = authoritative_chain()
        resolution_request = request(source, admission, asset)
        self.assertEqual("consumer_scope_mismatch", resolve(
            source, admission, asset, resolution_request,
            production_id="production-three").code)
        cross_tenant = request(source, admission, asset, tenant_id="tenant-two")
        self.assertEqual("tenant_mismatch", resolve(
            source, admission, asset, cross_tenant, tenant_id="tenant-two").code)
        cross_universe = request(source, admission, asset, universe_id="universe-two")
        self.assertEqual("universe_mismatch", resolve(
            source, admission, asset, cross_universe, universe_id="universe-two").code)
        self.assertEqual("purpose_mismatch", resolve(
            source, admission, asset, resolution_request, purpose="production_texture").code)

    def test_validly_resealed_request_substitutions_fail_against_authoritative_asset(self):
        source, admission, asset = authoritative_chain()
        value = request(source, admission, asset).to_json_value()
        value["asset"]["asset_id"] = "asset-" + "f" * 32
        substituted = reseal_request(value)
        self.assertEqual("authoritative_binding_mismatch", resolve(
            source, admission, asset, substituted).code)
        value = request(source, admission, asset).to_json_value()
        value["source"]["resource_revision"] = 2
        self.assertEqual("authoritative_binding_mismatch", resolve(
            source, admission, asset, reseal_request(value)).code)

    def test_validly_resealed_asset_substitution_cannot_become_authoritative(self):
        source, admission, asset = authoritative_chain()
        value = asset.to_json_value()
        value["rights"]["rights_reference"] = "rights-reference-two"
        value["asset_id"] = "asset-" + canonical_digest(asset_identity_material(value))[:32]
        value["asset_sha256"] = canonical_digest(asset_seal_material(value))
        with self.assertRaisesRegex(Exception, "authoritative rights mismatch"):
            validate_reusable_asset(value, source_artifact=source, admission=admission,
                                    source_content=CONTENT)

    def test_missing_or_wrong_admission_and_tampered_result_fail(self):
        source, admission, asset = authoritative_chain()
        resolution_request = request(source, admission, asset)
        self.assertEqual("invalid_authoritative_chain", resolve_universe_visual_reference(
            source_artifact=source, admission=object(), asset=asset, source_content=CONTENT,
            request=resolution_request, tenant_id="tenant-one", universe_id="universe-one",
            production_id="production-two").code)
        result = resolve(source, admission, asset, resolution_request).resource.to_json_value()
        result["rights"]["rights_reference"] = "rights-reference-two"
        with self.assertRaisesRegex(Exception, "authoritative binding mismatch"):
            validate_resource_resolution_result(
                result, request=resolution_request, source_artifact=source,
                admission=admission, asset=asset, source_content=CONTENT)

    def test_rights_restrictions_and_exact_revision_fail_closed(self):
        source, admission, asset = authoritative_chain(restrictions=["no_training"])
        resolution_request = request(source, admission, asset)
        value = resolution_request.to_json_value()
        value["restrictions"] = []
        self.assertEqual("authoritative_binding_mismatch", resolve(
            source, admission, asset, reseal_request(value)).code)
        value = resolution_request.to_json_value()
        value["asset"]["asset_revision"] = 2
        self.assertEqual("authoritative_binding_mismatch", resolve(
            source, admission, asset, reseal_request(value)).code)


if __name__ == "__main__":
    unittest.main()
