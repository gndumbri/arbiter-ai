# --- RDS Security Group ---
check "rds_password_when_enabled" {
  assert = !var.create_data_services || trimspace(var.db_password) != ""

  error_message = "create_data_services=true requires db_password."
}

resource "aws_security_group" "rds" {
  count = var.create_data_services ? 1 : 0

  name        = "${var.project_name}-rds-sg"
  description = "Allow PostgreSQL access from ECS tasks only"
  vpc_id      = local.vpc_id

  tags = { Name = "${var.project_name}-rds-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_ecs" {
  count = var.create_data_services ? 1 : 0

  security_group_id            = aws_security_group.rds[0].id
  referenced_security_group_id = aws_security_group.ecs.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "rds_all" {
  count = var.create_data_services ? 1 : 0

  security_group_id = aws_security_group.rds[0].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# --- DB Subnet Group (uses existing private subnets) ---
resource "aws_db_subnet_group" "main" {
  count = var.create_data_services ? 1 : 0

  name       = "${var.project_name}-db-subnet"
  subnet_ids = local.private_subnet_ids

  tags = { Name = "${var.project_name}-db-subnet" }
}

# --- RDS PostgreSQL (free-tier eligible) ---
resource "aws_db_instance" "main" {
  count = var.create_data_services ? 1 : 0

  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = "16"

  instance_class        = var.db_instance_class
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main[0].name
  vpc_security_group_ids = [aws_security_group.rds[0].id]

  multi_az            = false
  publicly_accessible = false
  skip_final_snapshot = var.environment != "production"

  final_snapshot_identifier = var.environment == "production" ? "${var.project_name}-db-final" : null

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:30-sun:05:30"

  tags = { Name = "${var.project_name}-db" }
}
