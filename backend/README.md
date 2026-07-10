# FanoosAI Backend

FastAPI backend for FanoosAI with email/password and SMS OTP authentication.

## Project Layout

```
backend/
|-- app/
|   |-- main.py
|   |-- core/
|   |-- database/
|   |-- users/
|   `-- auth/
|-- .env.example
|-- .python-version
|-- pyproject.toml
`-- uv.lock
```

## Requirements

- Python 3.11+
- PostgreSQL with the `asyncpg` driver
- A Melipayamak account for SMS OTP

## Install Dependencies

```bash
cd backend
uv sync
```

## Environment

1. Copy `.env.example` to `.env`.
2. Fill in the database, JWT, and SMS settings.

Example:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/fanoosai
JWT_SECRET_KEY=your-super-secret-jwt-key-change-me
SECRET_KEY=your-super-secret-jwt-key-change-me
MELIPAYAMAK_USERNAME=your-username
MELIPAYAMAK_PASSWORD=your-password
MELIPAYAMAK_FROM_NUMBER=+985000123456
MELIPAYAMAK_SENDER=+985000123456
```

3. Create the PostgreSQL database:

```bash
createdb fanoosai
```

## Run

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Authentication
- `POST /auth/register` - Register a new user
- `POST /auth/login` - Login with email and password
- `POST /auth/send-otp` - Send OTP to a mobile number
- `POST /auth/verify-otp` - Verify OTP code
- `GET /auth/jwt/login` - FastAPI Users JWT login route

### Users
- `GET /users/me` - Get the current user
- `PUT /users/me` - Update the current user

## Database Schema

The `users` table includes:
- `id` - primary key
- `email` - unique email address
- `phone` - unique mobile number
- `hashed_password` - hashed password
- `is_active` - active/inactive flag
- `is_verified` - verification flag
- `is_superuser` - admin flag

## Notes

- SQLAlchemy ORM is used with the `asyncpg` driver
- All requests are asynchronous
- JWT lifetime is controlled by `JWT_LIFETIME_SECONDS`
- OTP codes are 6 digits long

## More

- FastAPI Users docs: https://fastapi-users.github.io/fastapi-users/
- FastAPI docs: https://fastapi.tiangolo.com/
