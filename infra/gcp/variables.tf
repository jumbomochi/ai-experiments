variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "zone" {
  description = "GCP zone for the GCE instance"
  type        = string
  default     = "asia-southeast1-b"
}

variable "instance_type" {
  description = "GCE machine type. Use g2-standard-8 for L4, a2-highgpu-1g for A100."
  type        = string
  default     = "g2-standard-8"
}

variable "model_id" {
  description = "HuggingFace model ID to serve (e.g. Qwen/Qwen2.5-7B-Instruct)"
  type        = string
  default     = "Qwen/Qwen2.5-7B-Instruct"
}

variable "model_revision" {
  description = "HuggingFace model revision to download (branch, tag, or commit hash). Use 'main' for the latest."
  type        = string
  default     = "main"
}

variable "vllm_version" {
  description = "vLLM Docker image tag (pinned for reproducibility)"
  type        = string
  default     = "v0.4.3"
}

variable "hf_token" {
  description = "HuggingFace API token (required for gated models; leave empty for public models)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "preemptible" {
  description = "Use a preemptible (spot) instance to reduce cost"
  type        = bool
  default     = true
}
