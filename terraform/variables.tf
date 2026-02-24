variable "aws_region" {
  description = "AWS region to deploy resources in."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project identifier used as a prefix for all resource names."
  type        = string
  default     = "prima-tech-challenge"
}

variable "environment" {
  description = "Deployment environment (dev | staging | prod)."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "localstack_endpoint" {
  description = "LocalStack endpoint URL. Leave empty to target real AWS."
  type        = string
  default     = ""
}

# ── EKS / IRSA ─────────────────────────────────────────────────────────────

variable "eks_oidc_provider_arn" {
  description = <<-EOT
    ARN of the EKS cluster OIDC provider used for IAM Roles for Service
    Accounts (IRSA).  Leave empty when not deploying to EKS.
  EOT
  type    = string
  default = ""
}

variable "eks_oidc_provider_url" {
  description = <<-EOT
    Hostname of the EKS OIDC provider (without https://).
    Example: oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE123
  EOT
  type    = string
  default = ""
}

variable "k8s_namespace" {
  description = "Kubernetes namespace that hosts the service account."
  type        = string
  default     = "default"
}

variable "k8s_service_account_name" {
  description = "Name of the Kubernetes ServiceAccount that will assume the IAM role."
  type        = string
  default     = "prima-api"
}
