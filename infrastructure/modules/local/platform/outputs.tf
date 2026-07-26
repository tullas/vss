output "network_id" {
  description = "Isolated Docker network identifier."
  value       = docker_network.platform.id
}

output "network_name" {
  description = "Isolated Docker network name."
  value       = docker_network.platform.name
}

output "object_storage_endpoint" {
  description = "S3-compatible object-storage endpoint."
  value       = module.object_storage.endpoint
}

output "object_storage_health_endpoint" {
  description = "Object-storage health endpoint."
  value       = module.object_storage.health_endpoint
}

output "object_storage_container_id" {
  description = "MinIO container identifier."
  value       = module.object_storage.container_id
}

output "object_storage_volume_id" {
  description = "Persistent object-storage volume identifier."
  value       = module.object_storage.volume_id
}
