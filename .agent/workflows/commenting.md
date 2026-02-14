---
description: How to write clear, maintainable code comments so other developers can understand what's happening
---

# Code Commenting Standards

Every file, class, function, and non-obvious code block must have clear comments. Code should be self-documenting where possible, but comments explain the **why** — not just the **what**.

## Rules

### 1. Every File Gets a Module Docstring

**Python (backend):**

```python
"""
ingestion.py — 3-layer ingestion pipeline for PDF rulebooks.

Handles quarantine → validation → virus scan → relevance classification →
layout parsing → chunking → embedding → Pinecone upsert → source purge.

Called by: Celery task in workers/tasks.py
Depends on: security.py, relevance.py, embedder.py
"""
```

**TypeScript (frontend):**

```tsx
/**
 * ChatInterface.tsx — Real-time chat UI for rules adjudication.
 *
 * Sends queries to POST /api/v1/judge, streams verdicts,
 * and renders citations with expandable cards.
 *
 * Used by: session/[id]/page.tsx
 */
```

### 2. Every Function/Method Gets a Docstring

**Python — use Google-style docstrings:**

```python
async def adjudicate(query: str, session_id: str) -> Verdict:
    """Generate a rules verdict for the given query.

    Performs hybrid search (dense + sparse), reranks with cross-encoder,
    applies hierarchy re-sort, detects conflicts, and generates a
    cited verdict via LLM.

    Args:
        query: The user's natural-language rules question (max 500 chars).
        session_id: UUID of the active game session.

    Returns:
        Verdict object with ruling, confidence, citations, and conflicts.

    Raises:
        SessionExpiredError: If the session has expired.
        InsufficientContextError: If no relevant chunks are found.
    """
```

**TypeScript — use JSDoc:**

```tsx
/**
 * Renders an expandable citation card showing source, page, and snippet.
 *
 * @param citation - The citation object from the verdict response.
 * @param isExpanded - Whether the card is currently expanded.
 * @param onToggle - Callback fired when the user expands/collapses.
 *
 * @example
 * <CitationCard citation={c} isExpanded={false} onToggle={() => {}} />
 */
```

### 3. Comment the WHY, Not the WHAT

```python
# ❌ BAD — restates the code
# Set source priority to 100
source_priority = 100

# ✅ GOOD — explains the reasoning
# Errata always overrides base and expansion rules (priority 100 > 10 > 0)
source_priority = 100
```

```python
# ❌ BAD
# Loop through chunks
for chunk in chunks:

# ✅ GOOD
# Merge undersized chunks (<200 tokens) with neighbors to avoid
# retrieval of context-free fragments that confuse the reranker
for chunk in chunks:
```

### 4. Mark TODOs, HACKs, and FIXMEs

Always include your name/date so the team knows context:

```python
# TODO(kasey, 2026-02-14): Replace with streaming response once
# FastAPI SSE support is stable. Currently buffering full verdict.

# HACK(kasey, 2026-02-14): Pinecone doesn't support hybrid search
# natively yet — we run two queries and fuse with RRF. Remove when
# Pinecone adds native hybrid search.

# FIXME(kasey, 2026-02-14): Race condition if two uploads for the
# same session fire simultaneously. Need optimistic locking.
```

### 5. Inline Comments for Non-Obvious Logic

```python
# Truncate snippet to 300 chars to stay within fair-use limits (§5.1)
snippet = chunk.text[:300]

# RRF fusion: 1/(k+rank) where k=60 is standard. Higher k = more
# weight to lower-ranked results, smoothing out sparse vs dense bias.
score = 1.0 / (60 + rank)

# Namespace fan-out: search official + personal namespaces, then merge.
# Official results get a slight boost (1.05x) since publishers verify accuracy.
```

### 6. Section Headers in Long Functions

For functions > 30 lines, use comment headers to break into logical blocks:

```python
async def ingest_pdf(file: UploadFile, session_id: str) -> RulesetMetadata:
    # --- Layer 1: Security & Validation ---
    validate_magic_bytes(file)
    check_blocklist(file_hash)
    await scan_with_clamav(file)

    # --- Layer 2: Relevance Classification ---
    first_pages = extract_first_pages(file, n=3)
    is_rulebook = await classify_rulebook(first_pages)
    if not is_rulebook:
        await purge_file(file)
        raise NotARulebookError()

    # --- Layer 3: Index & Purge ---
    chunks = parse_and_chunk(file)
    embeddings = await embed_chunks(chunks)
    await upsert_to_pinecone(embeddings, namespace=f"user_{user_id}")
    await purge_file(file)
```

### 7. API Route Comments

Every route must document the auth, rate limits, and tier restrictions:

```python
@router.post("/upload", status_code=202)
async def upload_rulebook(
    file: UploadFile,
    session_id: UUID,
    source_type: SourceType,
    user: User = Depends(get_current_user),
):
    """Upload a PDF rulebook for ingestion through the 3-layer pipeline.

    Auth: JWT required (user).
    Rate limit: None (upload is naturally throttled by file size).
    Tier limits:
        - FREE: max 2 rulesets per session, 25 MB max file size.
        - PRO: max 10 rulesets per session, 50 MB max file size.

    Returns 202 with job_id for async status polling via GET /rules/{id}/status.
    """
```

### 8. Keep Comments Updated

> **A wrong comment is worse than no comment.**

When you change code, **immediately update the comments above it.** Stale comments that describe old behavior actively mislead other developers.

```python
# ❌ STALE COMMENT — code was changed but comment wasn't
# Search top 20 results
results = await pinecone.query(top_k=50)  # Now searches 50!

# ✅ UPDATED
# Search top 50 candidates for cross-encoder reranking (increased from
# 20 after finding retrieval misses in eval — see issue #87)
results = await pinecone.query(top_k=50)
```

## Commenting Checklist

Before committing, verify:

- [ ] Every file has a module-level docstring
- [ ] Every public function/method has a docstring with Args/Returns/Raises
- [ ] Non-obvious logic has inline comments explaining WHY
- [ ] TODOs/HACKs/FIXMEs include name and date
- [ ] No stale comments that describe old behavior
- [ ] Long functions have section-header comments
- [ ] API routes document auth, rate limits, and tier restrictions

## Anti-Patterns

- ❌ No comments at all
- ❌ Comments that just restate the code (`# increment counter` above `counter += 1`)
- ❌ Stale comments that describe behavior the code no longer has
- ❌ TODOs with no name or date (untraceable)
- ❌ Commented-out code left in the file (delete it, git has history)
- ❌ Wall-of-text comments — keep each comment ≤ 3 lines where possible
