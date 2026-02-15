locals {
  backend_log_group_name  = "/ecs/${var.project_name}-backend"
  frontend_log_group_name = "/ecs/${var.project_name}-frontend"
  worker_log_group_name   = "/ecs/${var.project_name}-worker"
  beat_log_group_name     = "/ecs/${var.project_name}-beat"
}

resource "aws_cloudwatch_log_group" "backend" {
  count = var.create_cloudwatch_log_groups ? 1 : 0

  name              = local.backend_log_group_name
  retention_in_days = var.cloudwatch_log_retention_days

  tags = { Name = "${var.project_name}-backend-logs" }
}

resource "aws_cloudwatch_log_group" "frontend" {
  count = var.create_cloudwatch_log_groups ? 1 : 0

  name              = local.frontend_log_group_name
  retention_in_days = var.cloudwatch_log_retention_days

  tags = { Name = "${var.project_name}-frontend-logs" }
}

resource "aws_cloudwatch_log_group" "worker" {
  count = var.create_cloudwatch_log_groups ? 1 : 0

  name              = local.worker_log_group_name
  retention_in_days = var.cloudwatch_log_retention_days

  tags = { Name = "${var.project_name}-worker-logs" }
}

resource "aws_cloudwatch_log_group" "beat" {
  count = var.create_cloudwatch_log_groups ? 1 : 0

  name              = local.beat_log_group_name
  retention_in_days = var.cloudwatch_log_retention_days

  tags = { Name = "${var.project_name}-beat-logs" }
}
