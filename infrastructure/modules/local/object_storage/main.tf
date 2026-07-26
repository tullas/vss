resource "docker_image" "minio" {
  name         = var.minio_image
  keep_locally = true
}

resource "docker_volume" "data" {
  name = var.volume_name
}

resource "docker_container" "minio" {
  name  = "${var.name_prefix}-minio"
  image = docker_image.minio.image_id

  env = [
    "MINIO_ROOT_USER=${var.root_user}",
    "MINIO_ROOT_PASSWORD=${var.root_password}",
  ]

  command = ["server", "/data", "--console-address", ":9001"]

  volumes {
    volume_name    = docker_volume.data.name
    container_path = "/data"
  }

  networks_advanced {
    name = var.network_name
  }

  ports {
    internal = 9000
    external = var.api_port
  }

  ports {
    internal = 9001
    external = var.console_port
  }

  healthcheck {
    test         = ["CMD-SHELL", "curl -fsS http://127.0.0.1:9000/minio/health/live >/dev/null || exit 1"]
    interval     = "10s"
    timeout      = "5s"
    retries      = 6
    start_period = "10s"
  }
}
