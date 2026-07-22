# Project Creation Plan (Detailed Tasks)

## Phase 1: Database & Models

### Task 1: Create Project Model
- **Title:** Add SQLAlchemy model for Project
- **Acceptance Criteria:**
  - Model includes `id`, `name`, `description`, `created_at`, `updated_at`, `user_id`
  - Relationship to `UserTable` via `user_id`
  - Table name: `projects`
- **Verification:**
  - Model imports successfully in `database/models.py`
  - `Base.metadata.create_all()` creates the table
- **Dependencies:** None

### Task 2: Update User Model
- **Title:** Add back-populates to User model for projects
- **Acceptance Criteria:**
  - `UserTable` has `projects` relationship to `Project` model
  - Proper `back_populates` setup
- **Verification:**
  - Relationship works in SQLAlchemy queries
- **Dependencies:** Task 1

---

## Phase 2: Repository Layer

### Task 3: Create Project Repository
- **Title:** Add ProjectRepository class
- **Acceptance Criteria:**
  - Methods: `create`, `get_by_id`, `list_by_user`, `update`, `delete`
  - Uses `AsyncSession` for DB operations
  - Returns `Project` model instances
- **Verification:**
  - Unit tests pass for all methods
  - Methods handle edge cases (e.g., not found)
- **Dependencies:** Task 1

---

## Phase 3: Service Layer

### Task 4: Create Project Service
- **Title:** Add ProjectService class
- **Acceptance Criteria:**
  - Methods: `create_project`, `list_user_projects`, `get_project`, `update_project`, `delete_project`
  - **Guard:** Only allows verified users to create projects
  - Uses `ProjectRepository` for DB operations
  - Handles business logic (e.g., validation)
- **Verification:**
  - Unit tests pass for all methods
  - Unverified users cannot create projects
- **Dependencies:** Task 3

---

## Phase 4: API Layer

### Task 5: Create Project Router
- **Title:** Add FastAPI router for projects
- **Acceptance Criteria:**
  - Endpoints:
    - `POST /projects` (create project)
    - `GET /projects` (list user projects)
    - `GET /projects/{id}` (get project)
    - `PUT /projects/{id}` (update project)
    - `DELETE /projects/{id}` (delete project)
  - Uses `ProjectService` for business logic
  - Proper request/response models (Pydantic)
  - Error handling (e.g., 403 for unverified users)
- **Verification:**
  - Integration tests pass for all endpoints
  - Swagger docs show correct endpoints
- **Dependencies:** Task 4

### Task 6: Add Router to Main App
- **Title:** Include project router in FastAPI app
- **Acceptance Criteria:**
  - Router is mounted under `/projects` prefix
  - Tags: `projects`
- **Verification:**
  - Endpoints are accessible in Swagger
  - No conflicts with existing routes
- **Dependencies:** Task 5

---

## Phase 5: Testing

### Task 7: Write Unit Tests for ProjectRepository
- **Title:** Add unit tests for ProjectRepository
- **Acceptance Criteria:**
  - Tests for `create`, `get_by_id`, `list_by_user`, `update`, `delete`
  - Uses `pytest` and `AsyncSession`
  - Covers edge cases (e.g., not found)
- **Verification:**
  - All tests pass
  - Coverage > 90%
- **Dependencies:** Task 3

### Task 8: Write Unit Tests for ProjectService
- **Title:** Add unit tests for ProjectService
- **Acceptance Criteria:**
  - Tests for `create_project`, `list_user_projects`, `get_project`, `update_project`, `delete_project`
  - Tests for verified user guard
  - Uses `pytest-mock` for mocking
- **Verification:**
  - All tests pass
  - Coverage > 90%
- **Dependencies:** Task 4

### Task 9: Write Integration Tests for Project Endpoints
- **Title:** Add integration tests for project endpoints
- **Acceptance Criteria:**
  - Tests for all endpoints (`POST /projects`, `GET /projects`, etc.)
  - Tests for unverified user guard
  - Uses `TestClient` and `AsyncSession`
- **Verification:**
  - All tests pass
  - Coverage > 90%
- **Dependencies:** Task 6

---

## Phase 6: Security & Validation

### Task 10: Add Input Validation
- **Title:** Validate project input data
- **Acceptance Criteria:**
  - Pydantic models for `ProjectCreate`, `ProjectUpdate`, `ProjectRead`
  - Validation for `name` (length, required)
  - Validation for `description` (optional)
- **Verification:**
  - Invalid input returns 422
  - Valid input passes
- **Dependencies:** Task 5

### Task 11: Add Verified User Guard
- **Title:** Enforce verified user check in service layer
- **Acceptance Criteria:**
  - `create_project` method checks `user.is_verified`
  - Unverified users get 403 error
- **Verification:**
  - Integration tests pass for unverified users
- **Dependencies:** Task 4

---

## Phase 7: Documentation

### Task 12: Update API Documentation
- **Title:** Add Swagger docs for project endpoints
- **Acceptance Criteria:**
  - All endpoints documented with examples
  - Error cases documented (e.g., 403 for unverified users)
- **Verification:**
  - Swagger docs are clear and complete
- **Dependencies:** Task 6

---

## Phase 8: Build & Deployment

### Task 13: Run Migrations
- **Title:** Generate and run Alembic migration for Project model
- **Acceptance Criteria:**
  - Migration file is generated
  - Migration runs successfully
- **Verification:**
  - `projects` table exists in DB
- **Dependencies:** Task 1

### Task 14: Update Deployment Scripts
- **Title:** Add project-related steps to deployment scripts
- **Acceptance Criteria:**
  - Deployment scripts include DB migrations
  - No manual steps required
- **Verification:**
  - Deployment runs without errors
- **Dependencies:** Task 13
# Scalability Redesign Plan

## Overview

Replace the in-process daily runner with a Redis-backed queue and separate worker, make database access migration- and index-driven, bound analytics queries, move distributed state to Redis, and add security/operational telemetry. The existing MVP remains the rollback point.

## Architecture Decisions

- Use Redis Lists for the first queue slice to avoid introducing a second job framework; workers use blocking pop and reclaimable job state.
- Keep the database unique daily claim as the final correctness guard. Redis locks reduce duplicate enqueue work but are not the source of truth.
- Run the web API, scheduler, and worker as separate processes.
- Use Alembic for schema changes; application startup will no longer perform data cleanup or schema creation.
- Keep metrics labels bounded to route/status/provider and never include user IDs or prompt text.

## Task List

### Phase 1: Queue and distributed state

- [ ] Add Redis configuration and a shared async Redis client.
- [ ] Add queue payloads, scheduler process, worker process, and worker-safe single-model execution.
- [ ] Move OTP, send throttling, verify-attempt counters, and daily enqueue locks to Redis.
- [ ] Remove the automatic task from the web lifespan and document process commands.

### Phase 2: Database and analytics

- [ ] Enable Alembic metadata and add migrations for daily claims, indexes, and run storage strategy.
- [ ] Add indexes for ownership, prompt/model lookups, and time-ordered runs.
- [ ] Add a bounded retention/archival policy and PostgreSQL partitioning migration for `ai_runs`.
- [ ] Replace analytics N+1 and in-memory unbounded queries with grouped SQL and bounded pagination.

### Phase 3: Network and operations

- [ ] Add shared HTTP client lifecycle, bounded timeouts, retry/backoff, and provider metrics.
- [ ] Add JSON request logging with request IDs, RED metrics, queue metrics, and health endpoints.
- [ ] Add Prometheus alert rules and a short runbook.
- [ ] Replace browser token storage with HttpOnly cookie-only auth and add CSP.

### Phase 4: Verification

- [ ] Add unit/integration tests for queue idempotency, Redis state, migration indexes, auth cookies, and analytics query bounds.
- [ ] Add load-test scenarios for 100, 1,000, and 10,000 virtual users with documented thresholds.
- [ ] Run the tests and load tests against a representative PostgreSQL/Redis environment.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Redis outage | Jobs/auth throttles unavailable | Explicit health checks, retryable queue, production startup validation, and clear degraded mode for local development |
| Worker crash after external call | Duplicate or lost work | Database daily claim, job status/reclaim policy, and idempotent persistence |
| Existing large `ai_runs` table | Migration downtime | Expand/contract migration and partitioning runbook; measure table size first |
| Analytics query rewrite changes results | Incorrect dashboard | Preserve response contracts and add fixture-based query tests |

## Open Questions

- Production PostgreSQL version and whether native partitioning is available.
- Production Redis deployment (single instance, Sentinel, or managed Redis).
- Target SLOs for API p95 latency and daily-run completion time.

---

# Implementation Plan: Product Completion Roadmap

## Overview

Deliver the ten missing FanoosAI capabilities in dependency order. The first phase strengthens execution correctness and project foundations; later phases add the analytical and collaboration layers. Each phase remains deployable on its own.

## Architecture decisions

- Extend the existing `daily_prompt_runs` unique claim rather than adding a second manual-quota system. A new claim state/source field records whether it was manual or scheduled and lets the UI explain the result.
- Treat brand ownership as project-scoped configuration; retain the global extracted-brand catalog to avoid duplicate entities.
- Use in-app alerts first. Email, Telegram, Slack, and webhooks are adapters added only after their delivery and retry contract is defined.
- Version prompts by creating immutable revisions; runs retain the revision text used at execution time.
- Introduce organizations/memberships before sharing projects. The existing user-owned project remains a single-owner organization during migration.

## Dependency map

```text
Execution claim/status ──> Manual-run UI + project run history ──> alerts
Project brand configuration ──> comparison analytics ──> reports/share links
Project settings + dashboard ──> project overview
Prompt revisions ──> version-aware analytics
Organization/membership ──> roles ──> secure sharing
Admin model management ──> model selection and execution health
```

## Phases

### Phase 0 — foundation and execution control

1. Establish frontend test tooling, runtime API configuration, and API error conventions.
2. Complete the daily execution-claim contract and expose execution availability/status.
3. Deliver manual-run controls and a project-level execution log.

Checkpoint: concurrent manual/scheduled attempts cannot exceed one execution per prompt/model/day.

### Phase 1 — project and brand intelligence

4. Finish project read/update settings, including website URL and safe deletion confirmation.
5. Add project-scoped owned-brand and competitor configuration.
6. Deliver a data-backed project dashboard with core visibility KPIs.

Checkpoint: a user can identify its brand, competitors, current visibility, and recent changes from one project page.

### Phase 2 — alerts and actionable analytics

7. Add alert rules, in-app alert inbox, and read state.
8. Complete analytics tables: ranking filters, brand drill-down, comparison, and pagination.
9. Add CSV export, scheduled report-ready snapshots, and private read-only sharing links.

Checkpoint: users can find a material rank/visibility change, inspect it, and export/share the result.

### Phase 3 — authoring, administration, collaboration

10. Add immutable prompt revisions and clone/compare flows.
11. Add AI-model administration and execution-health visibility.
12. Add organizations, memberships, roles, and project authorization migration.

Checkpoint: team users can safely collaborate and administrators can operate models without direct database access.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Daily-claim migration changes scheduler behavior | High | Add source/status fields in an expand/contract migration; test manual-first and scheduler-first cases. |
| Brand normalization merges separate brands | High | Keep raw extracted name, allow user overrides, and never silently merge user-configured competitors. |
| Alerts become noisy | Medium | Start with explicit rules and cooldowns; show a preview before enabling a rule. |
| Public sharing leaks raw model content | High | Scope links to aggregate analytics by default; use expiry, revocation, and no raw response field. |
| Organization migration breaks ownership | High | Backfill a personal organization per existing user and retain current ownership checks during transition. |

## Open decisions deferred to their phase

- Supported outbound alert channels and their providers.
- Default report cadence and retention of exported files.
- Final organization role matrix and whether external guests may be invited.
