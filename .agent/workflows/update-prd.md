---
description: How to update the PRD (plan.md) and spec documents when making changes to Arbiter AI
---

# Update PRD & Spec Documents

Every feature addition, API change, schema modification, or architectural decision **must** be reflected in the project documentation before the implementation is considered complete.

## When This Workflow Applies

- Adding or modifying API endpoints
- Changing the database schema (new tables, columns, constraints)
- Adding new components or pages to the frontend
- Modifying the ingestion pipeline, adjudication engine, or any core flow
- Adding or changing environment variables
- Updating tier limits, billing logic, or security controls
- Any change that affects the repository structure

## Steps

### 1. Identify Affected Sections in `plan.md`

Before writing code, open `plan.md` and identify ALL sections that your change touches. The key sections are:

| Section                         | What Goes Here                   |
| ------------------------------- | -------------------------------- |
| §2.2 Component Responsibilities | New services, tech stack changes |
| §2.3 Data Schema                | Table/column/index changes       |
| §3.x Functional Specifications  | New features, flow changes       |
| §4.x API Interface              | New/modified endpoints           |
| §6 Observability                | New metrics, alerts, log fields  |
| §9 Repository Structure         | New files, directories           |
| §10 Implementation Checklist    | Task tracking                    |

### 2. Update the PRD BEFORE Implementing

// turbo

```bash
# Verify plan.md exists and get current line count
wc -l plan.md
```

- Open `plan.md` and make the documentation changes **first**
- For API changes: add the full endpoint spec (method, path, request/response JSON, error codes)
- For schema changes: add the SQL DDL to §2.3
- For new features: add a subsection under §3 with a mermaid flow diagram if applicable
- For new files: update the §9 repository structure tree

### 3. Update the Implementation Checklist

- Mark completed items with `[x]` in §10
- Add new sub-tasks for any new work discovered
- Keep phase groupings consistent

### 4. Cross-Reference Consistency Check

After updating, verify these cross-references are consistent:

- [ ] Every API endpoint in §4 has a corresponding route file in §9
- [ ] Every table in §2.3 has a migration listed in §10
- [ ] Every new feature in §3 has corresponding §4 endpoints
- [ ] Every new metric in §6 matches the feature it monitors
- [ ] Environment variables in §12 cover all new integrations
- [ ] The architecture diagram in §2.1 reflects any new components

### 5. Update Auxiliary Docs

If a `docs/openapi.yaml` or `docs/architecture.md` exists, update those too:

- `openapi.yaml`: Add/modify endpoint definitions, schemas, examples
- `architecture.md`: Update component diagrams, data flow descriptions
- `CLAUDE.md`: Update build commands or architecture notes if relevant

### 6. Commit Documentation With Code

Documentation changes **must** be in the same commit (or PR) as the code they describe. Never merge code without updated docs.

```
git add plan.md docs/ CLAUDE.md
git commit -m "docs: update PRD for [feature-name]"
```

## Anti-Patterns to Avoid

- ❌ Implementing a feature and "documenting it later"
- ❌ Adding an endpoint without updating §4 API Interface
- ❌ Changing schema without updating §2.3
- ❌ Adding files without updating §9 Repository Structure
- ❌ Leaving checklist items unmarked after completion
