variable "project" {
  description = "Project name used in local resource names."
  type        = string
}

variable "environment" {
  description = "VSS environment name."
  type        = string
}

variable "minio_root_user" {
  description = "MinIO root username."
  type        = string
  sensitive   = true
}

variable "minio_root_password" {
  description = "MinIO root password."
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
