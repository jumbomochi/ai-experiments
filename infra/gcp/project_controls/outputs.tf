output "budget_name" {
  description = "Resource name of the protected project budget"
  value       = google_billing_budget.project.name
}

output "topic_id" {
  description = "ID of the budget update Pub/Sub topic"
  value       = google_pubsub_topic.budget_updates.id
}

output "function_name" {
  description = "Name of the budget shutdown Cloud Run function"
  value       = google_cloudfunctions2_function.budget_stop.name
}

output "runtime_service_account_email" {
  description = "Email of the function runtime service account"
  value       = google_service_account.function_runtime.email
}

output "source_bucket_name" {
  description = "Name of the Cloud Run function source bucket"
  value       = google_storage_bucket.function_source.name
}

output "project_number" {
  description = "Numeric ID of the controlled GCP project"
  value       = data.google_project.current.number
}
