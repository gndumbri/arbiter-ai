resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project_name}-backend"
  retention_in_days = 30

  tags = { Name = "${var.project_name}-backend-logs" }
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${var.project_name}-frontend"
  retention_in_days = 30

  tags = { Name = "${var.project_name}-frontend-logs" }
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project_name}-worker"
  retention_in_days = 30

  tags = { Name = "${var.project_name}-worker-logs" }
}

resource "aws_cloudwatch_log_group" "beat" {
  name              = "/ecs/${var.project_name}-beat"
  retention_in_days = 30

  tags = { Name = "${var.project_name}-beat-logs" }
}
