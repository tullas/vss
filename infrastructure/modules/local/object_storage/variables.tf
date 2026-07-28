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

variable "object_storage_image" {
  description = "Pinned VersityGW image reference."
  type        = string
  default     = "docker.io/versity/versitygw@sha256:ef1c6bf0180abd9583da8a0466b3cba1cfc1ed368afebdf7280c0774081d2c82"
}

variable "access_key" {
  description = "S3 root access key, supplied at runtime."
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "S3 root secret key, supplied at runtime."
  type        = string
  sensitive   = true
}

variable "api_port" {
  description = "Host port for the S3-compatible API."
  type        = number
  default     = 9000
}
