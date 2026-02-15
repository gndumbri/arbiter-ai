data "aws_lb" "existing" {
  count = var.create_alb_resources ? 0 : 1
  name  = "${var.project_name}-alb"
}

data "aws_lb_target_group" "existing_backend" {
  count = (!var.create_alb_resources && var.existing_backend_target_group_arn == "") ? 1 : 0
  name  = "${var.project_name}-backend-tg"
}

data "aws_lb_target_group" "existing_frontend" {
  count = (!var.create_alb_resources && var.existing_frontend_target_group_arn == "") ? 1 : 0
  name  = "${var.project_name}-frontend-tg"
}

locals {
  # HTTPS listener is optional so early sandbox deploys can run with HTTP only.
  # When a cert ARN is provided, all path rules are bound to the HTTPS listener.
  use_https_listener = var.alb_certificate_arn != ""

  alb_arn      = var.create_alb_resources ? aws_lb.main[0].arn : data.aws_lb.existing[0].arn
  alb_dns_name = var.create_alb_resources ? aws_lb.main[0].dns_name : data.aws_lb.existing[0].dns_name

  backend_target_group_arn = var.create_alb_resources ? aws_lb_target_group.backend[0].arn : (
    var.existing_backend_target_group_arn != "" ? var.existing_backend_target_group_arn : data.aws_lb_target_group.existing_backend[0].arn
  )
  frontend_target_group_arn = var.create_alb_resources ? aws_lb_target_group.frontend[0].arn : (
    var.existing_frontend_target_group_arn != "" ? var.existing_frontend_target_group_arn : data.aws_lb_target_group.existing_frontend[0].arn
  )

  rules_listener_arn = var.create_alb_resources ? (
    local.use_https_listener ? aws_lb_listener.https[0].arn : aws_lb_listener.http[0].arn
  ) : ""
}

check "existing_alb_inputs" {
  assert {
    condition = var.create_alb_resources || (
      local.alb_arn != "" &&
      local.backend_target_group_arn != "" &&
      local.frontend_target_group_arn != ""
    )

    error_message = "create_alb_resources=false requires an existing ALB and backend/frontend target groups (by explicit ARNs or discoverable names)."
  }
}

# --- Application Load Balancer ---
resource "aws_lb" "main" {
  count = var.create_alb_resources ? 1 : 0

  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [local.alb_security_group_id]
  subnets            = local.public_subnet_ids

  tags = { Name = "${var.project_name}-alb" }
}

# --- Target Groups ---
resource "aws_lb_target_group" "backend" {
  count = var.create_alb_resources ? 1 : 0

  name        = "${var.project_name}-backend-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = local.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Name = "${var.project_name}-backend-tg" }
}

resource "aws_lb_target_group" "frontend" {
  count = var.create_alb_resources ? 1 : 0

  name        = "${var.project_name}-frontend-tg"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = local.vpc_id
  target_type = "ip"

  health_check {
    path                = "/"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Name = "${var.project_name}-frontend-tg" }
}

# --- Listener (port 80) with path-based routing ---
resource "aws_lb_listener" "http" {
  count = var.create_alb_resources ? 1 : 0

  load_balancer_arn = aws_lb.main[0].arn
  port              = 80
  protocol          = "HTTP"

  dynamic "default_action" {
    for_each = local.use_https_listener ? [1] : []
    content {
      # Force canonical HTTPS in environments with ACM configured.
      type = "redirect"
      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }

  dynamic "default_action" {
    for_each = local.use_https_listener ? [] : [1]
    content {
      # HTTP-only fallback (no certificate yet): serve frontend directly.
      type             = "forward"
      target_group_arn = local.frontend_target_group_arn
    }
  }
}

resource "aws_lb_listener" "https" {
  count = var.create_alb_resources && local.use_https_listener ? 1 : 0

  load_balancer_arn = aws_lb.main[0].arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.alb_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = local.frontend_target_group_arn
  }
}

# WHY: NextAuth routes (/api/auth/*) are handled by the frontend (Next.js),
# not the backend. This must evaluate before the catch-all /api/* rule.
resource "aws_lb_listener_rule" "nextauth" {
  count = var.create_alb_resources ? 1 : 0

  listener_arn = local.rules_listener_arn
  priority     = 50

  action {
    type             = "forward"
    target_group_arn = local.frontend_target_group_arn
  }

  condition {
    path_pattern {
      values = ["/api/auth/*"]
    }
  }
}

resource "aws_lb_listener_rule" "api" {
  count = var.create_alb_resources ? 1 : 0

  listener_arn = local.rules_listener_arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = local.backend_target_group_arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}

resource "aws_lb_listener_rule" "health" {
  count = var.create_alb_resources ? 1 : 0

  listener_arn = local.rules_listener_arn
  priority     = 200

  action {
    type             = "forward"
    target_group_arn = local.backend_target_group_arn
  }

  condition {
    path_pattern {
      values = ["/health"]
    }
  }
}

resource "aws_lb_listener_rule" "docs" {
  count = var.create_alb_resources ? 1 : 0

  listener_arn = local.rules_listener_arn
  priority     = 300

  action {
    type             = "forward"
    target_group_arn = local.backend_target_group_arn
  }

  condition {
    path_pattern {
      values = ["/docs", "/redoc", "/openapi.json"]
    }
  }
}
