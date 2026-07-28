# Component approval

The OSS Governance Reviewer confirms source and license; Product Security
reviews provenance, maintenance, privilege/network behavior and advisories; the
Dependency Upgrade Steward records support/EOL and rollback. An Implementing
Engineer may prepare the record but cannot approve it.

Admission requires every field defined in `security/components.schema.json`,
an exact version/SHA/digest, upstream security-policy evidence, transitive-risk
notes, approval status, independent approver, and review date. OpenSSF
Scorecard is recorded where meaningful as one risk signal and is never an
automatic rejection criterion.

Statuses are `approved`, `review-required`, or `prohibited`. A
review-required component must have a named independent approver and documented
usage decision. Prohibited components require a valid exception record; an
exception never changes the underlying policy classification.
