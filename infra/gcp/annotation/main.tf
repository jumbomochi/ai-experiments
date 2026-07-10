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

# ── Static external IP ────────────────────────────────────────────────────────

resource "google_compute_address" "argilla_ip" {
  name   = "argilla-static-ip"
  region = local.region
}

# ── Firewall: allow argilla UI traffic on port 6900 ───────────────────────────

resource "google_compute_firewall" "argilla_ui" {
  name    = "allow-argilla-ui"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["6900"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["argilla-server"]
}

# ── GCE instance ──────────────────────────────────────────────────────────────

resource "google_compute_instance" "argilla" {
  name         = "argilla-annotation-server"
  machine_type = "e2-standard-2"
  zone         = var.zone

  tags = ["argilla-server"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = 30  # GB
      type  = "pd-ssd"
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.argilla_ip.address
    }
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
      "https://www.googleapis.com/auth/devstorage.read_write",
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring.write",
    ]
  }
}
