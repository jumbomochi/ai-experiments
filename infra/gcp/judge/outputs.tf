output "judge_endpoint_url" {
  value       = "http://${google_compute_address.judge_ip.address}:8000/v1"
  description = "OpenAI-compatible judge endpoint. Copy into shared/eval/judges/configs/v0.2.yaml."
}

output "instance_name" {
  value       = google_compute_instance.judge.name
  description = "GCE instance name (used by make judge-ssh)"
}
