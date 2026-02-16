# Canonical AWS production profile.
# Keep this file non-secret; secrets still come from CI -var args / secret vars.

environment = "production"
app_mode    = "production"
app_env     = "production"

# Current production stack is Terraform-managed.
# Keep these true to prevent accidental destructive "reuse mode" drift.
create_networking              = true
create_service_security_groups = true
create_alb_resources           = true
create_ecs_task_roles          = true
manage_ecs_task_role_policies  = true
create_cloudwatch_log_groups   = true
create_data_services           = true
create_efs_resources           = false
enable_shared_uploads          = false

# CI OIDC role is currently managed in-state.
create_github_actions_iam = true

# Runtime defaults for production behavior.
inject_optional_sandbox_secrets = false
sandbox_email_bypass_enabled    = false
email_provider                  = "ses"
email_from                      = "noreply@arbiter-ai.com"

# Keep catalog + open-license rules synchronized in production.
catalog_sync_enabled        = true
catalog_sync_cron           = "15 */6 * * *"
catalog_ranked_game_limit   = 1000
open_rules_sync_enabled     = true
open_rules_sync_cron        = "45 4 * * *"
open_rules_max_documents    = 20
open_rules_allowed_licenses = "creative commons,open gaming license,orc"
open_rules_force_reindex    = false

# SES domain identity is managed externally in production.
# Keep empty to avoid Terraform SES domain management with restricted CI roles.
ses_domain = ""

# Cost/availability baseline.
backend_desired_count  = 1
frontend_desired_count = 1
worker_desired_count   = 1
beat_desired_count     = 1
