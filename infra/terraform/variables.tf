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
  default     = "noreply@getquuie.com"
}

variable "email_from_name" {
  description = "Default sender display name for frontend auth emails"
  type        = string
  default     = "Arbiter AI"
}

variable "inject_optional_sandbox_secrets" {
  description = "When true, include optional sandbox secret mappings (Stripe + selected email provider). Production always includes them."
  type        = bool
  default     = false
}

variable "sandbox_email_bypass_enabled" {
  description = "Enable temporary sandbox-only credentials bypass for allowlisted tester emails."
  type        = bool
  default     = true
}

variable "email_provider" {
  description = "Frontend email provider (ses|brevo|console). Controls which optional secret keys ECS references."
  type        = string
  default     = "ses"

  validation {
    condition     = contains(["ses", "brevo", "console"], lower(var.email_provider))
    error_message = "email_provider must be one of: ses, brevo, console."
  }
}

variable "ses_domain" {
  description = "Optional SES sending domain to provision/verify via Terraform (leave empty to skip SES identity resources)"
  type        = string
  default     = ""
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "create_networking" {
  description = "When true, Terraform creates VPC/subnets/NAT. When false, deploy into existing network."
  type        = bool
  default     = false
}

variable "existing_vpc_id" {
  description = "Existing VPC ID to use when create_networking=false (auto-discovered by Name tag when empty)."
  type        = string
  default     = ""
}

variable "existing_public_subnet_ids" {
  description = "Existing public subnet IDs for ALB/NAT when create_networking=false (auto-discovered by Name tag when empty)."
  type        = list(string)
  default     = []
}

variable "existing_private_subnet_ids" {
  description = "Existing private subnet IDs for ECS tasks when create_networking=false (auto-discovered by Name tag when empty)."
  type        = list(string)
  default     = []
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

variable "frontend_node_options" {
  description = "NODE_OPTIONS for frontend runtime (heap cap to reduce OOM risk on small tasks)"
  type        = string
  default     = "--max-old-space-size=384"
}

variable "create_cloudwatch_log_groups" {
  description = "When true, create CloudWatch log groups. Set false when groups are pre-provisioned."
  type        = bool
  default     = false
}

variable "cloudwatch_log_retention_days" {
  description = "CloudWatch log retention days when create_cloudwatch_log_groups=true."
  type        = number
  default     = 30
}

variable "worker_cpu" {
  description = "CPU units for worker task"
  type        = number
  default     = 512
}

variable "worker_memory" {
  description = "Memory (MiB) for worker task"
  type        = number
  default     = 1024
}

variable "beat_cpu" {
  description = "CPU units for beat task"
  type        = number
  default     = 256
}

variable "beat_memory" {
  description = "Memory (MiB) for beat task"
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

variable "worker_desired_count" {
  description = "Number of Celery worker tasks (set to 0 only if async ingestion is intentionally disabled)"
  type        = number
  default     = 1
}

variable "beat_desired_count" {
  description = "Number of Celery beat scheduler tasks (set to 0 to disable periodic catalog/rules sync jobs)"
  type        = number
  default     = 1
}

variable "uploads_dir" {
  description = "Shared upload directory mounted by backend/worker tasks"
  type        = string
  default     = "/tmp/arbiter_uploads"
}

variable "enable_shared_uploads" {
  description = "Enable shared uploads volume in ECS task definitions."
  type        = bool
  default     = false
}

variable "create_efs_resources" {
  description = "When true, create EFS resources for shared uploads; otherwise use existing_efs_file_system_id."
  type        = bool
  default     = false
}

variable "existing_efs_file_system_id" {
  description = "Existing EFS filesystem ID to mount when create_efs_resources=false."
  type        = string
  default     = ""
}

variable "existing_efs_access_point_id" {
  description = "Optional existing EFS access point ID used when create_efs_resources=false."
  type        = string
  default     = ""
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

variable "create_github_actions_iam" {
  description = "When true, create GitHub OIDC provider and deploy role. Leave false for least-privilege deploy pipelines."
  type        = bool
  default     = false
}

variable "create_ecs_task_roles" {
  description = "When true, create ECS task execution/task roles. When false, reuse existing roles."
  type        = bool
  default     = false
}

variable "manage_ecs_task_role_policies" {
  description = "When true, attach/update inline ECS task role policies even when roles are pre-existing."
  type        = bool
  default     = false
}

variable "existing_ecs_task_execution_role_arn" {
  description = "Existing ECS task execution role ARN when create_ecs_task_roles=false."
  type        = string
  default     = ""
}

variable "existing_ecs_task_role_arn" {
  description = "Existing ECS task role ARN when create_ecs_task_roles=false."
  type        = string
  default     = ""
}

variable "existing_ecs_task_execution_role_name" {
  description = "Existing ECS task execution role name when create_ecs_task_roles=false. Defaults to <project>-ecs-task-execution."
  type        = string
  default     = ""
}

variable "existing_ecs_task_role_name" {
  description = "Existing ECS task role name when create_ecs_task_roles=false. Defaults to <project>-ecs-task."
  type        = string
  default     = ""
}

variable "create_data_services" {
  description = "When true, provision RDS + ElastiCache. Keep false when using pre-existing managed data services."
  type        = bool
  default     = false
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
  default     = ""
  sensitive   = true
}

# --- ElastiCache ---

variable "redis_node_type" {
  description = "ElastiCache node type (cache.t4g.micro is free-tier eligible)"
  type        = string
  default     = "cache.t4g.micro"
}
