# Arbiter AI — Technical Specification (SPEC)

**Version:** 1.0 · **Status:** Active · **Last Updated:** 2026-02-14

---

## 1. System Architecture

### 1.1 Technology Stack

| Layer           | Technology                       | Version   | Purpose                                             |
| --------------- | -------------------------------- | --------- | --------------------------------------------------- |
| **API**         | FastAPI                          | 0.110+    | REST API, async request handling                    |
| **Task Queue**  | Celery + Redis                   | 5.3+ / 7+ | Async ingestion, scheduled cleanup                  |
| **Database**    | PostgreSQL                       | 16        | Relational data, user accounts                      |
| **ORM**         | SQLAlchemy                       | 2.0+      | Database models and queries                         |
| **Migrations**  | Alembic                          | 1.13+     | Schema versioning                                   |
| **Vector DB**   | Pinecone Serverless              | —         | Semantic search, per-tenant namespaces              |
| **Embedding**   | OpenAI `text-embedding-3-small`  | —         | 1536-dim embeddings                                 |
| **LLM**         | OpenAI GPT-4o / Anthropic Claude | —         | Query expansion, verdict generation, classification |
| **PDF Parsing** | Docling / Unstructured           | —         | Layout-aware PDF extraction                         |
| **Frontend**    | Next.js 14+ (App Router)         | 14+       | PWA, React Server Components                        |
| **Auth**        | Supabase Auth                    | —         | JWT, OAuth (Google, GitHub)                         |
| **Billing**     | Stripe                           | —         | Subscriptions, webhooks                             |
| **Virus Scan**  | ClamAV                           | —         | Malware detection                                   |
| **Config**      | pydantic-settings                | 2.0+      | Typed configuration from env vars                   |
| **Reranker**    | Cohere Rerank v3 / bge-reranker  | —         | Cross-encoder scoring                               |

### 1.2 Service Boundaries

```
┌─────────────────────────────────────────────────────┐
│  Frontend (Next.js on Vercel)                       │
│  - SSR pages, PWA shell, Supabase Auth client       │
└──────────────────────┬──────────────────────────────┘
                       │ HTTPS
┌──────────────────────▼──────────────────────────────┐
│  API Server (FastAPI on Fargate)                    │
│  - REST endpoints, JWT validation, rate limiting    │
│  - Writes to Postgres, reads from Pinecone          │
│  - Enqueues jobs to Redis                           │
└──────┬──────────┬──────────────┬────────────────────┘
       │          │              │
   Postgres    Redis         Pinecone
       │          │
       │    ┌─────▼─────────────────────────────┐
       │    │  Celery Worker (isolated container) │
       │    │  - PDF ingestion pipeline           │
       │    │  - NO direct DB access (via API)    │
       │    │  - Ephemeral, destroyed after job   │
       │    └───────────────────────────────────┘
```

---

## 2. Database Schema

### 2.1 PostgreSQL Tables

All user-generated data scoped by `user_id`. Publisher data scoped by `publisher_id`.

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    tier TEXT NOT NULL DEFAULT 'FREE' CHECK (tier IN ('FREE', 'PRO')),
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    tier_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Game Sessions
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    game_name TEXT NOT NULL,
    active_ruleset_ids UUID[],
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- User-uploaded ruleset metadata
CREATE TABLE ruleset_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    game_name TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('BASE', 'EXPANSION', 'ERRATA')),
    source_priority INT NOT NULL DEFAULT 0,
    chunk_count INT DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PROCESSING'
           CHECK (status IN ('PROCESSING', 'INDEXED', 'FAILED', 'EXPIRED')),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Publishers
CREATE TABLE publishers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    api_key_hash TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Official rulesets
CREATE TABLE official_rulesets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    publisher_id UUID REFERENCES publishers(id) ON DELETE CASCADE,
    game_name TEXT NOT NULL,
    game_slug TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('BASE', 'EXPANSION', 'ERRATA')),
    source_priority INT NOT NULL DEFAULT 0,
    version TEXT NOT NULL DEFAULT '1.0',
    chunk_count INT DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PROCESSING'
           CHECK (status IN ('PROCESSING', 'INDEXED', 'FAILED')),
    pinecone_namespace TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- User game library
CREATE TABLE user_game_library (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    game_name TEXT NOT NULL,
    official_ruleset_ids UUID[],
    personal_ruleset_ids UUID[],
    is_favorite BOOLEAN DEFAULT false,
    last_queried TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- File blocklist
CREATE TABLE file_blocklist (
    hash TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    reported_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Query audit log
CREATE TABLE query_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    query_text TEXT NOT NULL,
    expanded_query TEXT,
    verdict_summary TEXT,
    reasoning_chain TEXT,
    confidence FLOAT,
    confidence_reason TEXT,
    citation_ids TEXT[],
    latency_ms INT,
    feedback TEXT CHECK (feedback IN ('up', 'down')),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX idx_ruleset_metadata_user_id ON ruleset_metadata(user_id);
CREATE INDEX idx_ruleset_metadata_session_id ON ruleset_metadata(session_id);
CREATE INDEX idx_ruleset_metadata_status ON ruleset_metadata(status);
CREATE INDEX idx_official_rulesets_publisher_id ON official_rulesets(publisher_id);
CREATE INDEX idx_official_rulesets_game_slug ON official_rulesets(game_slug);
CREATE INDEX idx_user_game_library_user_id ON user_game_library(user_id);
CREATE INDEX idx_query_audit_log_user_id ON query_audit_log(user_id);
CREATE INDEX idx_query_audit_log_session_id ON query_audit_log(session_id);
CREATE INDEX idx_query_audit_log_created_at ON query_audit_log(created_at);
```

### 2.2 Pinecone Configuration

| Setting             | Value                                   |
| ------------------- | --------------------------------------- |
| Index name          | `arbiter-rules`                         |
| Dimensions          | 1536                                    |
| Metric              | cosine                                  |
| User namespace      | `user_{user_id}`                        |
| Publisher namespace | `official_{publisher_slug}_{game_slug}` |

### 2.3 Redis Keys

| Pattern                | Purpose                     | TTL                    |
| ---------------------- | --------------------------- | ---------------------- |
| `rate:{user_id}`       | Sliding-window rate limiter | 60s                    |
| `session:{session_id}` | Session cache               | Matches session expiry |
| `job:{job_id}`         | Ingestion job status        | 24h                    |

---

## 3. API Specification

### 3.1 Authentication

- **Users:** `Authorization: Bearer <supabase_jwt>`
- **Publishers:** `X-Publisher-Key: <api_key>`
- **Webhooks:** Stripe signature verification

### 3.2 Endpoint Summary

| Method | Path                                | Auth      | Description                      |
| ------ | ----------------------------------- | --------- | -------------------------------- |
| GET    | `/health`                           | None      | Service health + DB connectivity |
| POST   | `/api/v1/sessions`                  | JWT       | Create game session              |
| POST   | `/api/v1/rules/upload`              | JWT       | Upload rulebook PDF              |
| GET    | `/api/v1/rules/{id}/status`         | JWT       | Poll ingestion status            |
| POST   | `/api/v1/judge`                     | JWT       | Submit rules question            |
| POST   | `/api/v1/judge/{id}/feedback`       | JWT       | Submit verdict feedback          |
| GET    | `/api/v1/library`                   | JWT       | Get user's game library          |
| POST   | `/api/v1/library/add`               | JWT       | Add game to library              |
| DELETE | `/api/v1/library/{id}`              | JWT       | Remove game from library         |
| PATCH  | `/api/v1/library/{id}/favorite`     | JWT       | Toggle favorite                  |
| GET    | `/api/v1/catalog`                   | JWT       | Browse official rulesets         |
| GET    | `/api/v1/catalog/{slug}`            | JWT       | Get official game details        |
| POST   | `/api/v1/publisher/rulesets/upload` | API Key   | Upload official ruleset          |
| GET    | `/api/v1/publisher/rulesets`        | API Key   | List publisher rulesets          |
| DELETE | `/api/v1/publisher/rulesets/{id}`   | API Key   | Delete official ruleset          |
| POST   | `/api/v1/billing/checkout`          | JWT       | Create Stripe checkout           |
| POST   | `/api/v1/billing/portal`            | JWT       | Create Stripe portal session     |
| POST   | `/api/v1/webhooks/stripe`           | Signature | Stripe webhook receiver          |

### 3.3 Error Codes

| Code                | HTTP | Description                        |
| ------------------- | ---- | ---------------------------------- |
| `VALIDATION_ERROR`  | 422  | Invalid request body or params     |
| `UNAUTHORIZED`      | 401  | Missing or invalid auth            |
| `RATE_LIMITED`      | 429  | Query rate exceeded                |
| `SESSION_EXPIRED`   | 410  | Session no longer active           |
| `PROCESSING_FAILED` | 500  | Ingestion pipeline failure         |
| `NOT_A_RULEBOOK`    | 422  | Layer 2 relevance filter rejection |
| `BLOCKED_FILE`      | 403  | File hash in blocklist             |
| `INTERNAL_ERROR`    | 500  | Unhandled server error             |

---

## 4. Ingestion Pipeline (3-Layer Defense)

### 4.1 Layer 1: Security

1. File → S3/local quarantine directory
2. Validate magic bytes (`%PDF-`), size ≤ 50MB, pages ≤ 500
3. SHA-256 hash → check `file_blocklist`
4. ClamAV scan in Docker container
5. Pass to sandboxed worker (ephemeral container, no DB access)

### 4.2 Layer 2: Relevance Filter

6. OCR first 3 pages
7. GPT-4o-mini classification prompt → YES/NO
8. If NO → delete file, return `NOT_A_RULEBOOK` error

### 4.3 Layer 3: Index & Purge

9. Layout parsing (Docling primary, Unstructured fallback)
10. Recursive semantic chunking (300–500 tokens, 50-token overlap)
11. Header prepending to each chunk
12. Batch embedding (100 chunks/call, exponential backoff)
13. Pinecone upsert + index count verification
14. HARD DELETE source PDF (overwrite + unlink)
15. Update status → `INDEXED`

### 4.4 Chunking Rules

- Split on structural headers: H1 → H2 → H3
- Within sections: paragraph boundaries
- Merge chunks < 200 tokens with neighbor
- Split chunks > 800 tokens at sentence boundaries
- Tables: Markdown format, atomic units (never split rows)

---

## 5. Adjudication Engine

### 5.1 Pipeline Steps

1. **Query expansion:** LLM rewrite + game term extraction + sub-query decomposition
2. **Hybrid search:** Dense (Pinecone, top 50) + Sparse (BM25) → RRF merge
3. **Multi-namespace fan-out:** Search `user_{id}` + official namespaces
4. **Multi-hop retrieval:** Second pass if chunks reference other sections
5. **Cross-encoder rerank:** Score top 50 → select top 10
6. **Hierarchy re-sort:** Promote higher `source_priority` on overlapping chunks
7. **Conflict detection:** Flag contradictions between source types
8. **Verdict generation:** Chain-of-thought LLM with calibrated confidence
9. **Citation truncation:** 300-char snippet cap
10. **Audit log:** Full trace to `query_audit_log`

### 5.2 Confidence Calibration

| Range    | Meaning                                 | Behavior                           |
| -------- | --------------------------------------- | ---------------------------------- |
| 0.9–1.0  | Direct, unambiguous answer              | Green badge                        |
| 0.7–0.89 | Multi-rule inference, well-supported    | Yellow badge                       |
| 0.5–0.69 | Interpretation required, some ambiguity | Yellow badge + caveat              |
| < 0.5    | Insufficient context                    | Red badge + uncertainty disclaimer |

---

## 6. Security Requirements

| Requirement           | Implementation                                                     |
| --------------------- | ------------------------------------------------------------------ |
| File quarantine       | Uploaded files isolated until virus scan clears                    |
| Sandbox execution     | PDF processing in ephemeral containers with no DB/network access   |
| Tenant isolation      | Per-user Pinecone namespaces, `user_id` FK on all rows             |
| Rate limiting         | Redis sliding window: 10/min FREE, 60/min PRO                      |
| Input sanitization    | Query length ≤ 500 chars, HTML/script stripping, parameterized SQL |
| Encryption in transit | TLS required, HSTS headers                                         |
| Secret management     | Environment variables (AWS Secrets Manager in production)          |
| Hash blocklist        | SHA-256 blocklist for known-bad files                              |

---

## 7. Performance Targets

| Metric                   | Target      | Measurement                  |
| ------------------------ | ----------- | ---------------------------- |
| Query latency P50        | < 1.5s      | `query_audit_log.latency_ms` |
| Query latency P95        | < 3.0s      | `query_audit_log.latency_ms` |
| Ingestion (50-page PDF)  | < 60s       | Celery task duration         |
| Ingestion (500-page PDF) | < 5min      | Celery task duration         |
| API throughput           | 100 req/s   | Load testing                 |
| Pinecone query           | < 200ms P95 | Pinecone metrics             |

---

## 8. Testing Strategy

| Level       | Tool                    | Scope                                              |
| ----------- | ----------------------- | -------------------------------------------------- |
| Unit        | pytest                  | Core modules (chunker, embedder, retriever, judge) |
| Integration | pytest + testcontainers | DB, Redis, full pipeline                           |
| E2E         | pytest + httpx          | API endpoints end-to-end                           |
| Frontend    | Vitest + Playwright     | Component + browser tests                          |
| Load        | Locust                  | API throughput under load                          |

### 8.1 Critical Test Cases

1. Multi-column PDF parses correctly (columns not merged)
2. Table-heavy PDF: tables chunked as atomic units
3. Non-rulebook PDF: rejected by Layer 2 within 10 seconds
4. Known-malware PDF: rejected by ClamAV
5. Blocked-hash PDF: rejected instantly
6. Cross-namespace query: official + user results merged correctly
7. Low-confidence query: uncertainty disclaimer returned
8. Conflicting rules: both interpretations shown
9. Rate limit exceeded: 429 returned with retry-after
10. Expired session: 410 returned

---

## 9. Monitoring & Observability

### Prometheus Metrics

- `arbiter_query_latency_seconds` (histogram)
- `arbiter_query_confidence` (histogram)
- `arbiter_ingestion_duration_seconds` (histogram)
- `arbiter_active_sessions` (gauge)
- `arbiter_relevance_filter_rejections_total` (counter)
- `arbiter_low_confidence_verdicts_total` (counter)
- `arbiter_thumbs_down_total` (counter)
- `arbiter_multi_hop_retrieval_total` (counter)

### Alerts

- P95 latency > 5s for 5 min
- Ingestion failure rate > 20% for 15 min
- Error rate > 5% for 5 min
- Thumbs-down rate > 15% for 1 hour

### Tracing

- OpenTelemetry spans: API → Queue → Worker → Pinecone → LLM
- Correlation IDs on all structured logs (`structlog`)
