# Local infrastructure provider

The first ADR-0009 vertical slice uses the OpenTofu Docker provider so a
developer can exercise the platform contract without a cloud account. It
creates one isolated Docker network and a least-privilege VersityGW container
with separately scoped object, IAM, and versioning volumes plus an HTTP
liveness check. The provider-neutral contract is in
`infrastructure/contracts/`; Docker resource details remain in
`infrastructure/modules/local/`.

## Prerequisites

- OpenTofu 1.6 or newer
- Docker Engine or Docker Desktop running locally
- network access to pull the pinned VersityGW and Docker provider images
- host port 9000 (S3 API) available

The local adapter is not a cloud emulator. It provides only the object-storage
capability needed by this development slice. Production adapters must publish
the same platform contract using their own managed services and independent
state.

## Credentials and state

Copy the safe example to the ignored local secrets path and set a private
password:

```bash
mkdir -p .local/secrets
cp infrastructure/environments/development/local/development.auto.tfvars.example .local/secrets/development.auto.tfvars
$EDITOR .local/secrets/development.auto.tfvars
```

State is local and ignored at `.local/state/development/`. Plans, provider
artifacts, credentials, and generated output are not committed. Every future
provider/environment must use independent state.

The VersityGW migration does not reuse MinIO's internal volume format. Before
upgrading a populated development environment, export required objects through
the S3 API and retain a snapshot of the prior Docker volume and pinned MinIO
configuration. Import through S3 after applying the new adapter. Rollback means
restoring that snapshot with the prior configuration; never attach a MinIO
volume directly to VersityGW.

## Workflow

The commands below are equivalent to direct OpenTofu commands and are kept in
`scripts/iac-local.sh` to make the state and secret paths explicit:

```bash
scripts/iac-local.sh init
scripts/iac-local.sh validate
scripts/iac-local.sh plan
scripts/iac-local.sh apply
scripts/iac-local.sh health
tofu -chdir=infrastructure/environments/development/local output
scripts/iac-local.sh destroy
```

The direct commands are also supported:

```bash
tofu -chdir=infrastructure/environments/development/local init
tofu -chdir=infrastructure/environments/development/local plan -var-file=.local/secrets/development.auto.tfvars
tofu -chdir=infrastructure/environments/development/local apply -var-file=.local/secrets/development.auto.tfvars
curl -fsS http://127.0.0.1:9000/health
tofu -chdir=infrastructure/environments/development/local destroy -var-file=.local/secrets/development.auto.tfvars
```

If Docker is unavailable, static formatting, initialization, and validation can
still run; apply, health, and destroy are local integration checks and should
report Docker as unavailable rather than being attempted in hosted CI.

## Contract outputs

`platform_contract` includes provider, environment, project, capability flags,
service and health endpoints, resource identifiers, and deployment metadata.
It never includes S3 credentials, environment variables, usernames, or
private host details. The contract is deliberately portable: a future cloud
adapter replaces the implementation module while preserving these capability
and output meanings.
