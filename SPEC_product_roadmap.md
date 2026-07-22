# Spec: FanoosAI Product Completion Roadmap

## Objective

Complete FanoosAI as a Persian, RTL product for monitoring a brand's visibility in AI answers. The work covers the ten product gaps identified in the product review: brand/competitor tracking, execution control, alerts, project dashboard, run history, project management, AI-model administration, richer analytics, prompt versioning, and teams/roles.

### Execution policy (approved)

- A prompt/model pair may execute at most once per Tehran calendar day.
- Manual and scheduled executions consume the same daily quota.
- If the scheduled execution has claimed or completed the pair today, a manual request is rejected; the inverse is also true.
- The UI must explain whether a model is unavailable because it is queued, running, or already executed today.
- The database is the final atomic authority for the quota; Redis may optimize queue delivery but must not decide correctness.

## Technical approach

- Backend: FastAPI, SQLAlchemy async, PostgreSQL, Redis Streams workers.
- Frontend: React, TanStack Router, TypeScript, RTL Persian UI.
- Use Alembic migrations for every schema change.
- Add endpoint contracts before connecting UI; deliver each capability as a vertical slice with unit/integration tests.

## Success criteria

1. A user can designate its own brand and competitors per project and compare their visibility over time.
2. Manual execution follows the approved quota rule under concurrent requests and clearly reports availability.
3. Users can see project KPIs, execution history, alerts, and actionable brand changes.
4. Project settings, prompt revisions, model administration, reports, sharing, and team permissions work without bypassing ownership checks.
5. All modified backend paths have automated tests; the frontend builds and has focused component/integration coverage for the new critical flows.

## Boundaries

- Always: preserve project ownership checks, validate inputs at API boundaries, use Tehran timezone for quota/date display, and add migrations and tests with each data-model change.
- Ask first: adding paid third-party notification/reporting providers, changing retention policy, enabling billing, or changing existing production data semantics.
- Never: make Redis the only execution guard, expose raw model responses in public links, or store secrets in the repository.

## Non-goals for this roadmap

- Native mobile applications.
- Automatic prompt rewriting/generation.
- Billing and subscriptions; usage data can be prepared but billing needs a separate product decision.
