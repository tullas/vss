output "endpoint" {
  description = "Host endpoint for S3-compatible object storage."
  value       = "http://127.0.0.1:${var.api_port}"
}

output "health_endpoint" {
  description = "MinIO liveness endpoint."
  value       = "http://127.0.0.1:${var.api_port}/minio/health/live"
}

output "container_id" {
  description = "MinIO Docker container identifier."
  value       = docker_container.minio.id
}

output "volume_id" {
  description = "Persistent object-storage Docker volume identifier."
  value       = docker_volume.data.id
}
