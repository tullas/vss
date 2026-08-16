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
  default     = "ghcr.io/tullas/vss/versitygw@sha256:0cb1fe893f0b67608c623a0cb36e5a5c7085f2118824f72b6833f3831cc35f53"
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
