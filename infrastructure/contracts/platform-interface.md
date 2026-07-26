# VSS platform contract

Infrastructure adapters expose a provider-neutral platform contract. The
contract describes capabilities and stable service outputs; it does not expose
how a provider implements a resource.

Every environment publishes:

- `provider`: adapter identifier, such as `local`
- `environment`: VSS environment name
- `project`: project name
- `capabilities`: supported platform capabilities and enabled state
- `services`: service endpoints and health endpoints
- `resource_ids`: stable provider resource identifiers
- `deployment`: release, revision, and creation metadata

The local adapter currently publishes an S3-compatible object-storage service.
Future cloud adapters must implement the same capability and output contract,
even when their resource identifiers and authentication mechanisms differ.

Credentials are inputs to an adapter and are never part of this contract's
rendered output.
