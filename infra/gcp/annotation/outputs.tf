output "argilla_url" {
  value       = "http://127.0.0.1:6900"
  description = "Argilla URL through `make tunnel`."
}

output "instance_name" {
  value       = google_compute_instance.argilla.name
  description = "GCE instance name used by SSH and the tunnel."
}
