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
