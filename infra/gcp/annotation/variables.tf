variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "zone" {
  description = "GCP zone for the annotation instance"
  type        = string
  default     = "asia-southeast1-b"
}

variable "argilla_username" {
  description = "Argilla admin username"
  type        = string
  default     = "owner"
}

variable "argilla_password" {
  description = "Argilla admin password"
  type        = string
  sensitive   = true
}
