# Shared EFS volume for backend <-> worker upload handoff.
# WHY: Rules upload route writes PDFs to UPLOADS_DIR, then Celery workers ingest
# them asynchronously. On ECS, backend and worker tasks do not share local disk,
# so a network file system is required for reliable ingestion.

resource "aws_security_group" "efs" {
  name        = "${var.project_name}-efs-sg"
  description = "Allow NFS access from ECS tasks"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.project_name}-efs-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "efs_from_ecs" {
  security_group_id            = aws_security_group.efs.id
  referenced_security_group_id = aws_security_group.ecs.id
  ip_protocol                  = "tcp"
  from_port                    = 2049
  to_port                      = 2049
}

resource "aws_vpc_security_group_egress_rule" "efs_all" {
  security_group_id = aws_security_group.efs.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_efs_file_system" "uploads" {
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
  count = length(aws_subnet.private)

  file_system_id  = aws_efs_file_system.uploads.id
  subnet_id       = aws_subnet.private[count.index].id
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_access_point" "uploads" {
  file_system_id = aws_efs_file_system.uploads.id

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
