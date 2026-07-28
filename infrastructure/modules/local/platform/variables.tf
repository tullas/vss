variable "project" {
  description = "Project name used in local resource names."
  type        = string
}

variable "environment" {
  description = "VSS environment name."
  type        = string
}

variable "minio_root_user" {
  description = "S3 root access key. The legacy variable name is retained for configuration compatibility."
  type        = string
  sensitive   = true
}

variable "minio_root_password" {
  description = "S3 root secret key. The legacy variable name is retained for configuration compatibility."
  type        = string
  sensitive   = true
}

variable "api_port" {
  description = "Host port for the S3-compatible API."
  type        = number
  default     = 9000
}
