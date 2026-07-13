# ZenU FastAPI Backend (Python Port)

This project replicates the `ZenU-Backend` TypeScript + Express logic in Python using FastAPI and Supabase.

## What was ported

- Cookie-based Supabase auth (`sb-access-token`, `sb-refresh-token`)
- Auth endpoints:
  - `POST /api/auth/sign-up`
  - `POST /api/auth/sign-in`
  - `POST /api/auth/refresh`
  - `POST /api/auth/sign-out`
  - `POST /api/auth/forgot-password`
  - `POST /api/auth/reset-password`
  - `GET /api/auth/me`
  - `GET /api/me` alias
  - `POST /api/logout` alias
- Dashboard / module endpoints:
  - `/api/dashboard/*`, `/api/breathing/*`, `/api/meditations*`, `/api/journal*`
  - `/api/gratitude/*`, `/api/chat/*`, `/api/recommendations/today`
- Status endpoints: `/health`, `/warmup`, `/api/status`, `/api/status/smtp`

## Setup

1. Create and activate a virtual environment.
2. Install dependencies from `requirements.txt`.
3. Copy `.env.example` to `.env` and fill all Supabase values.
4. Run the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload
```

## Supabase migration

SQL files:

- `migrations/001_init_app_schema.sql`
- `migrations/002_app_rls_policies.sql`
- `migrations/003_password_reset_tokens.sql`

You can apply it with your Supabase migration tooling (or from VS Code Supabase integration).

## Render deployment notes

- Keep `SUPABASE_SERVICE_ROLE_KEY` server-side only (Render secrets).
- Set `FRONTEND_URL` to your frontend origin(s) to allow credentials.
- Keep `COOKIE_SECURE=true` in HTTPS production.
- Render free/sleeping instances may take ~45 seconds to wake, so the frontend should retry and/or warm with `/warmup`.
- Pin Python to `3.12.x` on Render (`PYTHON_VERSION=3.12.9`) to avoid `pydantic-core` source builds requiring Rust.
- Build command: `pip install --upgrade pip && pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- A ready-to-use Render Blueprint is included at `render.yaml`.

## SMTP setup (forgot password)

Set these env vars in `.env` (and in Render secrets):

- `SMTP_HOST`
- `SMTP_PORT` (default `587`)
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME` (default `ZenU`)
- `SMTP_USE_TLS` (`true`/`false`)
- `RESET_PASSWORD_URL_BASE` (optional; defaults to `FRONTEND_URL`)

You can verify SMTP connection at `GET /api/status/smtp`.

## Compatibility notes

- Response shape for authenticated user is kept as `{ "user": mapUser(...) }` for frontend compatibility.
- Forgot/reset password is implemented via SMTP reset links and a one-time token table (`app.password_reset_tokens`).
