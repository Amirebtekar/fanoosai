# Scalability Redesign Checklist

- [ ] Queue + worker process
- [ ] Redis OTP/rate limiting/locks
- [ ] Alembic and database indexes
- [ ] `ai_runs` retention/partitioning
- [ ] Bounded analytics queries
- [ ] Shared HTTP client and pool configuration
- [ ] Structured logs, metrics, health, alerts
- [ ] HttpOnly cookies and CSP
- [ ] Load-test scenarios and baseline report

---

# Product Completion Tasks

## 1. Execution policy and test foundation

- [x] **Task 1: Configure frontend runtime and test harness**
  - Acceptance: API base URL is environment-driven; critical new UI flows have a runnable test command.
  - Verify: frontend lint/build and one focused test suite pass.
  - Dependencies: none.
  - Scope: M.

- [ ] **Task 2: Make daily execution claims source-aware and queryable**
  - Acceptance: one prompt/model has one Tehran-day claim across manual and scheduled sources; API can return queued/running/completed/unavailable state.
  - Verify: integration tests cover manual-first, scheduler-first, concurrent requests, and timezone boundary.
  - Dependencies: Task 1.
  - Scope: M.

- [ ] **Task 3: Add manual execution controls and run-log UI**
  - Acceptance: users can request only available models, see a clear refusal reason, and view paginated project runs.
  - Verify: API tests plus browser/manual flow against a seeded project.
  - Dependencies: Task 2.
  - Scope: M.

## 2. Project and brand intelligence

- [ ] **Task 4: Complete project settings contract and UI**
  - Acceptance: `website_url` round-trips; users can edit name/description/website and safely delete a project.
  - Verify: schema/API tests and create-edit-refresh browser flow.
  - Dependencies: Task 1.
  - Scope: M.

- [ ] **Task 5: Add owned-brand and competitor configuration**
  - Acceptance: a project has one or more owned domains/names and a managed competitor list; extracted brands can be matched or overridden.
  - Verify: migration and ownership/isolation integration tests.
  - Dependencies: Task 4.
  - Scope: M.

- [ ] **Task 6: Build project KPI dashboard**
  - Acceptance: dashboard shows visibility, average rank, appearances, competitor comparison, last successful run, and empty/error states.
  - Verify: aggregate-query tests and responsive RTL browser check.
  - Dependencies: Tasks 3 and 5.
  - Scope: M.

## 3. Alerts and analytics

- [ ] **Task 7: Deliver in-app alert rules and inbox**
  - Acceptance: users can configure rank-drop, disappearance, new-competitor, and run-failure alerts with cooldowns; alerts are readable and dismissible.
  - Verify: rule evaluation/unit tests and end-to-end alert creation/read flow.
  - Dependencies: Tasks 3, 5, and 6.
  - Scope: M.

- [ ] **Task 8: Complete ranking and brand drill-down analytics**
  - Acceptance: rankings support model/brand/date filters, sorting, pagination, and click-through brand history/comparison.
  - Verify: bounded-query tests and browser filters preserve URL state.
  - Dependencies: Tasks 5 and 6.
  - Scope: M.

- [ ] **Task 9: Export and securely share reports**
  - Acceptance: filtered analytics export to CSV; private expiring/revocable read-only links never expose raw responses.
  - Verify: authorization, expiry, revocation, and export-content tests.
  - Dependencies: Task 8.
  - Scope: M.

## 4. Authoring, operations, and collaboration

- [ ] **Task 10: Add immutable prompt revisions and comparison**
  - Acceptance: users clone a prompt to a new revision, see revision lineage, and compare outcomes without changing historical runs.
  - Verify: migration, immutability, and comparison-query tests.
  - Dependencies: Tasks 3 and 8.
  - Scope: M.

- [ ] **Task 11: Build AI-model administration**
  - Acceptance: authorized admins can sync, inspect, enable/disable models, and see recent execution health without affecting historical runs.
  - Verify: role-protected API tests and admin UI flow.
  - Dependencies: Task 3.
  - Scope: M.

- [ ] **Task 12: Add organizations, memberships, and roles**
  - Acceptance: projects belong to an organization; owner/admin/analyst/viewer permissions are enforced and existing user projects are backfilled safely.
  - Verify: migration-backfill and role matrix integration tests.
  - Dependencies: Tasks 4 and 9.
  - Scope: M.

## Checkpoints

- [ ] **After Tasks 1–3:** backend tests, frontend lint/build, and manual/scheduled quota scenario pass.
- [ ] **After Tasks 4–6:** project dashboard correctly reflects owned brand and competitor data.
- [ ] **After Tasks 7–9:** alert, drill-down, export, and sharing authorization checks pass.
- [ ] **After Tasks 10–12:** full regression suite, migration rehearsal, and RTL responsive browser pass.
