---
description: The master quality gate — run before marking ANY feature as complete. Orchestrates all other workflows.
---

# Quality Gate (God Class)

// turbo-all

This is the **master checklist** that ties together all quality workflows. Run this before marking ANY feature, PR, or phase as complete. If any gate fails, the feature is **not done**.

## The 5 Gates

Every feature must pass ALL five gates before it ships:

```
┌─────────────────────────────────────────────────────┐
│                   QUALITY GATE                       │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │  Gate 1   │  │  Gate 2   │  │  Gate 3   │          │
│  │   PRD     │→│  Tests   │→│   A11y    │          │
│  │  Synced   │  │  Pass    │  │  Checked  │          │
│  └──────────┘  └──────────┘  └──────────┘           │
│        ↓                           ↓                 │
│  ┌──────────┐              ┌──────────┐              │
│  │  Gate 4   │              │  Gate 5   │             │
│  │   E2E     │              │  Build    │             │
│  │  Linked   │              │  Clean    │             │
│  └──────────┘              └──────────┘              │
│                                                      │
│  ALL 5 GATES PASS → Feature is DONE ✅               │
│  ANY GATE FAILS  → Feature is BLOCKED ❌             │
└─────────────────────────────────────────────────────┘
```

---

## Gate 1: Documentation Synced (`/update-prd`)

Reference: `.agent/workflows/update-prd.md`

- [ ] `plan.md` updated for any API, schema, feature, or structure change
- [ ] Implementation checklist (§10) reflects current state
- [ ] `docs/openapi.yaml` updated if endpoints changed
- [ ] `CLAUDE.md` updated if build commands or architecture evolved
- [ ] Cross-references in plan.md are consistent (endpoints ↔ routes ↔ schema ↔ repo tree)

---

## Gate 2: Tests Pass (`/testing`)

Reference: `.agent/workflows/testing.md`

- [ ] Unit tests written for every new/changed function
- [ ] Regression test added if fixing a bug
- [ ] All backend tests pass:

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

- [ ] All frontend tests pass:

```bash
cd frontend && npm test -- --watchAll=false
```

- [ ] Coverage thresholds met (core ≥ 90%, api ≥ 80%, components ≥ 70%)
- [ ] No skipped tests without a tracked issue

---

## Gate 3: Accessibility Verified (`/accessibility`)

Reference: `.agent/workflows/accessibility.md`

- [ ] Semantic HTML used (no `<div>` buttons)
- [ ] ARIA attributes applied per component checklist
- [ ] Keyboard navigation works for all interactive elements
- [ ] Color contrast ≥ 4.5:1 for all text
- [ ] No color-only indicators (confidence, errors, status all have text+icon)
- [ ] Focus management correct for modals and navigation
- [ ] `aria-live` regions on dynamic content (chat, upload progress)
- [ ] A11y lint passes:

```bash
cd frontend && npx eslint --ext .tsx src/ --rule '{"jsx-a11y/alt-text":"error","jsx-a11y/click-events-have-key-events":"error"}'
```

---

## Gate 4: End-to-End Linked (`/end-to-end`)

Reference: `.agent/workflows/end-to-end.md`

- [ ] Full stack path documented for the feature
- [ ] Frontend → API → Route → Service → Data Store chain verified
- [ ] TypeScript types match API response shapes
- [ ] Auth is enforced at every layer
- [ ] Error handling at every boundary (network, validation, service, DB)
- [ ] No orphaned code (dead endpoints, unused pages, unregistered routes)
- [ ] Environment variables declared in `.env.example`
- [ ] Smoke test passes for the affected flow

---

## Gate 5: Code Commenting (`/commenting`)

Reference: `.agent/workflows/commenting.md`

- [ ] Module docstrings present in every modified file
- [ ] Function docstrings (Args/Returns/Raises) present
- [ ] Inline comments explain WHY, not WHAT
- [ ] TODOs include name and date (`TODO(user, date): ...`)
- [ ] No stale comments
- [ ] API routes document auth/rate-limits

---

## Gate 6: Build Clean

- [ ] Backend builds without errors:

```bash
cd backend && python -m py_compile app/main.py && echo "Build OK"
```

- [ ] Frontend builds without errors:

```bash
cd frontend && npm run build
```

- [ ] No TypeScript errors
- [ ] No Python linting errors:

```bash
cd backend && ruff check app/
```

- [ ] No console warnings in browser during manual verification
- [ ] Git working tree is clean (no unstaged changes):

```bash
git status --short
```

---

## Quick Reference: Running All Gates

Execute this single command sequence to validate all automated gates:

```bash
# Gate 2 — Tests
echo "🧪 Gate 2: Running tests..."
cd backend && python -m pytest tests/ -v --tb=short && cd ..
cd frontend && npm test -- --watchAll=false && cd ..

# Gate 3 — A11y lint
echo "♿ Gate 3: A11y lint..."
cd frontend && npx eslint --ext .tsx src/ --rule '{"jsx-a11y/alt-text":"error"}' && cd ..

# Gate 5 — Build
echo "🏗️ Gate 5: Building..."
cd frontend && npm run build && cd ..
cd backend && ruff check app/ && cd ..

echo "✅ All automated gates passed"
```

Gates 1 and 4 require **manual review** — they cannot be fully automated.

---

## When to Run This

| Trigger                        | What to Run                            |
| ------------------------------ | -------------------------------------- |
| Before every commit            | Gates 2 + 5 (tests + build)            |
| Before every PR                | All 5 gates                            |
| After completing a phase (§10) | All 5 gates + checklist update         |
| After fixing a bug             | Gates 2 + 4 (tests + E2E verification) |
| After UI changes               | Gates 3 + 4 + 5 (a11y + E2E + build)   |

## The Definition of Done

A feature is **DONE** when:

1. ✅ Code is written and functional
2. ✅ Documentation is updated (Gate 1)
3. ✅ Tests pass with coverage thresholds (Gate 2)
4. ✅ Accessibility is verified (Gate 3)
5. ✅ Full stack is connected end-to-end (Gate 4)
6. ✅ Build is clean (Gate 5)
7. ✅ Changes are committed with a descriptive message
