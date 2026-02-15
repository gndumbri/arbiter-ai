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

