# ADR-003: Database — PostgreSQL 15

**Status:** Accepted

## Context
Scheduling requires relational integrity (technicians, slots, appointments) plus flexible call context.

## Decision
**PostgreSQL 15** with async SQLAlchemy 2.x and Alembic migrations.

## Rationale
- FK constraints prevent orphan appointments
- JSON/JSONB for `call_sessions.context`
- `SELECT FOR UPDATE` for atomic slot booking

## Alternatives considered
SQLite — used in tests only; not suitable for concurrent production booking.
