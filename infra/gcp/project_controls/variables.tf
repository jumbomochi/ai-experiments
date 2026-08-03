variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "billing_account_id" {
  description = "Cloud Billing account ID that owns the project budget"
  type        = string
}

variable "region" {
  description = "GCP region for persistent project controls"
  type        = string
  default     = "asia-southeast1"
}

variable "budget_amount_sgd" {
  description = "Monthly project budget amount in SGD"
  type        = number
  default     = 100

  validation {
    condition     = var.budget_amount_sgd > 0
    error_message = "budget_amount_sgd must be greater than zero."
  }
}

variable "budget_display_name" {
  description = "Display name for the project budget"
  type        = string
  default     = "ai-experiments-monthly"
}

variable "function_name" {
  description = "Name of the budget shutdown Cloud Run function"
  type        = string
  default     = "budget-stop-compute"
}
