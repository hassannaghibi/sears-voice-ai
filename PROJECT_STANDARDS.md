# PROJECT STANDARDS
## Sears Home Services — Voice AI Take-Home Assignment

All agents (Architect, Backend, Voice Engineer, Reviewer, QA, DevOps) must follow these standards without exception. This document is the single source of truth for engineering decisions on this project.

---

## 1. Technology Stack (Locked)

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.11+ |
| Backend Framework | FastAPI | 0.111+ |
| ORM | SQLAlchemy | 2.x (async) |
| Migrations | Alembic | Latest |
| Database | PostgreSQL | 15 |
| Validation | Pydantic | v2 |
| Settings | pydantic-settings | v2 |
| Testing | pytest + pytest-asyncio | Latest |
| HTTP Client (tests) | httpx | Latest |
| Containerisation | Docker + Compose v2 | Latest |
| Telephony | Twilio | Latest SDK |
| Voice AI | OpenAI Realtime API | gpt-4o-realtime-preview |
| Vision (Tier 3) | GPT-4o Vision | Latest |
| Logging | Python `logging` (JSON) | stdlib |

---

## 2. Repository Structure

```
sears-voice-ai/
├── .cursor/
│   ├── agents/              # Agent role definitions
│   └── rules/               # Cursor rules (.mdc files)
├── app/
│   ├── api/v1/routes/       # FastAPI routers
│   ├── core/                # Config, DB engine, security
│   ├── models/              # SQLAlchemy models
│   ├── repositories/        # Data access layer
│   ├── schemas/             # Pydantic I/O schemas
│   ├── services/            # Business logic
│   ├── voice/               # OpenAI Realtime integration
│   ├── seed.py              # Sample data loader
│   └── main.py              # FastAPI app entry point
├── alembic/                 # Migration scripts
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
├── PROJECT_STANDARDS.md     # This file
└── IMPLEMENTATION_PLAN.md
```

---

## 3. Non-Negotiable Engineering Rules

### 3.1 Tests
- **Every backend function in `services/` and `repositories/` must have a unit test.**
- **Every API endpoint must have an integration test.**
- Tests run with: `pytest tests/ -v --cov=app --cov-fail-under=80`
- No feature is complete without passing tests.

### 3.2 Schema Changes
- **Never modify the database schema directly.** Always use Alembic:
  ```bash
  alembic revision --autogenerate -m "add_appointment_status_column"
  alembic upgrade head
  ```
- Every migration must implement both `upgrade()` and `downgrade()`.
- Test the downgrade before committing.

### 3.3 Repository Pattern
- **No direct ORM queries in route handlers.**
- All database access goes through `app/repositories/` classes.
- Route handlers call services; services call repositories.

### 3.4 Secrets Management
- **No secrets in source code, ever.**
- All credentials from environment variables via `pydantic-settings`.
- `.env` is gitignored; `.env.example` is committed with placeholder values.

### 3.5 Code Review
- **No feature is marked complete without Reviewer agent sign-off.**
- Apply the reviewer checklist in `reviewer.md` to every change.

### 3.6 Verification
- **Never say "done" without running the verification checklist in `verification-before-completion.mdc`.**
- Includes: tests passing, coverage met, Docker starts clean, `/health` responds.

---

## 4. Code Style

### Python
- **PEP 8** — enforced via `ruff`
- **Full type annotations** — every function parameter and return type
- **No bare `except:`** — always catch specific exceptions
- **No `print()`** — use `logging` throughout
- Maximum function length: **40 lines** (refactor if longer)
- Maximum file length: **300 lines** (split into modules if longer)

### Async
- All FastAPI route handlers must be `async def`
- All database calls must use `await`
- No blocking I/O (`time.sleep`, `requests.get`) in async functions — use `asyncio.sleep` and `httpx.AsyncClient`

### Imports
```python
# Order: stdlib → third-party → local (separated by blank lines)
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.technician import TechnicianRepository
```

---

## 5. Database Standards

- Primary keys: `Integer` for internal join tables, use `id: Mapped[int]`
- All timestamps: `DateTime(timezone=True)` — always timezone-aware
- Soft deletes: add `deleted_at: Mapped[datetime | None]` rather than hard deletes for appointments
- Indexes: required on all foreign key columns and frequently filtered columns
- Table names: snake_case, plural (e.g., `technicians`, `service_areas`, `appointments`)

---

## 6. API Standards

- All routes versioned under `/api/v1/`
- Twilio webhook routes under `/voice/`
- All routes must declare `response_model` and `status_code`
- Error responses use `ErrorDetail` schema: `{"code": "...", "message": "..."}`
- Pagination on all list endpoints: `{"data": [...], "total": N, "page": N, "page_size": N}`

---

## 7. Voice Agent Standards

- Latency target: first audio byte within **500 ms** of VAD silence detection
- Always use `server_vad` turn detection mode with OpenAI Realtime API
- Filler phrase required if any tool call may take >2 seconds
- System prompt must specify: name (Alex), company (Sears Home Services), tone (professional/warm)
- Conversation context must persist across the full call — never re-ask for information already given

---

## 8. Docker Standards

- Single command startup: `docker compose up --build`
- Database seeded automatically on first boot (idempotent)
- Migrations run automatically in container entrypoint
- Non-root user inside all containers
- Health checks on all services

---

## 9. Delivery Checklist

The project is ready for submission when:
- [ ] `docker compose up --build` starts cleanly from scratch
- [ ] Live Twilio phone number is functional
- [ ] All three tiers implemented (Core, Scheduling, + as much of Visual as time permits)
- [ ] 5–10 technicians seeded across multiple zip codes and specialties
- [ ] All tests pass with ≥80% coverage
- [ ] `.env.example` committed with all required keys
- [ ] Technical Design Document written (1–2 pages)
- [ ] Git repository is clean (no debug code, no TODO in production paths)
