# Arbiter AI — Product Requirements Document (PRD)

**Version:** 1.0 · **Status:** Active · **Last Updated:** 2026-02-14

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

### F1: Game Library (Dashboard)

**User Story:** As a gamer, I want to save the games I play so I can quickly ask rules questions without re-uploading files every time.

| Capability                    | FREE     | PRO       |
| ----------------------------- | -------- | --------- |
| Browse official catalog       | ✅       | ✅        |
| Add official games to library | Up to 5  | Unlimited |
| Upload personal PDFs          | 1 active | 10 active |
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
| Drag-and-drop upload | PDF files, ≤ 50 MB                               |
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

### F5: Accounts & Billing

**User Story:** As a power user, I want to upgrade to PRO to get longer sessions, more uploads, and faster query rates.

| Feature            | FREE           | PRO ($9.99/mo) |
| ------------------ | -------------- | -------------- |
| Sessions           | 24-hour expiry | 30-day expiry  |
| Active rulesets    | 2              | 10             |
| Max file size      | 25 MB          | 50 MB          |
| Queries/min        | 10             | 60             |
| Game library slots | 5              | Unlimited      |

**Acceptance Criteria:**

- Stripe-powered checkout and self-service portal
- Downgrade preserves library but enforces limits
- Grace period on payment failure before downgrade

### F6: PWA Install

**User Story:** As a mobile user, I want to install Arbiter on my home screen for instant access during game night.

**Acceptance Criteria:**

- Install prompt appears on supported browsers
- Offline fallback page displays when disconnected
- App appears in device app drawer with custom icon

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

| Phase    | Target   | Key Deliverables                                  |
| -------- | -------- | ------------------------------------------------- |
| **MVP**  | Week 6   | Upload, query, cite, library, billing, PWA        |
| **v1.1** | Week 8   | Publisher portal, official catalog, feedback loop |
| **v2**   | Month 4  | MCP integration, multi-modal, voice query         |
| **v3**   | Month 6+ | Community features, house rules, game sharing     |
