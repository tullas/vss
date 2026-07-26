terraform {
  required_version = ">= 1.6.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }

  backend "local" {
    path = "../../../../.local/state/development/terraform.tfstate"
  }
}

provider "docker" {}
