# One-time imports for resources created manually via CloudShell.
# These blocks can be removed after the first successful `terraform apply`.

import {
  to = aws_ecr_repository.backend
  id = "arbiter-ai-backend"
}

import {
  to = aws_ecr_repository.frontend
  id = "arbiter-ai-frontend"
}

import {
  to = aws_iam_openid_connect_provider.github_actions
  id = "arn:aws:iam::788397033906:oidc-provider/token.actions.githubusercontent.com"
}

import {
  to = aws_iam_role.github_actions
  id = "arbiter-ai-github-actions"
}
