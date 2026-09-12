# Controller integrity evidence binding: independent review v4

**Verdict: ACCEPT**

## Scope and independence

Reviewed the latest design for `controller-integrity-evidence-binding` (#161/#162), focusing on whether captured `.secrets.baseline` residue can launder suppressions and whether the new rule preserves the #161 identity-stability correction. This was an independent follow-up in a fresh review task, separate from the design author. The reviewer statement is accountability metadata only; it makes no authentication or identity claim. No design, controller, milestone state/history, or earlier review artifact was changed.

## Findings

The added rule closes the suppression-laundering path at the design level. The repository-governance validator checks fixed baseline scope and structural consistency, but it does not establish that individual suppression entries are legitimate ([validate-repository-governance.py](/home/tullas/github/vss/scripts/security/validate-repository-governance.py:36), [validate-repository-governance.py](/home/tullas/github/vss/scripts/security/validate-repository-governance.py:40)). The design explicitly limits captured worktree residue to identity bookkeeping and requires secret scanning for the governed change to use the `.secrets.baseline` blob from the bound base HEAD, so an added or substituted suppression in residue cannot alter scan results ([design](/home/tullas/github/vss/docs/reviews/controller-integrity-evidence-binding-design.md:30), [design](/home/tullas/github/vss/docs/reviews/controller-integrity-evidence-binding-design.md:69), [design](/home/tullas/github/vss/docs/reviews/controller-integrity-evidence-binding-design.md:72)). It treats any deliberate baseline update as governed work, not eligible residue, and includes tests for suppression substitutions and governed baseline changes ([design](/home/tullas/github/vss/docs/reviews/controller-integrity-evidence-binding-design.md:32), [design](/home/tullas/github/vss/docs/reviews/controller-integrity-evidence-binding-design.md:72)).

This still addresses #161: the controller may fingerprint and exclude only the captured exact residue from semantic identity, so stashing/restoring that residue does not rebind the governed source identity, while the residue itself never supplies scanner suppression authority ([design](/home/tullas/github/vss/docs/reviews/controller-integrity-evidence-binding-design.md:32), [design](/home/tullas/github/vss/docs/reviews/controller-integrity-evidence-binding-design.md:34)). A separately committed baseline change remains part of governed work and must be checked using the base-HEAD baseline for that change.

I found no remaining material constitutional issue in the reviewed scope. This accepts the design for the next governed review/implementation stage only. The implementation must actually make every applicable validation scanner read the bound base-HEAD baseline, and the stated adversarial tests must verify that a malicious worktree suppression cannot hide a finding; this review does not claim those behaviors already exist.

## Limits

This is a design review, not implementation validation. I did not run tests or modify repository behavior. The existing validator’s structural checks are not independent authentication of baseline entries; the design makes no such claim and routes deliberate baseline edits through governed work. No authentication or human identity is inferred from this review. The pre-existing unrelated untracked `.local/secrets/development.auto.tfvars.example` and prior untracked review/design artifacts were not modified.
