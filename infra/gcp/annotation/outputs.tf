output "argilla_url" {
  value       = "http://${google_compute_address.argilla_ip.address}:6900"
  description = "Argilla UI URL. Use with `make push` and `make export`."
}

output "instance_name" {
  value       = google_compute_instance.argilla.name
  description = "GCE instance name (used by SSH)"
}
