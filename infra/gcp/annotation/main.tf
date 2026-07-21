terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

locals {
  region = regex("^(.+)-[a-z]$", var.zone)[0]
}

provider "google" {
  project = var.project_id
  region  = local.region
}

# ── GCE instance ────────────────────────────────────────────────────────────

resource "google_compute_instance" "argilla" {
  name         = "argilla-annotation-server"
  machine_type = "e2-standard-2"
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = 30 # GB
      type  = "pd-ssd"
    }
  }

  network_interface {
    network = "default"
    access_config {}
  }

  # Not preemptible — annotation sessions require stable access
  scheduling {
    preemptible       = false
    automatic_restart = true
  }

  metadata = {
    startup-script = templatefile("${path.module}/startup.sh.tpl", {
      argilla_username = var.argilla_username
      argilla_password = var.argilla_password
    })
  }

  service_account {
    scopes = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring.write",
    ]
  }
}
