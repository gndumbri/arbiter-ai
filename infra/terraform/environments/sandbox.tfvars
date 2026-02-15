# Full AWS sandbox bootstrap profile.
# This file is intentionally non-secret; secrets still come from CI -var args.

environment = "sandbox"
app_mode    = "sandbox"
app_env     = "sandbox"

# Bootstrap foundational infra in sandbox.
create_networking            = true
create_ecs_task_roles        = true
create_cloudwatch_log_groups = true
create_data_services         = true
create_efs_resources         = true
enable_shared_uploads        = true

# CI OIDC role is typically pre-created outside this stack.
create_github_actions_iam = false

# Sandbox ergonomics.
inject_optional_sandbox_secrets = false
sandbox_email_bypass_enabled    = true

# Cost-aware baseline.
backend_desired_count  = 1
frontend_desired_count = 1
worker_desired_count   = 1
beat_desired_count     = 1
