output "endpoint_url" {
  value       = "http://127.0.0.1:8000/v1"
  description = "Inference endpoint through `make tunnel`."
}

output "instance_name" {
  value       = google_compute_instance.vllm.name
  description = "GCE instance name used by SSH and the tunnel."
}
