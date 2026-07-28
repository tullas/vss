# Security exceptions

Exceptions live in `security/exceptions.yml` and require: affected component
and version, vulnerability/policy violation, business justification, exposure,
compensating controls, owner, independent approval, expiry, and remediation
plan. The owner and approver must differ; neither may be the implementing agent.

Expiry is a hard UTC date. Missing, malformed, self-approved, or expired
records fail CI. Renewal is a new review, not an expiry edit without evidence.
Exceptions do not waive tests, suppress findings, change risk tolerance, or
authorize autonomous merging.
