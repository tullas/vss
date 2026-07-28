resource "docker_image" "object_storage" {
  name         = var.object_storage_image
  keep_locally = true
}

resource "docker_volume" "data" {
  name = var.volume_name
}

resource "docker_volume" "iam" {
  name = "${var.volume_name}-iam"
}

resource "docker_volume" "versions" {
  name = "${var.volume_name}-versions"
}

resource "docker_container" "volume_permissions" {
  name     = "${var.name_prefix}-object-storage-init"
  image    = docker_image.object_storage.image_id
  must_run = false
  user     = "0:0"

  entrypoint = ["/bin/sh", "-c"]
  command    = ["chmod 0700 /data /iam /versions && chown 65532:65532 /data /iam /versions"]

  volumes {
    volume_name    = docker_volume.data.name
    container_path = "/data"
  }

  volumes {
    volume_name    = docker_volume.iam.name
    container_path = "/iam"
  }

  volumes {
    volume_name    = docker_volume.versions.name
    container_path = "/versions"
  }

  capabilities {
    add  = ["CAP_CHOWN", "CAP_FOWNER"]
    drop = ["ALL"]
  }

  security_opts = ["no-new-privileges:true"]
}

resource "terraform_data" "volume_permissions_complete" {
  triggers_replace = docker_container.volume_permissions.id

  provisioner "local-exec" {
    command = "${path.module}/../../../../scripts/check-container-exit.sh"
    environment = {
      VSS_INIT_CONTAINER_ID = docker_container.volume_permissions.id
    }
  }
}

resource "docker_container" "object_storage" {
  name      = "${var.name_prefix}-object-storage"
  image     = docker_image.object_storage.image_id
  user      = "65532:65532"
  read_only = true
  restart   = "unless-stopped"

  env = [
    "ROOT_ACCESS_KEY=${var.access_key}",
    "ROOT_SECRET_KEY=${var.secret_key}",
  ]

  command = ["--port", ":9000", "--health", "/health", "--iam-dir", "/iam", "--quiet", "posix", "--versioning-dir", "/versions", "/data"]

  tmpfs = {
    "/tmp" = "rw,noexec,nosuid,size=16m"
  }

  volumes {
    volume_name    = docker_volume.data.name
    container_path = "/data"
  }

  volumes {
    volume_name    = docker_volume.iam.name
    container_path = "/iam"
  }

  volumes {
    volume_name    = docker_volume.versions.name
    container_path = "/versions"
  }

  networks_advanced {
    name = var.network_name
  }

  ports {
    internal = 9000
    external = var.api_port
    ip       = "127.0.0.1"
  }

  capabilities {
    drop = ["ALL"]
  }

  security_opts = ["no-new-privileges:true"]

  healthcheck {
    test         = ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1:9000/health"]
    interval     = "10s"
    timeout      = "5s"
    retries      = 6
    start_period = "10s"
  }

  depends_on = [terraform_data.volume_permissions_complete]
}
