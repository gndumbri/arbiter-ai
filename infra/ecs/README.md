# ECS Task Definition Templates

This folder contains canonical ECS task-definition templates for Arbiter AI.

## Backend

Use `backend-task-definition.json` as the source of truth for backend task config.

Important:
- It is configured for **Bedrock + pgvector**.
- It intentionally does **not** include `PINECONE_API_KEY`.
- ECS fails startup if `containerDefinitions[].secrets` references a JSON key missing in Secrets Manager.

If you change providers, update both:
- `containerDefinitions[].environment` provider vars
- `containerDefinitions[].secrets` to include only keys required by that provider

Example:
- Switching to OpenAI requires adding `OPENAI_API_KEY` secret mapping.
- Staying on Bedrock should not include `OPENAI_API_KEY` or `PINECONE_API_KEY`.

Frontend email delivery follows the same rule:
- `EMAIL_PROVIDER=ses` should map `EMAIL_SERVER` (SES SMTP URI) in ECS secrets.
- `EMAIL_PROVIDER=brevo` should map `BREVO_API_KEY`.
- `EMAIL_PROVIDER=console` should not map provider secrets.

The same task definition can be reused for separate ECS services:
- API service: default command (FastAPI)
- Worker service: override command to `celery -A app.workers.celery_app worker --loglevel=info`
- Beat service: override command to `celery -A app.workers.celery_app beat --loglevel=info`

Important for ECS:
- Backend and worker must mount the same shared uploads path (EFS) at `/tmp/arbiter_uploads`.
- Without shared storage, rules upload handoff to Celery will fail because worker tasks cannot read backend local disk.

Periodic catalog/rules refresh is controlled by environment vars in this template:
- `CATALOG_SYNC_ENABLED`, `CATALOG_SYNC_CRON`, `CATALOG_RANKED_GAME_LIMIT`
- `OPEN_RULES_SYNC_ENABLED`, `OPEN_RULES_SYNC_CRON`, `OPEN_RULES_MAX_DOCUMENTS`, `OPEN_RULES_ALLOWED_LICENSES`, `OPEN_RULES_FORCE_REINDEX`
