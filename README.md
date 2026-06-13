# Invoicio

A lightweight multi-tenant invoice management SaaS. Businesses can create customers, issue branded invoices, generate PDFs, and track payment status.

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
  - [Multi-tenancy](#multi-tenancy)
  - [Authentication Flow](#authentication-flow)
  - [Tenant Isolation Strategy](#tenant-isolation-strategy)
  - [Role System](#role-system)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [Docker Setup](#docker-setup)
- [Environment Variables](#environment-variables)
- [Database and Migrations](#database-and-migrations)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Development Workflow](#development-workflow)
  - [Branch Strategy](#branch-strategy)
  - [Commit Convention](#commit-convention)
  - [Pre-commit Hooks](#pre-commit-hooks)
- [CI/CD](#cicd)
- [Contributing](#contributing)

## Features

**Authentication**
- Register a business and owner account in one step
- JWT access tokens (30 min) and refresh tokens (7 days)
- Role-based route protection

**Business Profile**
- Configure company info, country, and currency
- Upload a branded logo (JPEG, PNG, WebP, SVG, max 5 MB)
- Store bank and payment details for invoice footers

**Staff Management**
- Invite staff with assigned roles (`owner`, `admin`, `staff`)
- Owner role is immutable and cannot be reassigned via API

**Customers**
- Full CRUD with paginated search
- Email uniqueness enforced per tenant

**Invoices**
- Create invoices with line items, tax rate, and discounts (flat or percentage)
- All totals calculated server-side using `Decimal`
- Status machine: `draft` to `sent` to `paid` or `overdue`
- Only draft invoices can be edited or deleted
- Auto-incrementing invoice numbers per tenant (`INV-0001`, `INV-0002`)

**PDF Generation**
- Branded PDF with logo, line items, totals, and payment details
- Generated on-demand via WeasyPrint, streamed as a download

**Dashboard**
- Invoice counts and totals grouped by status

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Database (dev) | SQLite |
| Database (prod) | PostgreSQL via `psycopg[binary]` |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Authentication | JWT via `python-jose` |
| Password hashing | `passlib[bcrypt]` |
| PDF generation | WeasyPrint + Jinja2 |
| Package manager | `uv` |
| Linter and formatter | Ruff |
| Type checker | mypy |
| Testing | pytest + pytest-cov |
| Frontend framework | React 18 + Vite |
| Styling | TailwindCSS |
| State management | Zustand |
| HTTP client | Axios |
| Containerisation | Docker + docker-compose |
| CI/CD | GitHub Actions |

## Project Structure

```
invoxa/
├── .github/
│   └── workflows/
│       └── ci.yml
├── backend/
│   ├── alembic/
│   │   ├── versions/
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── app/
│   │   ├── auth/
│   │   │   └── __init__.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── exceptions.py
│   │   │   └── security.py
│   │   ├── customers/
│   │   │   └── __init__.py
│   │   ├── invoices/
│   │   │   └── __init__.py
│   │   ├── shared/
│   │   │   └── __init__.py
│   │   ├── tenants/
│   │   │   └── __init__.py
│   │   └── users/
│   │       └── __init__.py
│   ├── main.py
│   ├── tests/
│   │   ├── auth/
│   │   │   └── test_auth.py
│   │   ├── invoices/
│   │   │   └── test_invoices.py
│   │   ├── tenants/
│   │   │   └── test_isolation.py
│   │   └── conftest.py
│   ├── .env.example
│   ├── alembic.ini
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layouts/
│   │   │   └── ui/
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── customers/
│   │   │   ├── dashboard/
│   │   │   ├── invoices/
│   │   │   └── settings/
│   │   ├── hooks/
│   │   ├── services/
│   │   │   └── api.js
│   │   └── store/
│   │       ├── authStore.js
│   │       └── tenantStore.js
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.js
├── .gitignore
├── .pre-commit-config.yaml
├── docker-compose.yml
└── README.md
```

## Architecture

### Multi-tenancy

Invoicio uses shared-database multi-tenancy. All tenants share a single database and schema. Every tenant-sensitive table carries a `tenant_id` foreign key that references the `tenants` table.

This approach was chosen over schema-per-tenant because it is simpler to operate at this scale with no per-tenant migration management, works well with a single Postgres instance, allows straightforward cross-tenant reporting if ever needed, and avoids subdomain routing complexity.

The tradeoff is that every query must include a `tenant_id` filter. This is enforced in the service layer on every read and write operation.

### Authentication Flow

```
POST /api/v1/auth/register
  creates Tenant + owner User in one transaction
  returns access_token (30 min) + refresh_token (7 days)

POST /api/v1/auth/login
  verifies email + bcrypt password
  returns access_token + refresh_token

POST /api/v1/auth/refresh
  validates refresh_token
  returns new access_token

POST /api/v1/auth/logout
  stateless: client discards tokens
```

Access tokens carry three claims beyond the standard JWT fields:

```json
{
  "sub": "<user_uuid>",
  "tenant_id": "<tenant_uuid>",
  "role": "owner | admin | staff"
}
```

### Tenant Isolation Strategy

The `tenant_id` in every access token is set at login time and comes from the database record. The frontend never supplies it. Every protected endpoint extracts a `CurrentUser` dataclass from the token via the `get_current_user` dependency:

```python
@dataclass(frozen=True)
class CurrentUser:
    user_id: UUID
    tenant_id: UUID
    role: str
```

Every service function that touches tenant data accepts `tenant_id` as a parameter and includes it in every query predicate. A request from Tenant A for a resource belonging to Tenant B returns `404` rather than `403` to avoid leaking the existence of the resource.

### Role System

| Role | Permissions |
|---|---|
| `owner` | Full access. Created automatically on registration. Cannot be reassigned. |
| `admin` | Manage staff, customers, invoices, and business profile. |
| `staff` | Create and edit customers and invoices. Cannot manage users or delete records. |

Role guards are implemented as FastAPI dependency factories in `shared/dependencies.py`:

```python
require_owner            # owner only
require_admin_or_above   # owner + admin
require_any_staff        # owner + admin + staff
```

## Getting Started

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11+ | [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 20+ | [nodejs.org](https://nodejs.org) |
| Docker + Compose | latest | [docker.com](https://docker.com) |

### Backend Setup

```bash
git clone https://github.com/Kenward-dev/invoxa.git
cd invoxa/backend

cp .env.example .env

uv sync

uv run alembic upgrade head

uv run uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/api/docs`

### Frontend Setup

```bash
cd invoicio/frontend

npm install

npm run dev
```

The frontend will be available at `http://localhost:5173`. The Vite dev server proxies `/api` and `/uploads` requests to `http://localhost:8000`.

### Docker Setup

```bash
cp backend/.env.example backend/.env

docker-compose up --build
```

Docker Compose loads `backend/.env` for the backend service. By default, the
backend container connects to the Postgres service with:

```env
postgresql+psycopg://invoicio:change-me@db:5432/invoicio
```

If you change the Postgres credentials, set `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_DB`, and `DOCKER_DATABASE_URL` in your shell or a root `.env` file
before running Compose.

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/api/docs |
| PostgreSQL | localhost:5432 |

To run only the database and develop the backend natively:

```bash
docker-compose up db
```

## Environment Variables

Copy `backend/.env.example` to `backend/.env` to get started.

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `Invoicio` | Application name shown in API docs |
| `APP_VERSION` | `0.1.0` | Semver version string |
| `DEBUG` | `false` | Enables SQLAlchemy query logging |
| `ENVIRONMENT` | `development` | `development`, `production`, or `test` |
| `SECRET_KEY` | insecure default | Generate with `openssl rand -hex 32` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `DATABASE_URL` | SQLite local file | Full SQLAlchemy connection string |
| `UPLOADS_DIR` | `uploads` | Directory for logo file storage |
| `MAX_UPLOAD_SIZE_MB` | `5` | Maximum logo file size |
| `ALLOWED_ORIGINS` | `["http://localhost:5173"]` | CORS allowed origins as a JSON array |

Minimum changes required for production:

```env
ENVIRONMENT=production
SECRET_KEY=<output of openssl rand -hex 32>
DATABASE_URL=postgresql+psycopg://user:password@host:5432/invoicio
ALLOWED_ORIGINS=["https://yourdomain.com"]
```

## Database and Migrations

```bash
uv run alembic upgrade head

uv run alembic downgrade -1

uv run alembic revision --autogenerate -m "add payment_reference to invoices"

uv run alembic history

uv run alembic current
```

In development, `main` runs `Base.metadata.create_all` on startup as a convenience. For production, always use `alembic upgrade head`. Never rely on `create_all` to manage schema changes.

The `DATABASE_URL` drives the engine. Use `sqlite:///./invoicio_dev.db` locally and `postgresql+psycopg://...` in production. No code changes are required between environments.

## API Documentation

When the backend is running, documentation is available at:

- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- OpenAPI JSON: `http://localhost:8000/api/openapi.json`

### Endpoint Summary

```
Health
  GET    /api/health
```

Feature routers are intentionally not mounted in this sprint. Protected API
endpoints will be documented here as they are added.

## Testing

```bash
cd backend

uv run pytest

uv run pytest --cov=app --cov-report=term-missing

uv run pytest tests/auth/test_auth.py

uv run pytest tests/auth/test_auth.py::test_register_creates_tenant_and_owner -v
```

Tests use a SQLite database created fresh per session. Each test gets a rolled-back session, so tests are fully isolated without truncating tables.

| Area | What is tested |
|---|---|
| Auth | Register, duplicate email, login, wrong password, protected route, token refresh |
| Tenant isolation | Cross-tenant customer visibility, cross-tenant invoice access |
| Invoice logic | Total calculation, percentage discount, immutability of sent invoices |

## Development Workflow

### Branch Strategy

```
main          production-ready, protected
dev           integration branch, PRs merge here first
feat/INV-N-*  feature branches cut from dev
fix/INV-N-*   bug fix branches
chore/*       tooling, config, docs
```

Branch naming follows the pattern `type/short-description`, for example `feat/invoice-pdf` or `fix/token-refresh-bug`.

Never push directly to `main` or `dev`. All changes come through pull requests. `main` requires at least one approval and passing CI.

### Commit Convention

This project enforces [Conventional Commits](https://www.conventionalcommits.org/) via a `commit-msg` pre-commit hook.

```
feat(invoices): add flat discount support
fix(auth): handle expired refresh token correctly
docs: update environment variable reference
chore(ci): cache uv.lock in GitHub Actions
test(tenants): add cross-tenant isolation test
refactor(pdf): extract template rendering to helper
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`, `build`

### Pre-commit Hooks

```bash
uv tool install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
```

On every commit, the following run automatically:

- Trailing whitespace removal
- End-of-file newline enforcement
- YAML, TOML, and JSON syntax validation
- Ruff lint with auto-fix
- Ruff format on backend Python files
- Prettier on frontend JS, JSX, CSS, and JSON files
- Conventional commit message validation

To run all hooks manually:

```bash
pre-commit run --all-files
```

## CI/CD

The GitHub Actions pipeline runs on every push and pull request to `main` and `dev`.

| Job | Steps |
|---|---|
| `backend-lint` | `uv sync --frozen`, `ruff check`, `ruff format --check`, `mypy` |
| `backend-test` | `uv sync --frozen`, `pytest --cov` (requires lint to pass) |
| `frontend-lint` | `npm ci`, `eslint`, `vite build` |

`--frozen` in CI means the pipeline will fail if `uv.lock` is not committed or is out of sync with `pyproject.toml`. This prevents dependency drift between environments.

`astral-sh/setup-uv` caches the uv package cache keyed on `backend/uv.lock` and invalidates automatically when any dependency changes.

Any lint violation, type error, test failure, or frontend build error fails the relevant job and blocks merging. ESLint runs with `--max-warnings 0`.


## Contributing

1. Fork the repo and create a branch from `dev`: `git checkout -b feat/your-feature dev`
2. Install pre-commit hooks: `pre-commit install && pre-commit install --hook-type commit-msg`
3. Make changes with small, focused commits
4. Ensure tests pass: `uv run pytest`
5. Ensure lint passes: `uv run ruff check . && uv run ruff format --check .`
6. Open a pull request against `dev`

Do not open PRs against `main` directly.
