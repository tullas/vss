terraform {
  required_version = ">= 1.6.0"
}

locals {
  resource_name_prefix = "vss-${var.environment}"
}
