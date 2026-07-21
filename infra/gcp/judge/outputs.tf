output "judge_endpoint_url" {
  value       = "http://127.0.0.1:8001/v1"
  description = "Judge endpoint through `make judge-tunnel`."
}

output "instance_name" {
  value       = google_compute_instance.judge.name
  description = "GCE instance name used by SSH and the tunnel."
}
