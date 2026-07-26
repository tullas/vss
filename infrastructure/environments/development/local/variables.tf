variable "project" {
  description = "VSS project name."
  type        = string
  default     = "vss"
}

variable "environment" {
  description = "VSS environment name."
  type        = string
  default     = "development"
  validation {
    condition     = var.environment == "development"
    error_message = "The local provider root is only for the development environment."
  }
}

variable "minio_root_user" {
  description = "MinIO root username, supplied through an ignored local tfvars file."
  type        = string
  sensitive   = true
}

variable "minio_root_password" {
  description = "MinIO root password, supplied through an ignored local tfvars file."
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
