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

# ── Reference existing GCS model weight cache ────────────────────────────────

data "google_storage_bucket" "model_cache" {
  name = "${var.project_id}-ai-experiments-model-cache"
}

# ── Static external IP ────────────────────────────────────────────────────────

resource "google_compute_address" "judge_ip" {
  name   = "judge-static-ip"
  region = local.region
}

# ── Firewall: allow judge inference traffic on port 8000 ──────────────────────

resource "google_compute_firewall" "judge_inference" {
  name    = "allow-judge-inference"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["8000"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["judge-server"]
}

# ── GCE instance ──────────────────────────────────────────────────────────────

resource "google_compute_instance" "judge" {
  name         = "vllm-judge-server"
  machine_type = "a2-highgpu-1g"
  zone         = var.zone

  tags = ["judge-server"]

  boot_disk {
    initialize_params {
      image = "deeplearning-platform-release/common-dl-gpu-debian-11-py310"
      size  = 200  # GB; 72B AWQ weights (~36 GB) + Docker layers
      type  = "pd-ssd"
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.judge_ip.address
    }
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
      bucket_name    = data.google_storage_bucket.model_cache.name
      hf_token       = var.hf_token
      vllm_version   = var.vllm_version
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
