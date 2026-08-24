# Scoped immutable resource contracts

M9.1 implements one inert local promotion path from an exact production
storyboard review-frame artifact to a reusable visual-reference asset in that
production's parent universe. It is intentionally not an asset catalog,
resolver, rights registry, legal engine, storage abstraction, or execution
path.

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

All three contracts are bounded Draft 2020-12 schemas with closed nested
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

## Limitations

Only one PNG review-frame to universe visual-reference path exists. Other
resource types, production-only admissions, cross-tenant transactions,
revocation propagation, catalogs, persistence, lookup, authentication, legal
interpretation, canon/BOM export, storage, publication, and effectful execution
remain deferred.
