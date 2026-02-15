# Arbiter AI — Product Requirements Document (PRD)

**Version:** 1.1 · **Status:** Active · **Last Updated:** 2026-02-15

---

## Product Vision

Arbiter AI is the **definitive rules judge** for tabletop gaming. Players upload a game's rulebook, ask questions in plain English, and receive instant, citeable verdicts — backed by the actual rules text, not guesses.

---

## Target Personas

| Persona                  | Need                                                  | Key Feature                           |
| ------------------------ | ----------------------------------------------------- | ------------------------------------- |
| **Mid-Game Player**      | "Can I do this move?" — needs an answer in <3 seconds | Chat interface, fast verdicts         |
| **Café Staff**           | Explain rules to customers across dozens of games     | Game library with official rulesets   |
| **Tournament Organizer** | Authoritative rulings with citation                   | Confidence badges, conflict detection |
| **Publisher**            | Reduce customer support load for rules questions      | Publisher portal, official rulesets   |

---

## Feature Map

### Implementation Snapshot (2026-02-15)

- Production auth path now uses NextAuth server-side token minting and backend HS256 verification.
- Ruleset upload/list/status endpoints are user-scoped and session-scoped, with mock-mode endpoint parity restored.
- Vector retrieval now requires indexed rulesets for a session (no anonymous/session fallback namespace).
- Current upload cap is 20 MB as a cost-control guardrail; tiered size limits remain a roadmap item.
- Active personal ruleset caps are currently enforced at FREE=10 and PRO/ADMIN=50.
- Canonical `APP_BASE_URL` is now separate from CORS `ALLOWED_ORIGINS` for Stripe/invite link correctness.
- IP abuse controls now use trusted proxy-depth parsing (`TRUSTED_PROXY_HOPS`) to prevent spoofed `X-Forwarded-For`.
- Party invite join flow now validates token payload shape and reuses standard party rate limits without runtime errors.
- New environment templates added for AWS sandbox/production bootstrap (`backend/.env.*.example`, `frontend/.env.*.example`).
- "Add Game" wizard now treats `INDEXED`/`COMPLETE`/`PUBLISHED` as chat-ready and routes directly to the created session.
- Party member responses now include display name/email, and Guild member UI shows names instead of raw UUID-only labels.
- Dashboard top nav now removes redundant Settings tab (avatar menu remains) and promotes Ask as the primary right-side CTA.
- Mock library endpoints now persist in-memory add/remove/favorite changes during runtime for realistic frontend testing.
- Shelf dashboard now surfaces claimed library games so "added from Armory" state is visible in the main view.
- AWS deployment now includes a repo-managed ECS backend task-definition template (`infra/ecs/backend-task-definition.json`) to prevent secret-key drift.
- Frontend API client now correctly handles `204/205` no-content responses, preventing false JSON parse failures on delete routes.
- Frontend regression tests now cover API fetcher success/error/no-content behavior (`frontend/src/lib/api.test.ts`).
- Mock API parity was expanded for `users`, `rulings`, `parties`, and `admin` endpoints to match dashboard behavior in `APP_MODE=mock`.
- Backend lint baseline is now clean (`ruff` on `app/` and `tests/`), and flaky async cleanup warnings are filtered in pytest config.
- `make lint` is now self-contained (no local mypy install required) and runs targeted type checks on critical config/environment modules.
- Root quality gates now include frontend checks by default (`make test` runs pytest + Vitest; `make lint` runs backend + frontend lint).
- Judge quality flow was upgraded with stronger grounding prompts, robust JSON normalization, and citation-chunk alignment to improve reliability under real gameplay queries.
- Agent quality flow now applies persona + custom system instructions directly in adjudication while preserving non-overridable safety/grounding constraints.
- Judge flow now includes recent-turn conversation context for higher-quality follow-up rulings (without relaxing citation grounding rules).
- Agent/session creation now stays available during Redis rate-limiter outages (degraded fail-open behavior with warnings), reducing false-create failures.
- Frontend now surfaces backend error messages cleanly (including structured rate-limit payloads) during agent creation.
- Account deletion UX now includes a multi-step, on-brand danger flow with escalating warnings and typed confirmation before irreversible deletion.
- Backend CORS ordering was corrected so browser clients receive CORS headers even on middleware short-circuit responses (rate-limit/auth/errors), fixing agent/session create calls that appeared as CORS failures.
- Root layout now suppresses browser-extension hydration class drift warnings to reduce false-positive React hydration noise in dev.
- Catalog browse/search now includes metadata-only `UPLOAD_REQUIRED` games (not just indexed ones), restoring full Armory discovery from seeded data.
- Shelf "Add Game" flow now preloads Armory entries immediately and keeps a local fallback list, so users see selectable games before typing.
- Session/Judge flow now supports official READY catalog namespaces via `active_ruleset_ids`, enabling no-upload chat when official indexed content exists.
- Alembic migration flow now avoids blocking on missing pgvector extension in local DBs, and a drift-fix migration guarantees session persona columns exist.
- New backend regression tests now cover agent listing and official-ruleset judge namespace wiring (`backend/tests/api/routes/test_agents.py`, `backend/tests/api/routes/test_judge_official_rulesets.py`).
- Ingestion classification prompt now uses structured JSON + confidence gating to reduce non-rulebook acceptance and improve corpus quality.
- New regression tests now cover adjudication prompt flow and ingestion classifier parsing (`backend/tests/unit/test_adjudication.py`, `backend/tests/unit/test_ingestion_classification.py`).
- Armory catalog ingestion now supports BoardGameGeek ranked browse sync (configurable top-N, default 1000) for broader out-of-box game coverage.
- Open-license rules ingestion now supports multi-document Open5e sync (CC/OGL/ORC), including scheduled production refresh via Celery Beat.
- New maintenance commands were added for deterministic sync runs: `backend/scripts/sync_catalog_live.py` and `backend/scripts/sync_open_rules.py`.
- Backend deployment readiness now includes explicit preflight gates (`backend/scripts/preflight.py`, `make preflight-sandbox`, `make preflight-production`) that verify env configuration plus DB/Redis/provider health before promotion.
- Deployment automation now includes a required CI preflight stage (`.github/workflows/deploy.yml`) so ECS service updates are blocked on failed readiness checks.
- Frontend auth/email flow now degrades gracefully in sandbox (console fallback when Brevo is missing or transiently failing) while keeping production strict for delivery quality.
- Ask flow now auto-links exact-name READY official rulesets when sessions were created without explicit linkage, and surfaces actionable indexing guidance instead of opaque judge failures.
- Shelf-to-Ask flow now starts from library entries directly, reusing indexed game sessions or creating official rules-linked sessions so game selection and adjudication context stay aligned.
- Session chat header now shows game/NPC context instead of raw session-id labels, improving in-conversation orientation.
- Ask and chat layouts now use tighter max-width containers for improved readability on large screens.
- Session setup flow now enforces explicit game selection while preserving separate NPC identity/persona fields, preventing mislabeled chats.
- API now supports direct session metadata lookup by ID for more reliable game-context rendering in Ask/chat views.

### F1: Game Library (Dashboard)

**User Story:** As a gamer, I want to save the games I play so I can quickly ask rules questions without re-uploading files every time.

| Capability                    | FREE     | PRO       |
| ----------------------------- | -------- | --------- |
| Browse official catalog       | ✅       | ✅        |
| Add official games to library | Up to 5  | Unlimited |
| Upload personal PDFs          | 10 active | 50 active |
| Personal PDF retention        | 24 hours | 30 days   |
| Favorites & history           | ✅       | ✅        |

**Acceptance Criteria:**

- User can browse a catalog of publisher-verified rulesets
- One-click add to personal library
- Library shows favorite games, recent queries, and upload status
- Combined search across official + personal rulesets

### F2: PDF Upload & Ingestion

**User Story:** As a gamer, I want to upload my rulebook PDF and have it ready for questions within 60 seconds.

| Capability           | Behavior                                         |
| -------------------- | ------------------------------------------------ |
| Drag-and-drop upload | PDF files, ≤ 20 MB (current guardrail)            |
| Progress indicator   | Real-time status (scanning → parsing → indexing) |
| Rejection feedback   | Clear error if file isn't a rulebook             |
| Security             | Virus scan, sandboxed processing                 |

**Acceptance Criteria:**

- Upload starts processing immediately
- Non-rulebooks rejected with clear message within 10 seconds
- Multi-column and table-heavy PDFs are parsed correctly
- Original PDF is deleted after indexing — user is notified

### F3: Rules Adjudication (The Judge)

**User Story:** As a player in the middle of a game, I want to ask a rules question in plain English and get a correct, cited answer.

| Capability             | Behavior                                             |
| ---------------------- | ---------------------------------------------------- |
| Natural-language query | "Can the rogue sneak attack with a thrown dagger?"   |
| Cited verdict          | Answer with page numbers and section references      |
| Confidence indicator   | Green (high), Yellow (moderate), Red (low/uncertain) |
| Conflict detection     | Alerts when base rules conflict with expansion rules |
| Follow-up hints        | Suggests related questions for complex rulings       |

**Acceptance Criteria:**

- Verdicts cite specific page and section
- Confidence < 0.5 triggers "I'm not sure" response with direction
- Conflicting rules shown side-by-side with resolution
- Reasoning chain visible for complex multi-rule questions

### F4: Official Publisher Rulesets

**User Story:** As a publisher, I want to host our official rules on Arbiter so players always have access to the latest, authoritative version.

| Capability       | Behavior                                       |
| ---------------- | ---------------------------------------------- |
| Publisher portal | API-based upload and version management        |
| Version control  | Push updates (errata, FAQ, expansions)         |
| User access      | All users can add official rulesets to library |
| Analytics        | Query volume and common questions per title    |

**Acceptance Criteria:**

- Publisher uploads are processed through the same 3-layer security pipeline
- Users see a verified badge on official rulesets
- Version updates automatically replace old vectors
- Publishers can flag incorrect verdicts for correction

### F5: Accounts, Billing & Social

**User Story:** As a power user, I want to upgrade to PRO, save rulings, and share them with my gaming group.

| Feature            | FREE             | PRO ($9.99/mo) | Enforced?       |
| ------------------ | ---------------- | -------------- | --------------- |
| Sessions           | 24-hour expiry   | 30-day expiry  | ✅ Backend      |
| Active rulesets    | 10               | 50             | ✅ Backend      |
| Max file size      | 20 MB            | 20 MB          | ✅ Backend      |
| Queries/day        | 5 (configurable) | Unlimited      | ✅ Backend      |
| Game library slots | 5                | Unlimited      | ⚠️ Aspirational |
| Saved rulings      | ✅               | ✅             | ✅              |
| Party groups       | ✅               | ✅             | ✅              |

**Acceptance Criteria:**

- Passwordless email login via NextAuth magic links (Brevo transactional email)
- Stripe-powered checkout and self-service portal
- Configurable tier limits via Admin portal (database-backed `subscription_tiers` table)
- Saved rulings with privacy controls (PRIVATE, PARTY, PUBLIC)
- Party management: create/join/leave groups, share rulings with party members
- Admin portal: system stats, user/publisher/tier management (RBAC)
- Redis-backed rate limiting with per-tier daily query caps

### F6: PWA Install

**User Story:** As a mobile user, I want to install Arbiter on my home screen for instant access during game night.

**Acceptance Criteria:**

- Install prompt appears on supported browsers
- Offline fallback page displays when disconnected
- App appears in device app drawer with custom icon

---

### F7: Agent Builder & Embeddable Widget

**User Story:** As a publisher, I want to create a custom AI referee agent and embed it on my website so customers can look up rules directly on my site.

| Capability        | Behavior                                                                     |
| ----------------- | ---------------------------------------------------------------------------- |
| Agent Wizard      | 3-step setup: Identity → Knowledge → Behavior                                |
| Custom Persona    | Choose from presets or write custom system prompts                           |
| Embeddable Widget | Frontend-rendered chat UI at `/widget/[id]` (Next.js page)                   |
| Widget Backend    | Uses standard `/api/v1/judge` endpoint with CORS (no dedicated widget route) |

**Acceptance Criteria:**

- Agent wizard captures name, description, persona, and knowledge base
- Agents are stored as Sessions with persona and system_prompt fields
- Widget renders a standalone chat UI accessible at `/widget/{id}`
- Widget queries go through the standard `/api/v1/judge` endpoint

### F8: AWS Migration (Bedrock + FlashRank)

**User Story:** As a platform operator, I want to swap LLM/embedding providers without changing application code.

| Capability           | Behavior                                             |
| -------------------- | ---------------------------------------------------- |
| Provider Abstraction | Swap LLM/embedding/reranker via env var              |
| Bedrock LLM          | Claude 3.5 Sonnet via AWS Bedrock                    |
| Bedrock Embeddings   | Titan Embeddings v2 via AWS Bedrock                  |
| FlashRank Reranker   | Local Python reranker (zero-cost, no API dependency) |

**Acceptance Criteria:**

- Setting `LLM_PROVIDER=bedrock` routes all LLM calls through Bedrock
- Setting `RERANKER_PROVIDER=flashrank` uses local FlashRank model
- All providers implement the same Protocol interfaces
- Full RAG pipeline works end-to-end with any provider combination

---

## Quality Commitments

| Metric                           | Target |
| -------------------------------- | ------ |
| Answer accuracy (vs. golden set) | ≥ 90%  |
| Query latency (P50)              | < 1.5s |
| Hallucination rate               | < 5%   |
| Uptime                           | 99.5%  |

---

## Success Metrics (Product)

| Metric           | Definition                        | Target (Month 3) |
| ---------------- | --------------------------------- | ---------------- |
| WAU              | Weekly active users               | 500              |
| Queries/user     | Avg queries per session           | 5+               |
| Upload success   | PDFs indexed / PDFs uploaded      | > 95%            |
| PRO conversion   | Free → paid                       | 5%               |
| Thumbs up rate   | Positive feedback / total queries | > 80%            |
| Official catalog | Games with publisher rulesets     | 20+              |

---

## Roadmap

| Phase         | Status  | Key Deliverables                                                                                                                                                      |
| ------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Phase 1–3** | ✅ Done | Foundation, ingestion pipeline, adjudication engine                                                                                                                   |
| **Phase 4**   | ✅ Done | Frontend PWA (landing, auth, library, chat)                                                                                                                           |
| **Phase 5**   | ✅ Done | Publisher portal, official catalog, UI polish                                                                                                                         |
| **Phase 6**   | ✅ Done | Auth, billing, admin, rulings, parties, rate limiting                                                                                                                 |
| **Phase 7**   | ✅ Done | Agent builder wizard, embeddable widget                                                                                                                               |
| **Phase 8**   | ✅ Done | AWS Bedrock + FlashRank provider migration                                                                                                                            |
| **Phase 9**   | ✅ Done | Full Stripe checkout + portal, production JWT, library API, publisher API key auth                                                                                    |
| **Phase 10**  | ✅ Done | Hybrid Catalog (3-tier: Open/Metadata/Custom), pgvector migration (replaces Pinecone), BGG Hot 50 + Open5e SRD data ingest, catalog search, legal provenance tracking |
| **Phase 11**  | Planned | MCP integration, extended test coverage, input sanitization                                                                                                           |
