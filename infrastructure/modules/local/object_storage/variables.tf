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
  default     = "ghcr.io/tullas/vss/versitygw@sha256:619ffa71548c6128dc52e53846a0f2178f8fe69fd083ae3c9d72982b50e1bd5c"
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
