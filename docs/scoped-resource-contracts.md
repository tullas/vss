# Scoped immutable resource contracts

M9.1 implements one inert local promotion path from an exact production
storyboard review-frame artifact to a reusable visual-reference asset in that
production's parent universe. It is intentionally not an asset catalog,
resolver, rights registry, legal engine, storage abstraction, or execution
path.

M9.2 adds one exact deterministic resolution path that lets a named production
consume that already-admitted universe visual reference as an inert resolution
artifact. It does not add lookup, discovery, storage, or execution.

M9.3 reuses this contract registry and canonical integrity convention for one
versioned movie creative-decision, production-context canon snapshot, and exact
production-input binding. See [Versioned movie canon binding](movie-canon-binding.md).

## Contracts

`production_resource_artifact/1` records an immutable PNG output with exact
tenant, optional universe, required production, activity, revision, content,
rights facts, and ancestor lineage. Its logical resource ID is reconstructed
from its exact kind, scope, activity, media type, and content digest. Changed
content therefore cannot retain the old logical identity even if a caller
recomputes the artifact seal. An artifact contains no reusable-asset status.

`reusable_asset_admission/1` is a separate exact admission for
`admit_storyboard_review_frame_as_universe_visual_reference/1`. It binds the
source artifact ID, logical resource/revision, artifact seal, content digest,
production scope, destination tenant/universe, purpose, rights facts,
restrictions, and policy version.

`reusable_asset/1` is created only by successful deterministic adjudication.
It retains exact production/activity/ancestor lineage, the admission binding,
the one admitted permission, all surviving restrictions, and explicit inert
authority limitations.

`resource_resolution_request/1` binds an exact consumer tenant, universe, and
production; the sole visual-reference purpose and permission; the exact asset
identity, revision, seal, and content digest; the exact upstream production
resource and admission identities; and the admitted rights reference and
restrictions. `resource_resolution_result/1` preserves that request binding,
the resolved asset identity, full source activity and ancestor lineage,
admission policy evidence, rights facts, and explicit inert limitations.

All resource contracts are bounded Draft 2020-12 schemas with closed nested
objects, exact versions, closed enums, and no `latest` input identity.
Canonical SHA-256 digests reuse the existing VSS canonical JSON convention.
Digests are integrity evidence, not ownership, access, promotion, or execution
authority.

## Local API

```python
from vss_resource_admission import (
    admit_storyboard_frame_to_universe,
    create_production_artifact,
    create_universe_admission,
)

artifact = create_production_artifact(
    pictorial_frame=authoritatively_admitted_pictorial_frame,
    resource_revision=1,
    tenant_id="tenant-one",
    universe_id="universe-one",
    content=png_bytes,
    ownership_class="customer_owned",
    rights_status="confirmed",
    permissions=["reuse_as_universe_visual_reference"],
    restrictions=["no_training", "no_redistribution", "no_publication"],
    rights_reference="rights-reference-one",
)
admission = create_universe_admission(
    source_artifact=artifact,
    destination_tenant_id="tenant-one",
    destination_universe_id="universe-one",
)
result = admit_storyboard_frame_to_universe(
    artifact, source_content=png_bytes, admission_request=admission,
)
```

Artifact construction requires the unforgeable `AdmittedPictorialFrame` from
the real movie path and independently applies the established strict pictorial
PNG validator. Production, storyboard, frame, and semantic-request bindings
come from that admitted object rather than caller labels. The service
independently revalidates the source and reconstructs its content digest before
comparing the exact admission binding. Asset validation also requires and
revalidates the independently admitted source and admission artifacts; it does
not authorize a candidate from its own resealed JSON. Identical authoritative
inputs produce identical IDs, seals, assets, and result codes. There are no
timestamps, UUIDs, filesystem paths, storage identifiers, provider calls,
Runtime calls, persistence, workflow activation, or global mutable state.

## Admission rules

Admission succeeds only when:

- source, request, and destination tenants match exactly;
- the destination universe is the source production's explicit parent
  universe (standalone productions cannot use this promotion);
- every source identity, revision, seal, content digest, and production binding
  matches the independently validated artifact;
- rights status is `confirmed`, the exact rights reference is preserved, and
  `reuse_as_universe_visual_reference` is positively granted;
- `no_reuse` is absent; and
- all source restrictions are carried exactly. The admitted permission is the
  intersection of the sole requested permission and source permissions.

`unknown` or `conflicting` rights fail closed. `no_training`,
`no_redistribution`, and `no_publication` survive promotion. Copying bytes,
matching a digest, physical co-location, access, or identifier knowledge does
not create admission or cross-scope/cross-tenant authority.

Rejected adjudications return a closed deterministic code and no asset. The
contracts and service grant no Runtime, provider, production approval,
publication, redistribution, training, ownership, or workflow authority.

## Exact production resolution

`create_resource_resolution_request` and
`resolve_universe_visual_reference` operate only on explicitly supplied,
validated M9.1 source, admission, and asset artifacts. The resolver
independently reconstructs that entire chain and the source content digest,
then requires the request to match the caller-supplied consumer tenant,
universe, production, and purpose. A validly resealed request cannot substitute
another asset, resource revision, admission, rights reference, or restriction.
The consumer production identifier is an exact scope label, not authenticated
identity or production approval.

Success returns a deterministic `resource_resolution_result/1`; failure
returns a closed code and no resource. Resolution invokes no provider or
Runtime, reads no path or mutable catalog, persists nothing, and activates no
workflow. The result grants no storage, publication, redistribution, training,
ownership, provider, Runtime, scheduling, or cross-scope authority.

## Limitations

Only one PNG review-frame to universe visual-reference admission and exact
production resolution path exists. Callers must already possess and explicitly
supply the authoritative artifact chain and bytes; there is no lookup.
Other
resource types, production-only admissions, cross-tenant transactions,
revocation propagation, catalogs, persistence, lookup, authentication, legal
interpretation, canon/BOM export, storage, publication, and effectful execution
remain deferred.
