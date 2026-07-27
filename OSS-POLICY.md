# Open source software policy

Every direct external component must be recorded in `security/components.yml`
and independently approved before admission. License identification uses the
upstream license file and distribution context, not a classifier or OpenSSF
Scorecard alone.

Allowed by default: Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, MIT, MIT-0,
MPL-2.0, PSF-2.0, and CC0-1.0.

Review required: GPL/LGPL/EPL/CDDL used as tools or services, dual/custom
licenses, public-domain assertions, missing metadata, and components that cross
a distribution or network-service boundary. Review records the usage context
and obligations in the component registry.

Prohibited without a separately approved, expiring exception: AGPL or SSPL in
a distributed VSS product, Commons Clause/source-available terms,
noncommercial/no-derivatives terms, unlicensed code, and components whose
license cannot be established. An exception cannot be approved by its author.

Notices, source-offer obligations, modifications, and attribution evidence must
ship with any release for which they apply.
