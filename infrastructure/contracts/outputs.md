# Local provider outputs

The development/local root publishes these stable outputs:

| Output | Meaning | Sensitive |
| --- | --- | --- |
| `platform_contract` | Provider-neutral capability and service contract | No |
| `object_storage_endpoint` | S3-compatible API endpoint | No |
| `object_storage_health_endpoint` | Object-storage liveness endpoint | No |
| `network_id` | Docker network identifier | No |
| `volume_id` | Persistent Docker volume identifier | No |
| `container_id` | Object-storage container identifier | No |

The S3 access and secret keys are input variables and are never output.
The contract intentionally contains no credentials or container environment
values.
