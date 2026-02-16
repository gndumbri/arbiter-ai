# --- ECS Cluster ---
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = { Name = "${var.project_name}-cluster" }
}

locals {
  # Canonical app URL fallback: if not explicitly provided, use the ALB hostname.
  # This keeps sandbox/prod deploys working even with minimal tfvars.
  resolved_app_base_url = var.app_base_url != "" ? var.app_base_url : "http://${local.alb_dns_name}"
  # Default CORS allow-list follows the canonical app URL when not overridden.
  resolved_allowed_origins = var.allowed_origins != "" ? var.allowed_origins : local.resolved_app_base_url
  # Frontend auth callbacks should generally point to the frontend origin.
  resolved_frontend_nextauth_url = (
    var.frontend_nextauth_url != ""
    ? var.frontend_nextauth_url
    : local.resolved_app_base_url
  )
  # Production should always inject optional billing/email secrets.
  # Sandbox can opt in via inject_optional_sandbox_secrets=true.
  include_optional_secrets = var.app_mode == "production" || var.inject_optional_sandbox_secrets

  # Base backend runtime contract: required across sandbox + production.
  backend_base_secrets = [
    { name = "DATABASE_URL", valueFrom = "${var.secrets_manager_arn}:DATABASE_URL::" },
    { name = "REDIS_URL", valueFrom = "${var.secrets_manager_arn}:REDIS_URL::" },
    { name = "NEXTAUTH_SECRET", valueFrom = "${var.secrets_manager_arn}:NEXTAUTH_SECRET::" },
  ]
  # Optional billing keys: avoid forcing them in minimal sandbox environments.
  backend_stripe_secrets = [
    { name = "STRIPE_SECRET_KEY", valueFrom = "${var.secrets_manager_arn}:STRIPE_SECRET_KEY::" },
    { name = "STRIPE_WEBHOOK_SECRET", valueFrom = "${var.secrets_manager_arn}:STRIPE_WEBHOOK_SECRET::" },
    { name = "STRIPE_PRICE_ID", valueFrom = "${var.secrets_manager_arn}:STRIPE_PRICE_ID::" },
  ]
  backend_runtime_env = [
    { name = "APP_MODE", value = var.app_mode },
    { name = "APP_ENV", value = var.app_env },
    { name = "LOG_LEVEL", value = "INFO" },
    { name = "ALLOWED_ORIGINS", value = local.resolved_allowed_origins },
    { name = "APP_BASE_URL", value = local.resolved_app_base_url },
    { name = "TRUSTED_PROXY_HOPS", value = tostring(var.trusted_proxy_hops) },
    { name = "AWS_REGION", value = var.aws_region },
    { name = "LLM_PROVIDER", value = "bedrock" },
    { name = "EMBEDDING_PROVIDER", value = "bedrock" },
    { name = "VECTOR_STORE_PROVIDER", value = "pgvector" },
    { name = "RERANKER_PROVIDER", value = "flashrank" },
    { name = "UPLOADS_DIR", value = var.uploads_dir },
    # Catalog sync pipeline (metadata + open-license ingestion) settings.
    { name = "CATALOG_SYNC_ENABLED", value = tostring(var.catalog_sync_enabled) },
    { name = "CATALOG_SYNC_CRON", value = var.catalog_sync_cron },
    { name = "CATALOG_RANKED_GAME_LIMIT", value = tostring(var.catalog_ranked_game_limit) },
    { name = "OPEN_RULES_SYNC_ENABLED", value = tostring(var.open_rules_sync_enabled) },
    { name = "OPEN_RULES_SYNC_CRON", value = var.open_rules_sync_cron },
    { name = "OPEN_RULES_MAX_DOCUMENTS", value = tostring(var.open_rules_max_documents) },
    { name = "OPEN_RULES_ALLOWED_LICENSES", value = var.open_rules_allowed_licenses },
    { name = "OPEN_RULES_FORCE_REINDEX", value = tostring(var.open_rules_force_reindex) },
  ]

  # Frontend uses sync Postgres driver, so keep a separate secret key.
  frontend_base_secrets = [
    { name = "AUTH_SECRET", valueFrom = "${var.secrets_manager_arn}:NEXTAUTH_SECRET::" },
    { name = "DATABASE_URL", valueFrom = "${var.secrets_manager_arn}:FRONTEND_DATABASE_URL::" },
  ]
  # Optional email provider secret keys. Keep mappings provider-specific so ECS
  # does not require unrelated keys to exist in Secrets Manager.
  frontend_email_provider_secrets = (
    lower(var.email_provider) == "ses"
    ? [{ name = "EMAIL_SERVER", valueFrom = "${var.secrets_manager_arn}:EMAIL_SERVER::" }]
    : lower(var.email_provider) == "brevo"
    ? [{ name = "BREVO_API_KEY", valueFrom = "${var.secrets_manager_arn}:BREVO_API_KEY::" }]
    : []
  )
  uploads_volume_name = "uploads-shared"
  shared_uploads_mount_points = local.shared_uploads_enabled ? [{
    sourceVolume  = local.uploads_volume_name
    containerPath = var.uploads_dir
    readOnly      = false
  }] : []
}

# --- Backend Task Definition ---
resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = local.ecs_task_execution_role_arn
  task_role_arn            = local.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "backend"
    image     = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
    essential = true

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    environment = local.backend_runtime_env

    mountPoints = local.shared_uploads_mount_points

    secrets = concat(
      # Keep required runtime secrets always present; add optional ones by mode.
      local.backend_base_secrets,
      local.include_optional_secrets ? local.backend_stripe_secrets : []
    )

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = local.backend_log_group_name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  dynamic "volume" {
    for_each = local.shared_uploads_enabled ? [1] : []
    content {
      name = local.uploads_volume_name
      efs_volume_configuration {
        file_system_id     = local.resolved_efs_file_system_id
        transit_encryption = "ENABLED"

        dynamic "authorization_config" {
          for_each = local.resolved_efs_access_point_id != "" ? [1] : []
          content {
            access_point_id = local.resolved_efs_access_point_id
            iam             = "DISABLED"
          }
        }
      }
    }
  }

  depends_on = [aws_efs_mount_target.uploads]
}

# --- Worker Task Definition ---
resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = local.ecs_task_execution_role_arn
  task_role_arn            = local.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "worker"
    image     = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
    essential = true
    command   = ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info"]

    environment = local.backend_runtime_env

    mountPoints = local.shared_uploads_mount_points

    secrets = concat(
      local.backend_base_secrets,
      local.include_optional_secrets ? local.backend_stripe_secrets : []
    )

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = local.worker_log_group_name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  dynamic "volume" {
    for_each = local.shared_uploads_enabled ? [1] : []
    content {
      name = local.uploads_volume_name
      efs_volume_configuration {
        file_system_id     = local.resolved_efs_file_system_id
        transit_encryption = "ENABLED"

        dynamic "authorization_config" {
          for_each = local.resolved_efs_access_point_id != "" ? [1] : []
          content {
            access_point_id = local.resolved_efs_access_point_id
            iam             = "DISABLED"
          }
        }
      }
    }
  }

  depends_on = [aws_efs_mount_target.uploads]
}

# --- Beat Task Definition ---
resource "aws_ecs_task_definition" "beat" {
  family                   = "${var.project_name}-beat"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.beat_cpu
  memory                   = var.beat_memory
  execution_role_arn       = local.ecs_task_execution_role_arn
  task_role_arn            = local.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "beat"
    image     = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
    essential = true
    command   = ["celery", "-A", "app.workers.celery_app", "beat", "--loglevel=info"]

    environment = local.backend_runtime_env

    mountPoints = local.shared_uploads_mount_points

    secrets = concat(
      local.backend_base_secrets,
      local.include_optional_secrets ? local.backend_stripe_secrets : []
    )

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = local.beat_log_group_name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  dynamic "volume" {
    for_each = local.shared_uploads_enabled ? [1] : []
    content {
      name = local.uploads_volume_name
      efs_volume_configuration {
        file_system_id     = local.resolved_efs_file_system_id
        transit_encryption = "ENABLED"

        dynamic "authorization_config" {
          for_each = local.resolved_efs_access_point_id != "" ? [1] : []
          content {
            access_point_id = local.resolved_efs_access_point_id
            iam             = "DISABLED"
          }
        }
      }
    }
  }

  depends_on = [aws_efs_mount_target.uploads]
}

# --- Frontend Task Definition ---
resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project_name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.frontend_cpu
  memory                   = var.frontend_memory
  execution_role_arn       = local.ecs_task_execution_role_arn
  task_role_arn            = local.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "frontend"
    image     = "${aws_ecr_repository.frontend.repository_url}:${var.frontend_image_tag}"
    essential = true

    portMappings = [{
      containerPort = 3000
      protocol      = "tcp"
    }]

    environment = [
      { name = "NODE_ENV", value = "production" },
      { name = "PORT", value = "3000" },
      { name = "HOSTNAME", value = "0.0.0.0" },
      { name = "NODE_OPTIONS", value = var.frontend_node_options },
      { name = "AUTH_TRUST_HOST", value = "true" },
      { name = "AUTH_URL", value = local.resolved_app_base_url },
      { name = "NEXTAUTH_URL", value = local.resolved_frontend_nextauth_url },
      { name = "NEXT_PUBLIC_API_URL", value = var.next_public_api_url },
      # Sandbox-only tester bypass gate (forced off outside sandbox).
      { name = "SANDBOX_EMAIL_BYPASS_ENABLED", value = var.app_mode == "sandbox" ? tostring(var.sandbox_email_bypass_enabled) : "false" },
      { name = "EMAIL_PROVIDER", value = lower(var.email_provider) },
      { name = "EMAIL_FROM", value = var.email_from },
      { name = "EMAIL_FROM_NAME", value = var.email_from_name },
      { name = "AWS_REGION", value = var.aws_region },
    ]

    secrets = concat(
      # Same pattern as backend: required first, optional provider key by mode.
      local.frontend_base_secrets,
      local.include_optional_secrets ? local.frontend_email_provider_secrets : []
    )

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = local.frontend_log_group_name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

# --- Backend Service ---
resource "aws_ecs_service" "backend" {
  name                   = "${var.project_name}-backend"
  cluster                = aws_ecs_cluster.main.id
  task_definition        = aws_ecs_task_definition.backend.arn
  desired_count          = var.backend_desired_count
  launch_type            = "FARGATE"
  enable_execute_command = true

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [local.ecs_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = local.backend_target_group_arn
    container_name   = "backend"
    container_port   = 8000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  health_check_grace_period_seconds = 60

  depends_on = [aws_lb_listener.http]
}

# --- Frontend Service ---
resource "aws_ecs_service" "frontend" {
  name            = "${var.project_name}-frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.frontend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [local.ecs_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = local.frontend_target_group_arn
    container_name   = "frontend"
    container_port   = 3000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  health_check_grace_period_seconds = 60

  depends_on = [aws_lb_listener.http]
}

# --- Worker Service ---
resource "aws_ecs_service" "worker" {
  name                   = "${var.project_name}-worker"
  cluster                = aws_ecs_cluster.main.id
  task_definition        = aws_ecs_task_definition.worker.arn
  desired_count          = var.worker_desired_count
  launch_type            = "FARGATE"
  enable_execute_command = true

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [local.ecs_security_group_id]
    assign_public_ip = false
  }
}

# --- Beat Service ---
resource "aws_ecs_service" "beat" {
  name                   = "${var.project_name}-beat"
  cluster                = aws_ecs_cluster.main.id
  task_definition        = aws_ecs_task_definition.beat.arn
  desired_count          = var.beat_desired_count
  launch_type            = "FARGATE"
  enable_execute_command = true

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [local.ecs_security_group_id]
    assign_public_ip = false
  }
}
