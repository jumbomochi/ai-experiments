terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = "asia-southeast1"
}

# ── GCS model weight cache ──────────────────────────────────────────────────

resource "google_storage_bucket" "model_cache" {
  name                        = "${var.project_id}-ai-experiments-model-cache"
  location                    = "ASIA-SOUTHEAST1"
  uniform_bucket_level_access = true

  lifecycle {
    prevent_destroy = true
  }
}

# ── Static external IP (stable across stop/start) ───────────────────────────

resource "google_compute_address" "vllm_ip" {
  name   = "vllm-static-ip"
  region = "asia-southeast1"
}

# ── Firewall: allow inference traffic on port 8000 ──────────────────────────

resource "google_compute_firewall" "vllm_inference" {
  name    = "allow-vllm-inference"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["8000"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["vllm-server"]
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
      size  = 100  # GB; model weights + Docker layers
      type  = "pd-ssd"
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.vllm_ip.address
    }
  }

  scheduling {
    preemptible         = var.preemptible
    automatic_restart   = !var.preemptible
    on_host_maintenance = "TERMINATE"  # required for GPU instances
  }

  metadata = {
    startup-script = templatefile("${path.module}/startup.sh.tpl", {
      model_id     = var.model_id
      bucket_name  = google_storage_bucket.model_cache.name
      hf_token     = var.hf_token
      vllm_version = var.vllm_version
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
