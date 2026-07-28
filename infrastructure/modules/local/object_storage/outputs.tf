output "endpoint" {
  description = "Host endpoint for S3-compatible object storage."
  value       = "http://127.0.0.1:${var.api_port}"
}

output "health_endpoint" {
  description = "Object-storage liveness endpoint."
  value       = "http://127.0.0.1:${var.api_port}/health"
}

output "container_id" {
  description = "Object-storage Docker container identifier."
  value       = docker_container.object_storage.id
}

output "volume_id" {
  description = "Persistent object-storage Docker volume identifier."
  value       = docker_volume.data.id
}
