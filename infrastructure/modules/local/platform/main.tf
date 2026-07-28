locals {
  name_prefix = "${var.project}-${var.environment}"
  network     = "${local.name_prefix}-network"
  volume      = "${local.name_prefix}-object-storage"
}

resource "docker_network" "platform" {
  name   = local.network
  driver = "bridge"
}

module "object_storage" {
  source = "../object_storage"

  name_prefix  = local.name_prefix
  network_name = docker_network.platform.name
  volume_name  = local.volume
  access_key   = var.minio_root_user
  secret_key   = var.minio_root_password
  api_port     = var.api_port
}
