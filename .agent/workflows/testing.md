---
description: How to ensure unit testing and regression testing is in place for every change
---

# Unit Testing & Regression Testing

Every code change to Arbiter AI **must** have corresponding tests. No PR is mergeable without test coverage for the changed code paths.

## Testing Structure

```
backend/tests/
├── unit/                    # Fast, isolated, no external deps
│   ├── test_ingestion.py    # Chunking, parsing, hash validation
│   ├── test_relevance.py    # Rulebook classifier mock tests
│   ├── test_judge.py        # Verdict generation logic
│   ├── test_retriever.py    # Search, RRF fusion, namespace routing
│   ├── test_reranker.py     # Hierarchy re-sort, conflict detection
│   ├── test_security.py     # File validation, blocklist, sanitization
│   ├── test_billing.py      # Stripe webhook handlers, tier transitions
│   ├── test_sessions.py     # Session lifecycle, expiry
│   ├── test_library.py      # Library CRUD, favorites
│   └── test_publisher.py    # Publisher API auth, ruleset management
├── integration/             # Requires running services (DB, Redis, Pinecone)
│   ├── test_ingestion_e2e.py
│   ├── test_judge_e2e.py
│   └── test_billing_e2e.py
└── fixtures/
    ├── sample_rulebook.pdf    # Valid multi-column rulebook
    ├── table_heavy.pdf        # Rulebook with complex tables
    ├── not_a_rulebook.pdf     # Should be rejected by Layer 2
    └── mock_responses/        # Frozen LLM/API responses for deterministic tests
```

```
frontend/
├── __tests__/               # Or colocated .test.tsx files
│   ├── components/
│   │   ├── ChatInterface.test.tsx
│   │   ├── CitationCard.test.tsx
│   │   ├── FileUpload.test.tsx
│   │   ├── GameCard.test.tsx
│   │   └── ConfidenceBadge.test.tsx
│   ├── pages/
│   │   ├── library.test.tsx
│   │   ├── catalog.test.tsx
│   │   └── session.test.tsx
│   └── lib/
│       ├── api.test.ts
│       └── auth.test.ts
```

## Steps for Every Code Change

### 1. Write Tests FIRST (or Alongside)

For every function, endpoint, or component you create or modify:

- **Backend (Python):** Write `pytest` tests using fixtures and mocks
- **Frontend (TypeScript):** Write tests using Jest + React Testing Library
- Mock all external services (LLM, Pinecone, Stripe, ClamAV, S3)

### 2. Required Test Categories

| Category        | What to Test                                      | Tools                             |
| --------------- | ------------------------------------------------- | --------------------------------- |
| **Unit**        | Individual functions in isolation                 | `pytest`, mocks                   |
| **API**         | Endpoint request/response, auth, validation       | `httpx.AsyncClient`, `TestClient` |
| **Integration** | Multi-service flows with real deps                | `pytest`, docker fixtures         |
| **Regression**  | Previously-broken scenarios that must never recur | Dedicated `test_regressions.py`   |
| **Component**   | React component rendering, interaction            | Jest, RTL                         |

### 3. Regression Test Protocol

When fixing a bug:

1. **Write a failing test that reproduces the bug FIRST**
2. Fix the bug
3. Verify the test passes
4. Add the test to `test_regressions.py` (backend) or a `__tests__/regressions/` folder (frontend) with a comment:

```python
def test_regression_issue_42_duplicate_hash_crash():
    """
    Regression: duplicate file hash caused 500 instead of 409.
    Fixed: 2025-02-15
    Root cause: missing unique constraint check before insert.
    """
    ...
```

### 4. Run the Full Suite Before Every Commit

// turbo

```bash
# Backend tests
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -50
```

// turbo

```bash
# Frontend tests
cd frontend && npm test -- --watchAll=false 2>&1 | tail -50
```

### 5. Coverage Thresholds

| Layer               | Target                | Enforcement                                 |
| ------------------- | --------------------- | ------------------------------------------- |
| Backend core/       | ≥ 90% line coverage   | `pytest --cov=app.core --cov-fail-under=90` |
| Backend api/        | ≥ 80% line coverage   | `pytest --cov=app.api --cov-fail-under=80`  |
| Frontend components | ≥ 70% branch coverage | Jest `--coverage --coverageThreshold`       |

### 6. Critical Test Scenarios (Must Always Exist)

These scenarios must **always** have tests. If a test is missing, add it:

**Ingestion Pipeline:**

- [ ] Valid PDF → INDEXED status
- [ ] Non-rulebook PDF → rejected by Layer 2
- [ ] Oversized PDF → 422 error
- [ ] Blocklisted hash → rejected
- [ ] Malformed PDF → FAILED status
- [ ] Duplicate upload → handled gracefully

**Adjudication Engine:**

- [ ] Simple query → verdict with citations
- [ ] Low-confidence → uncertainty disclaimer returned
- [ ] Conflicting rules → both interpretations shown
- [ ] Empty context → "insufficient context" response
- [ ] Query > 500 chars → rejected

**Auth & Billing:**

- [ ] Unauthenticated request → 401
- [ ] FREE tier at rate limit → 429
- [ ] Stripe webhook `checkout.session.completed` → tier upgraded
- [ ] Stripe webhook `customer.subscription.deleted` → tier reverted

**Session Management:**

- [ ] Expired session → 410 Gone
- [ ] Session data isolation → user A cannot see user B's data

## Anti-Patterns to Avoid

- ❌ Writing code without any tests
- ❌ Testing only the happy path
- ❌ Fixing a bug without a regression test
- ❌ Mocking so aggressively that the test verifies nothing
- ❌ Skipping tests with `@pytest.mark.skip` without a tracked issue
- ❌ Tests that depend on execution order
