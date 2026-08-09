# Architecture Entropy Ledger

## Purpose and cadence

This ledger makes architecture growth visible without pretending that
complexity is one number. It is updated only at a major integration checkpoint,
new architectural plane, major persistent subsystem, major domain-family
expansion, Strategic Review, or explicit complexity concern—not on ordinary
feature pull requests.

Counts are evidence prompts, not targets. Growth may be correct when it
represents an independent vocabulary, lifecycle, authority, provenance,
ownership, workload, or security boundary. A higher count never proves a
problem, and a lower count never proves safety. There is deliberately no
aggregate entropy score.

Each snapshot records its counting definitions. Later snapshots must retain or
explicitly revise those definitions before claiming a trend.

## Snapshot fields

Every snapshot records:

- reviewed main SHA and milestone/checkpoint;
- objectively available counts and their source/definition;
- additions and removals since the comparable snapshot;
- meaningful complexity increase and meaningful simplification;
- qualitative pressure (`LOW`, `WATCH`, or `HIGH`);
- retirement and framework candidates; and
- decision: `ACCEPTABLE`, `WATCH`, or
  `SIMPLIFY_BEFORE_NEXT_MAJOR_EXPANSION`.

Tracked quantitative categories, when applicable, are contract families and
versions, Context families/versions, registries, strategy/provider families,
persistent components/services, authority-bearing concepts, first-party
packages, cross-domain dependency exceptions, major public semantic execution
paths, review exceptions/deviations, framework candidates, and retirement
candidates.

Tracked qualitative pressures are Gateway, Registry, versioning, operational,
cognitive, domain coupling, CI/test, and governance overhead.

## Baseline: post-M5 integration checkpoint

- **Reviewed main:** `002d8a5323aea4ec082c80ce9648abaa8da4286c`
- **Checkpoint:** accepted M5 Character Continuity and Semantic Engine
  Integration Checkpoint
- **Decision:** `WATCH`

### Evidence counts

| Category | Baseline | Definition and evidence |
|---|---:|---|
| Non-Context contract registration records | 16 | Movie 14 + Semantic 1 + Knowledge 1 repository-owned registration records; not a count of every envelope nested inside a registration |
| Movie contract families / registered versions | 12 / 14 | Family is the exact identity before the terminal version; task `analyze_character_continuity` has three versions |
| Context families / registered versions | 7 / 8 | Context Registry entries; Character Continuity has Context v1 and v2 |
| Federated contract registries | 4 | Semantic, Knowledge, Context, and Movie Contract Registries |
| Versioned semantic strategy/provider paths | 5 | Generate Options, Scene Breakdown, Scene Production Options, Character Continuity 1.0, and Character Continuity 1.1 |
| Major public semantic execution paths | 5 | Same versioned behavior paths as above; several may share one public Gateway method |
| First-party Python packages | 20 | Top-level `src/vss_*` directories at the reviewed SHA |
| Mandatory external persistent services | 0 | Baseline VSS operation requires no DB server, broker, cache daemon, model server, or distributed service |
| Authority-bearing concepts | 2 | Runtime capability authorization/execution admission and retained human creative/production authority; semantic components add none |
| Cross-domain dependency exceptions | 1 | Documented legacy Workflow → CommandRunner adapter protected by architecture tests |
| Current framework candidates | 1 | Semantic evidence validation → Context projection → provider projection → result-binding pattern |
| Current retirement candidates | 0 | No removal justified; historical contracts are not retirement candidates merely because they are old |
| Accepted review deviations/exceptions | 1 | The explicit legacy dependency exception above; deferred future work is not counted as a deviation |

These are scoped counts, not claims that all categories have identical cost.
Capability, provider, workflow, and revocation registries remain separately
governed and should be counted in a later snapshot only under a stated stable
definition if total registry surface becomes a decision concern.

### Change and pressure

| Dimension | Pressure | Evidence |
|---|---|---|
| Gateway complexity | `WATCH` | Semantic-only boundary remains sound, but lifecycle/audit adapter repetition has grown to three movie adapters and versioned continuity dispatch |
| Registry complexity | `LOW` | Exact static lookup remains small, federated, immutable, and ownership-aligned |
| Versioning complexity | `LOW` | M5 versions reflect genuine semantic incompatibility and preserve historical interpretation |
| Operational complexity | `LOW` | No new persistent component or mandatory service through M5 |
| Cognitive complexity | `WATCH` | Exact digest domains and task/Context/catalogue cross-products require careful review and documentation |
| Domain coupling | `LOW` | Architecture dependency tests preserve boundaries; one legacy exception is explicit |
| CI/test complexity | `WATCH` | More than 419 Python tests plus duplicated public/full validation paths; evidence is valuable but layering should be monitored |
| Governance overhead | `WATCH` | Detailed M5 reviews found real defects, but review instructions and reports are becoming large |

- **Meaningful increase:** Character Continuity added exact task, Context,
  catalogue, evidence, and implementation versions plus Gateway adapter surface.
- **Meaningful simplification:** no separate service, database, general rules
  engine, Plan IR, Asset/Compute subsystem, or second continuity path was added.
- **Pressure areas:** Gateway lifecycle duplication, semantic version
  cross-products, CI layering, and review cognitive load.
- **Decision rationale:** current growth is justified and bounded, but the next
  major semantic family must reassess Gateway and governance repetition before
  adding framework machinery.

## Snapshot template

| Field | Entry |
|---|---|
| Reviewed main / checkpoint | |
| Comparable prior snapshot | |
| Additions / removals | |
| Meaningful complexity increase | |
| Meaningful simplification | |
| Quantitative evidence and definitions | |
| Pressure table | |
| Framework candidates | |
| Candidates for Removal | `None` is valid |
| Things deliberately not built | item, reason, reconsideration trigger |
| Decision | `ACCEPTABLE`, `WATCH`, or `SIMPLIFY_BEFORE_NEXT_MAJOR_EXPANSION` |
