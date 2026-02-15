# --- ElastiCache Security Group ---
resource "aws_security_group" "redis" {
  count = var.create_data_services ? 1 : 0

  name        = "${var.project_name}-redis-sg"
  description = "Allow Redis access from ECS tasks only"
  vpc_id      = local.vpc_id

  tags = { Name = "${var.project_name}-redis-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_ecs" {
  count = var.create_data_services ? 1 : 0

  security_group_id            = aws_security_group.redis[0].id
  referenced_security_group_id = local.ecs_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}

resource "aws_vpc_security_group_egress_rule" "redis_all" {
  count = var.create_data_services ? 1 : 0

  security_group_id = aws_security_group.redis[0].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# --- ElastiCache Subnet Group (uses existing private subnets) ---
resource "aws_elasticache_subnet_group" "main" {
  count = var.create_data_services ? 1 : 0

  name       = "${var.project_name}-redis-subnet"
  subnet_ids = local.private_subnet_ids

  tags = { Name = "${var.project_name}-redis-subnet" }
}

# --- ElastiCache Redis (free-tier eligible) ---
resource "aws_elasticache_cluster" "main" {
  count = var.create_data_services ? 1 : 0

  cluster_id           = "${var.project_name}-redis"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  port                 = 6379
  parameter_group_name = "default.redis7"

  subnet_group_name  = aws_elasticache_subnet_group.main[0].name
  security_group_ids = [aws_security_group.redis[0].id]

  maintenance_window = "sun:05:00-sun:06:00"

  tags = { Name = "${var.project_name}-redis" }
}
