---
description: How to verify every feature is connected end-to-end from frontend to backend to database
---

# End-to-End Integration Checklist

Every feature in Arbiter AI must be verified as fully connected — from the UI button click all the way through API → service logic → database/vector store → response → UI rendering. No orphaned code, no dead endpoints, no unconnected pages.

## The Integration Rule

> **If a frontend page calls an API endpoint, that endpoint must exist, be routed, be authenticated, hit the correct service layer, persist to the correct store, and return data the frontend actually renders.**

## Steps for Every Feature

### 1. Trace the Full Stack Path

Before marking a feature as complete, document its full path:

```
[UI Component] → [API Call] → [Route Handler] → [Service/Core Logic] → [Database/Store] → [Response] → [UI Rendering]
```

**Example — "Ask a Rules Question":**

```
ChatInterface.tsx
  → POST /api/v1/judge (lib/api.ts)
    → app/api/routes/judge.py (auth middleware validates JWT)
      → app/core/retriever.py (hybrid search: Pinecone + BM25)
      → app/core/reranker.py (cross-encoder + hierarchy sort)
      → app/core/judge.py (LLM verdict generation)
      → app/db/ (insert into query_audit_log)
    → Response: { verdict, confidence, citations, conflicts }
  → ChatInterface renders verdict
  → CitationCard renders each citation
  → ConfidenceBadge renders confidence
  → ConflictAlert renders if conflicts present
```

### 2. Verify Every Connection Point

For each feature, check ALL of these:

#### Frontend → API

- [ ] API client function exists in `lib/api.ts` for every endpoint the UI calls
- [ ] TypeScript types in `lib/types.ts` match the API response schema
- [ ] Loading states are handled (spinner/skeleton while waiting)
- [ ] Error states are handled (network error, 4xx, 5xx)
- [ ] Auth token is attached to every authenticated request

#### API → Routes

- [ ] Route is registered in the FastAPI app (check `main.py` router includes)
- [ ] Route path matches what the frontend calls
- [ ] HTTP method matches (GET vs POST vs PATCH vs DELETE)
- [ ] Auth middleware is applied (JWT for users, API key for publishers)
- [ ] Request validation matches the frontend's payload shape
- [ ] Rate limiting is applied per the tier config

#### Routes → Service Layer

- [ ] Route handler calls the correct service/core function
- [ ] Dependencies are injected correctly (DB session, Redis, Pinecone client)
- [ ] Errors from the service layer are caught and mapped to HTTP error codes

#### Service → Data Store

- [ ] Database queries use parameterized SQL (no SQL injection)
- [ ] Pinecone queries are scoped to the correct namespace
- [ ] Redis operations use the correct key prefix
- [ ] Transactions are used where atomicity is required

#### Response → UI

- [ ] Response shape matches TypeScript types
- [ ] All fields the UI renders are present in the response
- [ ] Nullable fields are handled in the UI (null checks, fallbacks)
- [ ] Pagination is handled if the endpoint is paginated

### 3. Feature-by-Feature Integration Matrix

Verify each feature row is fully connected:

| Feature          | Frontend Page           | API Endpoint                             | Route File     | Core Logic                                | Data Store                     | Status |
| ---------------- | ----------------------- | ---------------------------------------- | -------------- | ----------------------------------------- | ------------------------------ | ------ |
| Sign Up          | `auth/signup/page.tsx`  | Supabase Auth                            | —              | —                                         | `users` table                  | ☐      |
| Log In           | `auth/login/page.tsx`   | Supabase Auth                            | —              | —                                         | `users` table                  | ☐      |
| Create Session   | `library/page.tsx`      | `POST /api/v1/sessions`                  | `sessions.py`  | —                                         | `sessions` table               | ☐      |
| Upload PDF       | `session/[id]/page.tsx` | `POST /api/v1/rules/upload`              | `rules.py`     | `ingestion.py`                            | `ruleset_metadata` + Pinecone  | ☐      |
| Poll Status      | `session/[id]/page.tsx` | `GET /api/v1/rules/{id}/status`          | `rules.py`     | —                                         | `ruleset_metadata`             | ☐      |
| Ask Question     | `session/[id]/page.tsx` | `POST /api/v1/judge`                     | `judge.py`     | `retriever.py`, `reranker.py`, `judge.py` | Pinecone + `query_audit_log`   | ☐      |
| Give Feedback    | `session/[id]/page.tsx` | `POST /api/v1/judge/{id}/feedback`       | `judge.py`     | —                                         | `query_audit_log`              | ☐      |
| View Library     | `library/page.tsx`      | `GET /api/v1/library`                    | `library.py`   | —                                         | `user_game_library`            | ☐      |
| Add to Library   | `catalog/page.tsx`      | `POST /api/v1/library/add`               | `library.py`   | —                                         | `user_game_library`            | ☐      |
| Browse Catalog   | `catalog/page.tsx`      | `GET /api/v1/catalog`                    | `catalog.py`   | —                                         | `official_rulesets`            | ☐      |
| Upgrade to PRO   | `billing/page.tsx`      | `POST /api/v1/billing/checkout`          | `billing.py`   | —                                         | Stripe → webhook → `users`     | ☐      |
| Manage Billing   | `billing/page.tsx`      | `POST /api/v1/billing/portal`            | `billing.py`   | —                                         | Stripe                         | ☐      |
| Publisher Upload | (external API)          | `POST /api/v1/publisher/rulesets/upload` | `publisher.py` | `ingestion.py`                            | `official_rulesets` + Pinecone | ☐      |

### 4. Dead Code / Orphan Detection

Periodically scan for disconnected pieces:

// turbo

```bash
# Find backend route files and check they're imported in main.py
echo "=== Route files ===" && find backend/app/api/routes -name "*.py" -not -name "__init__*" | sort
echo "=== Registered in main.py ===" && grep -n "include_router\|router" backend/app/main.py 2>/dev/null || echo "main.py not found yet"
```

// turbo

```bash
# Find frontend pages and check they have corresponding API calls
echo "=== Frontend pages ===" && find frontend/src/app -name "page.tsx" | sort
echo "=== API client functions ===" && grep -n "export.*function\|export.*const.*=" frontend/src/lib/api.ts 2>/dev/null || echo "api.ts not found yet"
```

### 5. Environment Variable Verification

Every service connection requires config. Verify nothing is hardcoded:

- [ ] All API URLs come from environment variables
- [ ] All API keys come from environment variables
- [ ] `.env.example` lists every required variable
- [ ] Frontend env vars use `NEXT_PUBLIC_` prefix where needed
- [ ] No secrets are committed to git (check `.gitignore`)

### 6. Smoke Test Sequence

After any major change, run through this manually or via integration tests:

1. **Auth:** Sign up → Log in → Verify JWT is valid
2. **Library:** View library → Browse catalog → Add game → Verify library updated
3. **Ingestion:** Create session → Upload PDF → Poll status → Verify INDEXED
4. **Query:** Ask question → Receive verdict → Check citations render → Give feedback
5. **Billing:** Click upgrade → Complete Stripe checkout → Verify tier = PRO
6. **Publisher:** Authenticate with API key → Upload ruleset → Verify in catalog

## Anti-Patterns to Avoid

- ❌ Frontend page that calls an endpoint that doesn't exist yet
- ❌ Backend endpoint that no frontend page ever calls
- ❌ TypeScript types that don't match the API response shape
- ❌ Database tables with no migration and no route that writes to them
- ❌ Hardcoded URLs, API keys, or connection strings
- ❌ Features that work in isolation but break when connected
- ❌ Missing error handling at any layer boundary
