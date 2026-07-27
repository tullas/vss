variable "name_prefix" {
  description = "Prefix used for local Docker resource names."
  type        = string
}

variable "network_name" {
  description = "Docker network name supplied by the platform module."
  type        = string
}

variable "volume_name" {
  description = "Docker volume name supplied by the platform module."
  type        = string
}

variable "minio_image" {
  description = "Pinned MinIO image reference."
  type        = string
  default     = "docker.io/minio/minio@sha256:391d1d45fdbe79944cb6de9337b073864bb9ee38c4c24280bfb39572e925af08"
}

variable "root_user" {
  description = "MinIO root username, supplied at runtime."
  type        = string
  sensitive   = true
}

variable "root_password" {
  description = "MinIO root password, supplied at runtime."
  type        = string
  sensitive   = true
}

variable "api_port" {
  description = "Host port for the S3-compatible API."
  type        = number
  default     = 9000
}

variable "console_port" {
  description = "Host port for the MinIO console."
  type        = number
  default     = 9001
}
