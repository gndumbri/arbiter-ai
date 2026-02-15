# Shared EFS volume for backend <-> worker upload handoff.
# WHY: Rules upload route writes PDFs to UPLOADS_DIR, then Celery workers ingest
# them asynchronously. On ECS, backend and worker tasks do not share local disk,
# so a network file system is required for reliable ingestion.

locals {
  manage_uploads_efs      = var.enable_shared_uploads && var.create_efs_resources
  resolved_efs_file_system_id = var.create_efs_resources ? aws_efs_file_system.uploads[0].id : var.existing_efs_file_system_id
  resolved_efs_access_point_id = var.create_efs_resources ? aws_efs_access_point.uploads[0].id : var.existing_efs_access_point_id
  shared_uploads_enabled = var.enable_shared_uploads && local.resolved_efs_file_system_id != ""
}

check "shared_uploads_inputs" {
  assert = !var.enable_shared_uploads || local.resolved_efs_file_system_id != ""

  error_message = "enable_shared_uploads=true requires either create_efs_resources=true or existing_efs_file_system_id to be set."
}

resource "aws_security_group" "efs" {
  count = local.manage_uploads_efs ? 1 : 0

  name        = "${var.project_name}-efs-sg"
  description = "Allow NFS access from ECS tasks"
  vpc_id      = local.vpc_id

  tags = { Name = "${var.project_name}-efs-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "efs_from_ecs" {
  count = local.manage_uploads_efs ? 1 : 0

  security_group_id            = aws_security_group.efs[0].id
  referenced_security_group_id = aws_security_group.ecs.id
  ip_protocol                  = "tcp"
  from_port                    = 2049
  to_port                      = 2049
}

resource "aws_vpc_security_group_egress_rule" "efs_all" {
  count = local.manage_uploads_efs ? 1 : 0

  security_group_id = aws_security_group.efs[0].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_efs_file_system" "uploads" {
  count = local.manage_uploads_efs ? 1 : 0

  creation_token   = "${var.project_name}-uploads"
  encrypted        = true
  throughput_mode  = "bursting"
  performance_mode = "generalPurpose"

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  tags = { Name = "${var.project_name}-uploads-efs" }
}

resource "aws_efs_mount_target" "uploads" {
  count = local.manage_uploads_efs ? length(local.private_subnet_ids) : 0

  file_system_id  = aws_efs_file_system.uploads[0].id
  subnet_id       = local.private_subnet_ids[count.index]
  security_groups = [aws_security_group.efs[0].id]
}

resource "aws_efs_access_point" "uploads" {
  count = local.manage_uploads_efs ? 1 : 0

  file_system_id = aws_efs_file_system.uploads[0].id

  posix_user {
    uid = 1000
    gid = 1000
  }

  root_directory {
    path = "/uploads"
    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "0775"
    }
  }

  tags = { Name = "${var.project_name}-uploads-ap" }
}
