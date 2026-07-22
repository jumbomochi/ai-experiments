locals {
  required_services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudfunctions.googleapis.com",
    "compute.googleapis.com",
    "eventarc.googleapis.com",
    "logging.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
  ])
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "function_runtime" {
  account_id   = "budget-compute-stop"
  display_name = "Budget compute shutdown runtime"
  project      = var.project_id

  depends_on = [google_project_service.required]
}

resource "google_service_account" "event_trigger" {
  account_id   = "budget-event-trigger"
  display_name = "Budget shutdown Eventarc trigger"
  project      = var.project_id

  depends_on = [google_project_service.required]
}

resource "google_service_account" "function_build" {
  account_id   = "budget-function-build"
  display_name = "Budget shutdown Cloud Build"
  project      = var.project_id

  depends_on = [google_project_service.required]
}

resource "google_project_iam_custom_role" "budget_compute_stopper" {
  project     = var.project_id
  role_id     = "budgetComputeStopper"
  title       = "Budget Compute Stopper"
  description = "List, inspect, and stop Compute Engine instances at the project budget limit."
  permissions = [
    "compute.instances.get",
    "compute.instances.list",
    "compute.instances.stop",
  ]

  depends_on = [google_project_service.required]
}

resource "google_project_iam_member" "function_runtime_custom" {
  project = var.project_id
  role    = google_project_iam_custom_role.budget_compute_stopper.name
  member  = "serviceAccount:${google_service_account.function_runtime.email}"
}

resource "google_project_iam_member" "function_runtime_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.function_runtime.email}"
}

resource "google_project_iam_member" "event_trigger" {
  for_each = toset([
    "roles/eventarc.eventReceiver",
    "roles/run.invoker",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.event_trigger.email}"
}

resource "google_project_iam_member" "function_build" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/logging.logWriter",
    "roles/storage.objectViewer",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.function_build.email}"
}

resource "google_pubsub_topic" "budget_updates" {
  name    = "budget-updates"
  project = var.project_id

  depends_on = [google_project_service.required]
}

resource "google_pubsub_topic_iam_member" "budget_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.budget_updates.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:billingbudgets-notification@system.gserviceaccount.com"
}

resource "google_storage_bucket" "function_source" {
  name                        = "${var.project_id}-function-source"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  depends_on = [google_project_service.required]
}

data "archive_file" "function" {
  type        = "zip"
  source_dir  = "${path.module}/function"
  output_path = "${path.module}/.terraform/budget-stop-function.zip"
}

resource "google_storage_bucket_object" "function_source" {
  name   = "budget-stop-${data.archive_file.function.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.function.output_path
}

resource "google_cloudfunctions2_function" "budget_stop" {
  name     = var.function_name
  location = var.region
  project  = var.project_id

  build_config {
    runtime         = "python312"
    entry_point     = "stop_compute_on_budget"
    service_account = google_service_account.function_build.id

    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_source.name
      }
    }
  }

  service_config {
    available_memory      = "256M"
    timeout_seconds       = 540
    max_instance_count    = 1
    service_account_email = google_service_account.function_runtime.email
    environment_variables = {
      EXPECTED_BUDGET_NAME = var.budget_display_name
      EXPECTED_PROJECT_ID  = var.project_id
    }
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = google_pubsub_topic.budget_updates.id
    service_account_email = google_service_account.event_trigger.email
    retry_policy          = "RETRY_POLICY_RETRY"
  }

  depends_on = [google_project_iam_member.function_build]
}

resource "google_billing_budget" "project" {
  billing_account = var.billing_account_id
  display_name    = var.budget_display_name

  lifecycle {
    prevent_destroy = true
  }

  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }
  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_amount_usd)
    }
  }
  threshold_rules { threshold_percent = 0.10 }
  threshold_rules { threshold_percent = 0.50 }
  threshold_rules { threshold_percent = 1.00 }
  all_updates_rule {
    pubsub_topic                    = google_pubsub_topic.budget_updates.id
    schema_version                  = "1.0"
    enable_project_level_recipients = true
  }

  depends_on = [google_pubsub_topic_iam_member.budget_publisher]
}
