# Local secrets

Copy `infrastructure/environments/development/local/development.auto.tfvars.example`
to this directory as `development.auto.tfvars` and set a private
`minio_root_password`. Files in this directory are ignored and must never be
committed.
