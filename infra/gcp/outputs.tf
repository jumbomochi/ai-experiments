output "endpoint_url" {
  value       = "http://${google_compute_address.vllm_ip.address}:8000/v1"
  description = "OpenAI-compatible inference endpoint. Copy into the model manifest YAML."
}

output "instance_name" {
  value       = google_compute_instance.vllm.name
  description = "GCE instance name (used by make ssh)"
}

output "bucket_name" {
  value       = google_storage_bucket.model_cache.name
  description = "GCS bucket holding cached model weights"
}
