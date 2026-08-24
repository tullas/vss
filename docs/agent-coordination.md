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
