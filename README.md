# FanoosAI - Dual Authentication System

Email + Password and SMS OTP authentication for FanoosAI platform.

## Features

- ✅ Email registration with verification
- ✅ Email + Password login (with OTP)
- ✅ SMS OTP login (passwordless via Melipayamak)
- ✅ JWT token generation
- ✅ Protected routes
- ✅ PostgreSQL database
- ✅ FastAPI Users standard implementation

## Installation

```bash
cd backend
uv sync
```

## Setup

1. Copy `templates/env.example` to `backend/.env` and fill credentials.
2. Create PostgreSQL database:
```sql
CREATE DATABASE fanoosai;
```
3. Run the server:

```bash
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Before the first start, apply the database migrations:

```bash
cd backend
uv run alembic upgrade head
```

## Automatic prompt execution

The API process only schedules jobs. Run the scheduler and one or more workers as separate processes:

```bash
cd backend
uv run python -m app.scheduler
uv run python -m app.worker
```

Each prompt/model pair is claimed once per Tehran calendar day in PostgreSQL, while Redis Streams provides delivery, retries, and distributed scheduler locking. Run retention periodically (for example, daily cron):

```bash
uv run python -m app.retention
```

Production health endpoints are `/health/live`, `/health/ready`, and Prometheus metrics are exposed at `/metrics`. Redis is mandatory outside `DEBUG=true`; it is used for OTP state, rate limits, locks, and the worker queue.

## Load test

The included read-only smoke test runs the requested concurrency scenarios:

```bash
python scripts/load_test.py --base-url http://127.0.0.1:8000 --duration 30 --users 100 1000 10000
```

## API Endpoints

### Standard FastAPI Users Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register new user |
| `/auth/jwt/login` | POST | Email + password login |
| `/users/` | GET | List users (admin) |
| `/users/{id}` | GET | Get user by ID |

### OTP Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/otp/email/request` | POST | Request email OTP |
| `/auth/otp/email/verify` | POST | Verify email OTP |
| `/auth/otp/sms/request` | POST | Request SMS OTP (via Melipayamak) |
| `/auth/otp/sms/verify` | POST | Verify SMS OTP |

## Authentication Flow

```
Email + Password Login:
1. POST /auth/jwt/login (email + password)
2. POST /auth/otp/email/request (email)
3. POST /auth/otp/email/verify (session_id + code)
4. Receive JWT token

SMS Login:
1. POST /auth/otp/sms/request (phone_number)
2. POST /auth/otp/sms/verify (session_id + code)
3. Receive JWT token
```

## Database Schema

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    phone_number VARCHAR,
    email_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE
);
```

## Environment Variables

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/fanoosai
JWT_SECRET_KEY=your-secret-key-here
SECRET_KEY=your-secret-key-here
JWT_LIFETIME_SECONDS=3600
MELIPAYAMAK_USERNAME=your_username
MELIPAYAMAK_PASSWORD=your_password
MELIPAYAMAK_FROM_NUMBER=09123456789
MELIPAYAMAK_SENDER=09123456789
```
