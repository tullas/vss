# VSS Repository Guidance

## Repository intent

VSS targets a working AI-assisted movie/story production platform. Prefer executable vertical
slices over architecture-only scaffolding, speculative abstractions, or governance without value.

A milestone needs meaningful executable behavior and automated tests. Schemas
and interfaces alone do not make it complete.

## Inspect before implementing

Before significant implementation:

- Inspect the current branch and `git status --short`.
- Inspect the relevant implementation, contracts, tests, ADRs, and docs.
- Reuse existing architecture and conventions.
- Identify the smallest complete vertical slice.

Extend existing VSS components; do not invent parallel frameworks.

## Contract discipline

For governed artifacts:

- Use strict JSON Schema and `additionalProperties: false` where appropriate.
- Require exact fields and closed enums; bound arrays, strings, IDs, and digests.
- Avoid open nested objects; register exact task/result compatibility.
- Update pinned registry digests and use canonical VSS integrity conventions.

Do not trust caller-supplied digests when validated upstream artifacts allow
authoritative content to be reconstructed. Resealing tampered content must not
legitimize unauthorized substitution.

## Determinism

Identical authoritative inputs and parameters must produce identical semantic output. Timestamps,
UUIDs, randomness, paths, unordered iteration, audit metadata, and global state must not influence it.
Audit metadata may be nondeterministic only where existing conventions permit.

## Authority boundaries

Keep semantic and review artifacts separate from operational authority:

- Review acceptance is not production approval.
- Draft artifacts are not final selections.
- Semantic artifacts grant no scheduling or workflow-activation authority.
- Semantic artifacts grant no capability or provider authority.
- Semantic artifacts do not authorize Runtime execution.

Do not silently expand authority in later milestones. Enforce intentionally
inert or draft-only status structurally in contracts.

## Human identity

Caller-supplied reviewer or user IDs are accountability metadata unless real authentication
is implemented. Do not call them authenticated, verified, authorized, signed, or proof of identity.

## Reasoning Gateway

When extending the Reasoning Gateway:

- Minimize provider-visible input to what the operation requires.
- Use exact strategy/provider registration.
- Avoid retry or fallback unless architecture explicitly requires it.
- Validate provider output before admission.
- Preserve existing audit and security behavior.
- Where supported, dry-run must make zero provider calls.

Do not weaken existing Gateway routes while adding a new one.

## Runtime

Use Runtime for effectful or governed capability execution. Do not route inert deterministic
transformations through it for symmetry. Runtime remains the execution authority.

## Tests

Every meaningful milestone requires automated tests. Use
`python -m unittest discover -s tests/<domain> -p 'test_*.py'`.

Do not import foreign `unittest.TestCase` classes directly into test modules;
unittest may discover them twice.

Adversarial tests must cover validly resealed substitutions when integrity
reconstruction is claimed, not only malformed-schema rejection. Cross-stage
features need at least one genuine end-to-end test through the real path,
without manually constructing final upstream artifacts.

Before declaring completion, run focused/regression suites and canonical
isolated discovery across every test directory.

## Required validation

For substantial changes, run as applicable:

- Canonical per-directory Python tests, focused regressions, and compilation.
- Recursive strict-schema inspection and `git diff --check`.
- Changed-file secret, ADR, CI/CD shell, and workflow YAML validation.
- Governed supply-chain validation.

Do not mix unrelated developer-environment dependency upgrades into a feature
milestone unless repository policy requires them.

## CI

New test directories must be discovered exactly once by CI. Avoid duplicate
unittest discovery, and verify registry-digest assertions after adding
contracts.

## Security and secrets

Never commit real secrets. Treat
`.local/secrets/development.auto.tfvars.example` as unrelated local residue
unless a future task explicitly establishes otherwise.

Do not stage unrelated files. Run repository secret scanning before committing
substantial work.

## Git discipline

Use one focused branch per milestone. Do not commit until implementation and
adversarial review pass. Keep milestones in separate commits; do not amend or
squash approved checkpoints unless explicitly instructed.

Before committing:

- Inspect `git status --short`.
- Stage only milestone files.
- Inspect the staged file list and stat.
- Run `git diff --cached --check`.
- Verify no unrelated files or secrets are staged.

Do not push unless explicitly instructed.

## Documentation

Document only behavior that exists. Distinguish implementation, limitations, and deferred
architecture; do not present conceptual ADR material as implemented capability.

## POC priority

Current product direction prioritizes demonstrable movie-production value. M7.4 / POC-1
establishes story → scene breakdown → production options → human review → accepted review
decision → deterministic shot-plan draft.

Prefer extending this executable path toward tangible user-visible outputs
over governance layers that do not improve demonstrability.

## AGENTS.md maintenance

At the end of each milestone, review whether `AGENTS.md` needs updating.
Update it only when:

- A durable repository-wide engineering convention changes.
- A permanent architecture or authority boundary changes.
- Canonical validation or test commands change.
- A recurring implementation mistake reveals a durable rule worth preserving.
- The high-level executable POC baseline materially advances.

Do not update it for:

- Milestone-specific implementation details.
- Temporary branch names or commit hashes.
- Transient bugs or test counts.
- One-off commands.
- Future ideas that are not implemented.

If no durable rule changed, leave `AGENTS.md` untouched. Keep updates small,
deduplicate existing guidance, and do not turn it into project history or a
milestone diary.

## Completion reports

At the end of implementation work, report concisely:

- What changed, tests/validation/adversarial coverage, and known limitations.
- `git status --short`.

Do not claim success without executable evidence.
