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