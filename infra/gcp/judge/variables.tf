variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "zone" {
  description = "GCP zone for the judge instance"
  type        = string
  default     = "asia-southeast1-b"
}

variable "judge_model_id" {
  description = "HuggingFace model ID for the judge"
  type        = string
  default     = "Qwen/Qwen2.5-72B-Instruct-AWQ"
}

variable "judge_model_revision" {
  description = "Model revision (git SHA or tag)"
  type        = string
  default     = "main"
}

variable "vllm_version" {
  description = "vLLM Docker image tag"
  type        = string
  default     = "v0.4.3"
}

variable "hf_token" {
  description = "HuggingFace API token (may be needed for gated models)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "preemptible" {
  description = "Use preemptible instance to reduce cost"
  type        = bool
  default     = true
}
