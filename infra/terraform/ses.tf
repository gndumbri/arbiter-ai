# --- SES Domain Identity (email sending) ---

resource "aws_ses_domain_identity" "main" {
  count  = trimspace(var.ses_domain) != "" ? 1 : 0
  domain = trimspace(var.ses_domain)
}

resource "aws_ses_domain_dkim" "main" {
  count  = trimspace(var.ses_domain) != "" ? 1 : 0
  domain = aws_ses_domain_identity.main[0].domain
}

# --- IAM: Allow frontend ECS task role to send emails via SES ---

resource "aws_iam_role_policy" "ecs_task_ses" {
  count = local.manage_task_role_policies && lower(var.email_provider) == "ses" ? 1 : 0

  name = "${var.project_name}-ecs-task-ses"
  role = local.ecs_task_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ]
      Resource = "*"
      Condition = {
        StringEquals = {
          "ses:FromAddress" = var.email_from
        }
      }
    }]
  })
}
