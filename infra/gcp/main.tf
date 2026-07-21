terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

locals {
  # Derive region from zone by stripping the trailing zone letter (e.g. "asia-southeast1-b" → "asia-southeast1")
  region = regex("^(.+)-[a-z]$", var.zone)[0]
}

provider "google" {
  project = var.project_id
  region  = local.region
}

# ── GCE instance ─────────────────────────────────────────────────────────────

resource "google_compute_instance" "vllm" {
  name         = "vllm-eval-server"
  machine_type = var.instance_type
  zone         = var.zone

  tags = ["vllm-server"]

  boot_disk {
    initialize_params {
      # Deep Learning VM: CUDA drivers + Docker pre-installed.
      image = "deeplearning-platform-release/common-dl-gpu-debian-11-py310"
      size  = 100 # GB; model weights + Docker layers
      type  = "pd-ssd"
    }
  }

  network_interface {
    network = "default"
    access_config {}
  }

  scheduling {
    preemptible         = var.preemptible
    automatic_restart   = !var.preemptible
    on_host_maintenance = "TERMINATE" # required for GPU instances
  }

  metadata = {
    startup-script = templatefile("${path.module}/startup.sh.tpl", {
      model_id       = var.model_id
      model_revision = var.model_revision
      hf_token       = var.hf_token
      vllm_version   = var.vllm_version
    })
  }

  service_account {
    scopes = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring.write",
    ]
  }
}
