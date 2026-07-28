output "platform_contract" {
  description = "Provider-neutral VSS platform contract."
  value = {
    provider    = "local"
    environment = var.environment
    project     = var.project
    capabilities = {
      networking          = true
      object_storage      = true
      relational_database = false
      cache               = false
      durable_messaging   = false
      gpu_compute         = false
    }
    services = {
      object_storage = {
        endpoint        = module.platform.object_storage_endpoint
        health_endpoint = module.platform.object_storage_health_endpoint
      }
    }
    resource_ids = {
      network   = module.platform.network_id
      volume    = module.platform.object_storage_volume_id
      container = module.platform.object_storage_container_id
    }
    deployment = {
      managed_by = "OpenTofu"
      revision   = "local"
    }
  }
}

output "object_storage_endpoint" {
  description = "S3-compatible object-storage endpoint."
  value       = module.platform.object_storage_endpoint
}

output "object_storage_health_endpoint" {
  description = "Object-storage liveness endpoint."
  value       = module.platform.object_storage_health_endpoint
}

output "network_id" {
  description = "Docker network identifier."
  value       = module.platform.network_id
}

output "volume_id" {
  description = "Persistent Docker volume identifier."
  value       = module.platform.object_storage_volume_id
}

output "container_id" {
  description = "Object-storage container identifier."
  value       = module.platform.object_storage_container_id
}
