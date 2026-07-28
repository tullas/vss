module "platform" {
  source = "../../../modules/local/platform"

  project             = var.project
  environment         = var.environment
  minio_root_user     = var.minio_root_user
  minio_root_password = var.minio_root_password
  api_port            = var.api_port
}
