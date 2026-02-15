# --- ECS Cluster ---
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = { Name = "${var.project_name}-cluster" }
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
      { name = "APP_ENV", value = "production" },
      { name = "LOG_LEVEL", value = "INFO" },
      { name = "PINECONE_INDEX_NAME", value = "arbiter-rules" },
    ]

    secrets = [
      { name = "DATABASE_URL", valueFrom = "${var.secrets_manager_arn}:DATABASE_URL::" },
      { name = "REDIS_URL", valueFrom = "${var.secrets_manager_arn}:REDIS_URL::" },
      { name = "OPENAI_API_KEY", valueFrom = "${var.secrets_manager_arn}:OPENAI_API_KEY::" },
      { name = "ANTHROPIC_API_KEY", valueFrom = "${var.secrets_manager_arn}:ANTHROPIC_API_KEY::" },
      { name = "PINECONE_API_KEY", valueFrom = "${var.secrets_manager_arn}:PINECONE_API_KEY::" },
      { name = "SUPABASE_URL", valueFrom = "${var.secrets_manager_arn}:SUPABASE_URL::" },
      { name = "SUPABASE_ANON_KEY", valueFrom = "${var.secrets_manager_arn}:SUPABASE_ANON_KEY::" },
      { name = "SUPABASE_JWT_SECRET", valueFrom = "${var.secrets_manager_arn}:SUPABASE_JWT_SECRET::" },
      { name = "STRIPE_SECRET_KEY", valueFrom = "${var.secrets_manager_arn}:STRIPE_SECRET_KEY::" },
      { name = "STRIPE_WEBHOOK_SECRET", valueFrom = "${var.secrets_manager_arn}:STRIPE_WEBHOOK_SECRET::" },
      { name = "STRIPE_PRICE_ID", valueFrom = "${var.secrets_manager_arn}:STRIPE_PRICE_ID::" },
      { name = "COHERE_API_KEY", valueFrom = "${var.secrets_manager_arn}:COHERE_API_KEY::" },
    ]

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
      { name = "NODE_ENV", value = "production" },
      { name = "PORT", value = "3000" },
      { name = "HOSTNAME", value = "0.0.0.0" },
      { name = "AUTH_TRUST_HOST", value = "true" },
      { name = "AUTH_URL", value = "http://${aws_lb.main.dns_name}" },
      { name = "BREVO_API_KEY", valueFrom = "${var.secrets_manager_arn}:BREVO_API_KEY::" },
    ]

    secrets = [
      { name = "AUTH_SECRET", valueFrom = "${var.secrets_manager_arn}:AUTH_SECRET::" },
      { name = "DATABASE_URL", valueFrom = "${var.secrets_manager_arn}:DATABASE_URL::" },
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
