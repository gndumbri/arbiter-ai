variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (e.g. production, sandbox, staging)"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "arbiter-ai"
}

variable "app_mode" {
  description = "Application mode passed to services (mock|sandbox|production)"
  type        = string
  default     = "production"
}

variable "app_env" {
  description = "Application environment label (e.g. development|staging|production)"
  type        = string
  default     = "production"
}

variable "app_base_url" {
  description = "Canonical frontend URL for backend links/CORS; defaults to ALB URL when empty"
  type        = string
  default     = ""
}

variable "allowed_origins" {
  description = "Comma-separated CORS origins for backend; defaults to app_base_url (or ALB URL when empty)"
  type        = string
  default     = ""
}

variable "trusted_proxy_hops" {
  description = "Trusted proxy depth for X-Forwarded-For parsing"
  type        = number
  default     = 1
}

variable "frontend_nextauth_url" {
  description = "NEXTAUTH_URL for frontend service; defaults to app_base_url (or ALB URL when empty)"
  type        = string
  default     = ""
}

variable "next_public_api_url" {
  description = "Frontend NEXT_PUBLIC_API_URL value (use /api/v1 for ALB path routing)"
  type        = string
  default     = "/api/v1"
}

variable "email_from" {
  description = "Default sender email for frontend auth emails"
  type        = string
  default     = "noreply@arbiter-ai.com"
}

variable "email_from_name" {
  description = "Default sender display name for frontend auth emails"
  type        = string
  default     = "Arbiter AI"
}

variable "inject_optional_sandbox_secrets" {
  description = "When true, include optional sandbox secret mappings (Stripe/Brevo). Production always includes them."
  type        = bool
  default     = false
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "alb_certificate_arn" {
  description = "ACM certificate ARN for ALB HTTPS listener (leave empty to run HTTP-only)"
  type        = string
  default     = ""
}

variable "backend_image_tag" {
  description = "Docker image tag for the backend service"
  type        = string
  default     = "latest"
}

variable "frontend_image_tag" {
  description = "Docker image tag for the frontend service"
  type        = string
  default     = "latest"
}

variable "backend_cpu" {
  description = "CPU units for backend task (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Memory (MiB) for backend task"
  type        = number
  default     = 1024
}

variable "frontend_cpu" {
  description = "CPU units for frontend task"
  type        = number
  default     = 256
}

variable "frontend_memory" {
  description = "Memory (MiB) for frontend task"
  type        = number
  default     = 512
}

variable "backend_desired_count" {
  description = "Number of backend tasks"
  type        = number
  default     = 1
}

variable "frontend_desired_count" {
  description = "Number of frontend tasks"
  type        = number
  default     = 1
}

variable "secrets_manager_arn" {
  description = "ARN of the Secrets Manager secret containing app env vars"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository (owner/name) for OIDC trust policy"
  type        = string
  default     = "gndumbri/arbiter-ai"
}

# --- RDS ---

variable "db_instance_class" {
  description = "RDS instance class (db.t4g.micro is free-tier eligible)"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB (20 GB is free-tier eligible)"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Max storage for autoscaling in GB (0 disables autoscaling)"
  type        = number
  default     = 0
}

variable "db_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "arbiter"
}

variable "db_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "arbiter"
}

variable "db_password" {
  description = "Master password for the RDS instance"
  type        = string
  sensitive   = true
}

# --- ElastiCache ---

variable "redis_node_type" {
  description = "ElastiCache node type (cache.t4g.micro is free-tier eligible)"
  type        = string
  default     = "cache.t4g.micro"
}
