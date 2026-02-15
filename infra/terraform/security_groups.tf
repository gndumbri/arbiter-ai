data "aws_security_group" "existing_alb" {
  count = (!var.create_service_security_groups && var.existing_alb_security_group_id == "") ? 1 : 0

  filter {
    name   = "group-name"
    values = ["${var.project_name}-alb-sg"]
  }

  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }
}

data "aws_security_group" "existing_ecs" {
  count = (!var.create_service_security_groups && var.existing_ecs_security_group_id == "") ? 1 : 0

  filter {
    name   = "group-name"
    values = ["${var.project_name}-ecs-sg"]
  }

  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }
}

locals {
  alb_security_group_id = var.create_service_security_groups ? aws_security_group.alb[0].id : (
    var.existing_alb_security_group_id != "" ? var.existing_alb_security_group_id : data.aws_security_group.existing_alb[0].id
  )
  ecs_security_group_id = var.create_service_security_groups ? aws_security_group.ecs[0].id : (
    var.existing_ecs_security_group_id != "" ? var.existing_ecs_security_group_id : data.aws_security_group.existing_ecs[0].id
  )
}

check "service_security_groups_inputs" {
  assert {
    condition = var.create_service_security_groups || (
      local.alb_security_group_id != "" &&
      local.ecs_security_group_id != ""
    )

    error_message = "create_service_security_groups=false requires existing ALB and ECS security groups (by explicit IDs or discoverable names)."
  }
}

# --- ALB Security Group ---
resource "aws_security_group" "alb" {
  count = var.create_service_security_groups ? 1 : 0

  name        = "${var.project_name}-alb-sg"
  description = "Allow HTTP/HTTPS inbound to ALB"
  vpc_id      = local.vpc_id

  tags = { Name = "${var.project_name}-alb-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  count = var.create_service_security_groups ? 1 : 0

  security_group_id = aws_security_group.alb[0].id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  count = var.create_service_security_groups ? 1 : 0

  security_group_id = aws_security_group.alb[0].id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_all" {
  count = var.create_service_security_groups ? 1 : 0

  security_group_id = aws_security_group.alb[0].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# --- ECS Security Group ---
resource "aws_security_group" "ecs" {
  count = var.create_service_security_groups ? 1 : 0

  name        = "${var.project_name}-ecs-sg"
  description = "Allow traffic from ALB to ECS tasks"
  vpc_id      = local.vpc_id

  tags = { Name = "${var.project_name}-ecs-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "ecs_from_alb" {
  count = var.create_service_security_groups ? 1 : 0

  security_group_id            = aws_security_group.ecs[0].id
  referenced_security_group_id = aws_security_group.alb[0].id
  ip_protocol                  = "tcp"
  from_port                    = 0
  to_port                      = 65535
}

resource "aws_vpc_security_group_egress_rule" "ecs_all" {
  count = var.create_service_security_groups ? 1 : 0

  security_group_id = aws_security_group.ecs[0].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
