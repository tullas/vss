# Versioned movie canon binding

M9.3 implements one deterministic, in-memory path that turns the existing
scene-production-option review decision into an immutable creative-decision
revision, admits exact accepted revisions into a production-context canon
snapshot, and binds that snapshot to the exact scene shot-plan input lineage.
The canonical `vss movie demo` path returns all three artifacts after its human
option acceptance.

## Contracts and identity

`creative_decision_revision/1` represents only a scene production-option
selection. Its logical decision ID is reconstructed from the exact tenant,
universe, production, scene, and decision kind. Its revision-specific seal
binds status, the selected option and content digest, complete review decision,
review packet, option set, scene breakdown and scene-content digests, sorted
evidence and dependencies, and the exact prior revision when present. Reviewer
ID is accountability metadata supplied by the caller; VSS does not authenticate
or verify that identity.

`canon_snapshot/1` is an immutable production-context set of exact accepted
decision IDs, revisions, seals, statuses, and scene IDs. Snapshot identity
includes its explicit version, scope, and complete canonical decision set.
There is no mutable global canon, name lookup, or `latest` resolution.

`production_canon_binding/1` preserves the exact snapshot and decision-revision
bindings plus the selected option, review decision, review packet, option set,
scene breakdown, and scene-content lineage used as a scene shot-plan input.
It is an inert result, not execution admission.

All three use strict, bounded Draft 2020-12 schemas with closed nested objects.
IDs and SHA-256 seals reuse the VSS canonical JSON digest convention. Validators
reconstruct identities, ordering, scope, revision predecessor rules, and seals.
The binding service reconstructs the real upstream movie decision rather than
trusting a validly resealed caller artifact.

## Local API

```python
from vss_movie_canon import (
    bind_production_input_to_canon,
    create_canon_snapshot,
    create_creative_decision_revision,
)

decision_revision = create_creative_decision_revision(
    review_decision, review_packet, option_set, scene_breakdown,
    tenant_id="tenant-one", universe_id="universe-one", revision=1,
)
snapshot = create_canon_snapshot(decisions=[decision_revision], snapshot_version=1)
binding = bind_production_input_to_canon(
    review_decision, review_packet, option_set, scene_breakdown,
    tenant_id="tenant-one", universe_id="universe-one",
    decisions=[decision_revision], canon_snapshot=snapshot,
)
```

Only `accepted` revisions enter a snapshot or binding. Rejected, deprecated,
and superseded revisions fail closed. A later revision binds its exact immediate
predecessor and creates new seals and snapshot identity; existing Python values
remain frozen and historical snapshots and bindings are unchanged.

Tenant, universe, production, and scene scope must match exactly. Equal content,
possession, or knowledge of an identity grants no cross-scope use. The artifacts
grant no production approval, Runtime/provider execution, workflow activation,
scheduling, regeneration, storage, publication, rights, ownership, reuse,
training, or cross-tenant authority.

## Bounded dependency-impact assessment

M9.4 adds `dependency_impact_request/1`, `dependency_impact_result/1`, and the
in-process `assess_production_binding_impact` API. A request pins one exact
historical production binding, its canon snapshot and selected decision, plus
one explicitly supplied candidate canon/decision state. The API reconstructs
the historical binding and both real movie review-to-canon chains before it
compares the exact decision identity/revision/seal and canon
identity/version/seal.

An exact match is `unaffected`; an in-scope changed pin is
`affected_reassessment_required`; missing, inconsistent, ambiguous, or
cross-scope evidence is `incomplete_fail_closed` or a closed malformed-contract
rejection. Results contain bounded exact evidence and are deterministic and
immutable. Assessment never changes the historical artifacts. “Affected” is
only a reassessment signal and grants no authority to invalidate, regenerate,
delete, schedule, execute, publish, store, or change rights.

## Limitations

This slice supports one explicitly supplied scene option decision and a bounded
production-context snapshot. It has no database, registry of decisions, lookup,
mutable canon service, dependency traversal beyond the one selected binding,
multi-hop or persistent impact analysis, regeneration,
multi-production universe canon, authentication, UI, rights adjudication,
Runtime/provider call, persistence, publication, BOM/export, or cross-tenant
sharing. The demo uses explicit local scope labels `tenant-local` and
`universe-local`; they are not authenticated principals.
