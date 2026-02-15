# --- SES Domain Identity (email sending) ---

resource "aws_ses_domain_identity" "main" {
  domain = var.ses_domain
}

resource "aws_ses_domain_dkim" "main" {
  domain = aws_ses_domain_identity.main.domain
}

# --- IAM: Allow frontend ECS task role to send emails via SES ---

resource "aws_iam_role_policy" "ecs_task_ses" {
  name = "${var.project_name}-ecs-task-ses"
  role = aws_iam_role.ecs_task.id

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
