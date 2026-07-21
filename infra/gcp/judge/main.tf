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

resource "google_compute_instance" "judge" {
  name         = "vllm-judge-server"
  machine_type = "a2-highgpu-1g"
  zone         = var.zone

  tags = ["judge-server"]

  boot_disk {
    initialize_params {
      image = "deeplearning-platform-release/common-dl-gpu-debian-11-py310"
      size  = 200 # GB; 72B AWQ weights (~36 GB) + Docker layers
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
    on_host_maintenance = "TERMINATE"
  }

  metadata = {
    startup-script = templatefile("${path.module}/startup.sh.tpl", {
      model_id       = var.judge_model_id
      model_revision = var.judge_model_revision
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
