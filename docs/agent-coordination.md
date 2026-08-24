# GitHub agent coordination protocol

VSS uses GitHub issues and pull requests as the durable coordination record for human,
ChatGPT, and Codex handoffs. This protocol reduces repeated prose; it does not create an agent,
workflow engine, identity system, or execution authority.

`AGENTS.md` remains repository guidance. Runtime remains the only capability/provider execution
authority. A GitHub checkpoint or approval record cannot authorize Runtime, a provider call,
production, publication, or workflow activation. Caller-supplied `recorded_by` is accountability
metadata, not authenticated or signed identity.

## Checkpoints

The strict contract is `schemas/agent-checkpoint-v1.schema.json`. Checkpoint types are:

- `design`: proposed architecture before implementation;
- `implementation`: implementation and test delta ready for review;
- `review`: adversarial review result;
- `blocked`: concise blocking condition and current evidence;
- `complete`: completed milestone evidence;
- `approval_record`: a human decision recorded against exact code and operation identities.

Every payload binds repository, branch, base SHA, HEAD SHA, bounded delta counts/paths, closed check
statuses, and constant-false authority fields. Changed paths are sorted and capped. `.local/**` and
credential-looking paths are omitted from payloads, but omission does not make them safe: only
`.local/secrets/development.auto.tfvars.example` is the repository-defined protected residue ignored
for approval worktree freshness. Any other dirty path, including another `.local/**` path, blocks an
approval record.

Comments use this envelope:

````text
<!-- vss-agent-checkpoint:v1 sha256=<canonical-payload-sha256> -->
```json
<canonical JSON payload>
```
````

The digest covers the exact canonical JSON bytes. Consumers validate the marker, digest, closed
contract, and—when freshness matters—current HEAD. Exact markers make repeated posting idempotent;
checkpoints remain immutable comments rather than mutable hidden state.

## Helper

`scripts/vss-agent` is a stdlib-only local helper. It reads bounded Git metadata and explicitly
supplied check outcomes. It never reads diffs or changed-file contents, executes tests, invokes VSS
Runtime/providers, merges, pushes, or interprets GitHub approval as execution permission.

Emit a local checkpoint without network access:

```bash
scripts/vss-agent checkpoint \
  --target issue:90 \
  --type implementation \
  --base 0694824cf3adea03c90762483342811808c41cbb \
  --summary 'Implementation ready for adversarial review.' \
  --check focused-tests=passed
```

Add `--post` only when authorized to write a GitHub issue/PR comment. Pull requests use
`--target pr:<number>`. Posting validates first, calls `gh` with fixed argument vectors, fetches
existing comments, and posts only if the exact marker is absent.

Record coordination approval metadata only from a clean code worktree:

```bash
scripts/vss-agent approval \
  --target issue:90 \
  --scope effectful_operation \
  --operation-digest <64-lowercase-hex> \
  --decision approved \
  --recorded-by <accountability-id>
```

Approval scopes are closed: `paid_provider_attempt`, `effectful_operation`, `merge`, and `push`.
The record binds current HEAD and the operation digest. Any HEAD change makes it stale. It still
grants no Runtime or provider authority; effectful systems must perform their own admission and
authorization through existing boundaries.

Validate raw payload JSON or a complete comment envelope:

```bash
scripts/vss-agent validate --input checkpoint.txt
scripts/vss-agent validate --input checkpoint.txt --require-current-head
```

Malformed, oversized, secret-looking, ambiguous, stale, detached-HEAD, unsupported-origin, or
unexpected-dirty states fail closed with bounded diagnostics.

## Harness v2 routing and validation

`config/agent-harness-v2.json` is the strict repository-owned navigation and impact map. It contains
closed domain IDs, authoritative documentation/code/test paths, ordered exact-or-prefix impact
rules, and validation profiles expressed only as fixed argument vectors. It is configuration, not
executable authority: callers cannot supply commands, shell expressions, imports, or fallback
profiles.

Route a disposable session to paths without reading source contents:

```bash
scripts/vss-agent context --domain agent-coordination --domain security
```

Plan the current change against an explicit ancestor:

```bash
scripts/vss-agent impact --base <base-sha>
```

The plan deterministically unions every matching rule. Validation levels are `L0` for bounded
syntax/schema/diff checks, `L1` for direct domain tests, `L2` for declared architecture/security
dependencies, and `L3` for the canonical `scripts/validate-change.sh` repository gate. Lower levels
speed up inner-loop work; L3 is always required for merge readiness. Unknown paths and changes to
the map, helper, schemas, CI, or validation machinery fail closed to at least `shared` risk and L3.

Risks are closed and ordered: `docs`, `isolated`, `shared`, `external-effect`, and
`paid-authority`. Risk can only increase required validation, review, or human gates. It never
authorizes Runtime, providers, payment, merge, or push. Existing explicit Runtime/provider
authorization remains mandatory.

Run the selected fixed profiles and write compact proof-carrying evidence:

```bash
scripts/vss-agent validate-change --base <base-sha> --level L3 --output /tmp/evidence.json
scripts/vss-agent evidence --input /tmp/evidence.json --require-current-change
```

Successful evidence contains no command logs. It binds the repository, branch, base and HEAD SHA,
canonical map digest, exact tracked diff plus bounded untracked-content identity, selected plan,
fixed profile IDs, and pass results. Any HEAD, map, or worktree change makes it stale. Unexpected
`.local/**`, sensitive-looking, or unclassified paths are not silently omitted; only
`.local/secrets/development.auto.tfvars.example` retains its narrow protected-residue exception.
Failure output is bounded and written only as diagnostic material.
Evidence output paths must be absolute and outside the repository so writing evidence cannot make
the evidence stale or turn a local artifact into repository authority.

A reset session reconstructs state from the GitHub issue or PR, `AGENTS.md`, requested domain IDs,
router output, and the latest fresh checkpoint/evidence digest. Hidden agent memory and local
evidence files are never authoritative.

## Short handoff workflow

1. Human or ChatGPT creates the milestone issue: `Work issue #N`.
2. Codex reads `AGENTS.md`, this protocol, and the issue, then posts a `design` checkpoint.
3. After issue review, Codex implements and posts `implementation`: user says `Continue #N`.
4. ChatGPT fetches and validates the checkpoint: user says `Check #N`.
5. Once a PR exists, subsequent checkpoints target the PR rather than duplicating issue prose.
6. Human approvals are recorded as SHA/operation-bound metadata; actual effects still require their
   normal explicit authorization and Runtime policy.

Use verbose prose only for exceptions, blocking evidence, or material design changes. Normal
handoffs should be the marker, canonical payload, and at most a short human-readable sentence.
