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
  resolved_app_base_url = var.app_base_url != "" ? var.app_base_url : "http://${aws_lb.main.dns_name}"
  resolved_allowed_origins = var.allowed_origins != "" ? var.allowed_origins : local.resolved_app_base_url
  resolved_frontend_nextauth_url = (
    var.frontend_nextauth_url != ""
    ? var.frontend_nextauth_url
    : local.resolved_app_base_url
  )
  include_optional_secrets = var.app_mode == "production" || var.inject_optional_sandbox_secrets

  backend_base_secrets = [
    { name = "DATABASE_URL", valueFrom = "${var.secrets_manager_arn}:DATABASE_URL::" },
    { name = "REDIS_URL", valueFrom = "${var.secrets_manager_arn}:REDIS_URL::" },
    { name = "NEXTAUTH_SECRET", valueFrom = "${var.secrets_manager_arn}:NEXTAUTH_SECRET::" },
  ]
  backend_stripe_secrets = [
    { name = "STRIPE_SECRET_KEY", valueFrom = "${var.secrets_manager_arn}:STRIPE_SECRET_KEY::" },
    { name = "STRIPE_WEBHOOK_SECRET", valueFrom = "${var.secrets_manager_arn}:STRIPE_WEBHOOK_SECRET::" },
    { name = "STRIPE_PRICE_ID", valueFrom = "${var.secrets_manager_arn}:STRIPE_PRICE_ID::" },
  ]

  frontend_base_secrets = [
    { name = "AUTH_SECRET", valueFrom = "${var.secrets_manager_arn}:NEXTAUTH_SECRET::" },
    { name = "DATABASE_URL", valueFrom = "${var.secrets_manager_arn}:FRONTEND_DATABASE_URL::" },
  ]
  frontend_brevo_secret = [
    { name = "BREVO_API_KEY", valueFrom = "${var.secrets_manager_arn}:BREVO_API_KEY::" },
  ]
}

# --- Backend Task Definition ---
resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "backend"
    image     = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
    essential = true

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    environment = [
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
    ]

    secrets = concat(
      local.backend_base_secrets,
      local.include_optional_secrets ? local.backend_stripe_secrets : []
    )

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.backend.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

# --- Frontend Task Definition ---
resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project_name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.frontend_cpu
  memory                   = var.frontend_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "frontend"
    image     = "${aws_ecr_repository.frontend.repository_url}:${var.frontend_image_tag}"
    essential = true

    portMappings = [{
      containerPort = 3000
      protocol      = "tcp"
    }]

    environment = [
      { name = "APP_MODE", valueFrom = "${var.secrets_manager_arn}:APP_MODE::" },
      { name = "NODE_ENV", valueFrom = "${var.secrets_manager_arn}:APP_MODE::" },
      { name = "PORT", value = "3000" },
      { name = "HOSTNAME", value = "0.0.0.0" },
      { name = "AUTH_TRUST_HOST", value = "true" },
      { name = "NEXTAUTH_URL", value = local.resolved_frontend_nextauth_url },
      { name = "NEXT_PUBLIC_API_URL", value = var.next_public_api_url },
      { name = "EMAIL_FROM", value = var.email_from },
      { name = "EMAIL_FROM_NAME", value = var.email_from_name },
    ]


    secrets = [
      { name = "AUTH_SECRET", valueFrom = "${var.secrets_manager_arn}:AUTH_SECRET::" },
      { name = "DATABASE_URL", valueFrom = "${var.secrets_manager_arn}:DATABASE_URL::" },
      { name = "AUTH_URL", value = "http://${aws_lb.main.dns_name}" },
      { name = "BREVO_API_KEY", valueFrom = "${var.secrets_manager_arn}:BREVO_API_KEY::" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.frontend.name
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
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
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
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
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
