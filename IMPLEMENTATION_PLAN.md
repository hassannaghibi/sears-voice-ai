# IMPLEMENTATION PLAN
## Sears Home Services — Voice AI Take-Home Assignment

**Total estimated effort:** 3–4 hours (Tier 1 + Tier 2) | 5–6 hours (all tiers)  
**Agents involved:** Architect → Backend → Voice Engineer → DevOps → QA → Reviewer

---

## Phase 1 — Architecture & Project Bootstrap
**Owner:** Architect + DevOps  
**Estimated time:** 30 minutes  
**Goal:** Project is runnable (empty shell) before any features are built.

### Deliverables
- [ ] Git repository initialised with `.gitignore`
- [ ] `requirements.txt` with all pinned dependencies
- [ ] `Dockerfile` (multi-stage, non-root user)
- [ ] `docker-compose.yml` with `db` + `api` services and health checks
- [ ] `entrypoint.sh` running migrations then uvicorn
- [ ] `.env.example` with all required keys
- [ ] `app/main.py` — FastAPI app skeleton with CORS, logging, lifespan
- [ ] `app/core/config.py` — pydantic-settings `Settings` class
- [ ] `app/core/database.py` — async SQLAlchemy engine + session factory
- [ ] `GET /health` route returning `{"status": "ok", "version": "1.0.0"}`
- [ ] Architecture Decision Records written for: voice provider, LLM, database, email
- [ ] Mermaid sequence diagram: inbound call happy path

### Verification
```bash
docker compose up --build
curl http://localhost:8000/health  # → {"status": "ok"}
```

---

## Phase 2 — Database Design & Seeding
**Owner:** Backend  
**Estimated time:** 45 minutes  
**Goal:** Full schema implemented, migrations running, sample data loaded.

### Database Schema

#### `technicians`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| name | String(100) | |
| email | String(255) | unique |
| phone | String(20) | |
| created_at | DateTime TZ | server_default |
| updated_at | DateTime TZ | |

#### `service_areas`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| technician_id | FK → technicians | ondelete=CASCADE |
| zip_code | String(10) | indexed |

#### `specialties`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| technician_id | FK → technicians | ondelete=CASCADE |
| appliance_type | Enum | washer, dryer, refrigerator, dishwasher, oven, hvac, other |

#### `availability_slots`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| technician_id | FK → technicians | ondelete=CASCADE |
| start_time | DateTime TZ | |
| end_time | DateTime TZ | |
| is_booked | Boolean | default=False |

#### `appointments`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| technician_id | FK → technicians | ondelete=RESTRICT |
| slot_id | FK → availability_slots | ondelete=RESTRICT |
| customer_name | String(100) | |
| customer_phone | String(20) | |
| customer_email | String(255) | nullable |
| zip_code | String(10) | |
| appliance_type | Enum | |
| symptoms | Text | |
| status | Enum | pending, confirmed, cancelled |
| call_sid | String(64) | Twilio call SID |
| created_at | DateTime TZ | |

#### `call_sessions` (voice context persistence)
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| call_sid | String(64) | unique, indexed |
| state | String(50) | conversation state machine |
| context | JSONB | accumulated call context |
| appointment_id | FK → appointments | nullable |
| created_at | DateTime TZ | |
| updated_at | DateTime TZ | |

### Deliverables
- [ ] All SQLAlchemy models created in `app/models/`
- [ ] Initial Alembic migration: `alembic revision --autogenerate -m "initial_schema"`
- [ ] `app/seed.py` — 8 technicians across Chicago-area zip codes (60601, 60614, 60626, 60629, 60641), each with 2-3 specialties and 10 availability slots over the next 14 days
- [ ] Seed is idempotent (safe to run multiple times)
- [ ] All repositories implemented: `TechnicianRepository`, `AppointmentRepository`, `SlotRepository`, `CallSessionRepository`
- [ ] Unit tests for all repositories

### Verification
```bash
docker compose up --build
docker compose exec api python -m app.seed
docker compose exec db psql -U postgres sears_voice_ai -c "SELECT COUNT(*) FROM technicians;"
# → 8
```

---

## Phase 3 — Scheduling APIs
**Owner:** Backend + Reviewer  
**Estimated time:** 45 minutes  
**Goal:** Full REST API for technician lookup and appointment booking.

### Endpoints
- [ ] `GET /api/v1/technicians?zip={zip}&specialty={type}&date={date}`
- [ ] `GET /api/v1/technicians/{id}/availability?date={date}`
- [ ] `POST /api/v1/appointments` — creates appointment + marks slot as booked
- [ ] `GET /api/v1/appointments/{id}`
- [ ] `PATCH /api/v1/appointments/{id}` — update status (confirm/cancel)

### Business Logic (SchedulingService)
- [ ] `find_available_technicians(zip: str, specialty: ApplianceType, date: date) → list[Technician]`
  - Match by zip code in `service_areas`
  - Match by appliance type in `specialties`
  - Only return technicians with at least one unbooked slot on the requested date
- [ ] `book_slot(slot_id: int, appointment_data: AppointmentCreate) → Appointment`
  - Atomic: check slot is still available + create appointment + mark slot booked in one transaction
  - Raises `SlotNotAvailableError` if already booked (→ HTTP 409)

### Deliverables
- [ ] `app/services/scheduling.py`
- [ ] `app/api/v1/routes/technicians.py`
- [ ] `app/api/v1/routes/appointments.py`
- [ ] All Pydantic schemas for request/response
- [ ] Integration tests covering: happy path, no technician found, slot conflict, invalid zip

### Verification
```bash
curl "http://localhost:8000/api/v1/technicians?zip=60601&specialty=washer"
# → list of technicians with availability

curl -X POST http://localhost:8000/api/v1/appointments \
  -H "Content-Type: application/json" \
  -d '{"technician_id": 1, "slot_id": 3, "customer_name": "Jane Smith", ...}'
# → 201 with appointment details
```

---

## Phase 4 — Voice Agent (OpenAI Realtime API)
**Owner:** Voice Engineer + Backend  
**Estimated time:** 60 minutes  
**Goal:** Inbound Twilio call connects to OpenAI Realtime API and can complete the full diagnostic conversation.

### Twilio Webhook Flow
```
Twilio inbound call
  → POST /voice/inbound
  → FastAPI returns TwiML: <Connect><Stream url="wss://host/voice/stream/{call_sid}"/>
  → Twilio opens WebSocket to /voice/stream/{call_sid}
  → FastAPI bridges audio to OpenAI Realtime API
```

### Deliverables
- [ ] `POST /voice/inbound` — validates Twilio signature, returns TwiML with Media Stream
- [ ] `POST /voice/status` — handles call status callbacks (completed, failed)
- [ ] `WebSocket /voice/stream/{call_sid}` — bridges Twilio ↔ OpenAI Realtime API
- [ ] `app/voice/session.py` — OpenAI Realtime API WebSocket manager
- [ ] `app/voice/prompts.py` — system prompt construction (Alex persona, instructions, context)
- [ ] `app/voice/tools.py` — all 6 tool definitions + handler functions
- [ ] `app/core/security.py` — Twilio signature validation dependency
- [ ] Audio transcoding: μ-law 8kHz ↔ PCM16 24kHz

### System Prompt Key Instructions
```
You are Alex, a voice assistant for Sears Home Services.
Your goal: diagnose appliance issues and schedule technician visits when needed.
State machine: GREETING → APPLIANCE_ID → SYMPTOM_COLLECTION → DIAGNOSIS → [SCHEDULING] → CONFIRMATION
Keep responses under 30 words. Never ask for information already provided.
When scheduling: use find_available_technicians tool, offer 3 time slots, confirm booking verbally.
```

### Tool Handler Integration
Each voice tool call triggers the corresponding service method and returns structured JSON to the LLM.

### Verification
- Use Twilio test credentials to trigger a call
- Verify audio bridge connects (WebSocket log shows "Connected to OpenAI Realtime API")
- Verify tool calls appear in logs when LLM triggers them
- Full conversation test: appliance identified → symptoms collected → diagnosis → scheduling offer → booking confirmed

---

## Phase 5 — Technician Matching Intelligence
**Owner:** Backend + Voice Engineer  
**Estimated time:** 30 minutes  
**Goal:** Matching logic is robust and the voice agent can seamlessly handle the scheduling conversation.

### Matching Algorithm
1. Filter technicians by zip code (`service_areas.zip_code = caller_zip`)
2. Filter by specialty (`specialties.appliance_type = identified_appliance`)
3. Filter by date availability (`availability_slots` with `is_booked = false`)
4. Sort by: number of available slots DESC (prefer technicians with more flexibility)
5. Return top 3 technicians for voice agent to present

### Edge Cases to Handle
- [ ] No technician in zip → "I'm sorry, we don't have coverage in your area yet. Let me take your information and have someone call you back."
- [ ] All slots booked for requested date → offer next available date
- [ ] Caller provides partial zip → ask to confirm
- [ ] Caller changes mind about date → restart slot selection without losing other context

### Deliverables
- [ ] Enhanced `SchedulingService.find_available_technicians()` with all edge cases
- [ ] Voice tool handler for `find_available_technicians` with natural language formatting
- [ ] Tests for all edge cases

---

## Phase 6 — Docker & Deployment
**Owner:** DevOps  
**Estimated time:** 30 minutes  
**Goal:** Full system launches with `docker compose up --build` from a clean clone.

### Deliverables
- [ ] Final `Dockerfile` (multi-stage, non-root user, `entrypoint.sh`)
- [ ] Final `docker-compose.yml` with healthchecks and dependencies
- [ ] `entrypoint.sh` — migrations + seed + uvicorn
- [ ] `.env.example` fully populated with placeholder values
- [ ] `docker compose up --build` tested from scratch (fresh clone simulation)
- [ ] ngrok/Cloudflare Tunnel setup documented for Twilio webhook URL
- [ ] All environment variables documented

### ngrok Setup (Local Development)
```bash
# In a separate terminal
ngrok http 8000

# Copy the HTTPS URL (e.g. https://abc123.ngrok.io)
# Set in .env: BASE_URL=https://abc123.ngrok.io
# Configure in Twilio console: 
#   Voice webhook: https://abc123.ngrok.io/voice/inbound
#   Status callback: https://abc123.ngrok.io/voice/status
```

### Verification
```bash
# Fresh clone simulation
git clone <repo> && cd sears-voice-ai
cp .env.example .env
# Fill in real API keys
docker compose up --build
# Wait for health checks to pass
curl http://localhost:8000/health
# → {"status": "ok"}
```

---

## Phase 7 — Testing & QA Sign-off
**Owner:** QA + Reviewer  
**Estimated time:** 30 minutes  
**Goal:** Full test suite passing, coverage met, system ready for submission.

### Test Execution
```bash
# Full suite with coverage
pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=80

# Unit only (fast feedback)
pytest tests/unit/ -v

# Integration only
pytest tests/integration/ -v
```

### Final QA Checklist
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Coverage ≥ 80% overall, ≥ 90% for `services/`
- [ ] No regressions from any phase
- [ ] Twilio signature validation tested (403 on bad signature)
- [ ] Slot conflict returns 409
- [ ] Appointment booking end-to-end tested
- [ ] Voice conversation state machine tested (mocked audio)
- [ ] Docker startup clean from scratch
- [ ] Live phone number tested manually

### Reviewer Sign-off Checklist
- [ ] All security rules pass (reviewer.md checklist)
- [ ] No hardcoded secrets
- [ ] All routes have tests
- [ ] All migrations reversible
- [ ] Verdict: **APPROVED**

---

## Tier 3 — Visual Diagnosis (Bonus, if time permits)
**Owner:** Backend + Voice Engineer  
**Estimated time:** 45 minutes additional

### Deliverables
- [ ] `POST /api/v1/images/upload-link` — generate signed S3/temp URL, store token in DB
- [ ] Email sent via SendGrid with upload link
- [ ] `POST /api/v1/images/{token}/analyze` — receive uploaded image, call GPT-4o Vision
- [ ] Vision analysis result stored in `call_sessions.context`
- [ ] Voice agent tool: `send_image_upload_link` triggers email during call
- [ ] Voice agent uses vision result to enhance diagnosis after image is uploaded

---

## Phase Summary

| Phase | Owner | Time | Key Output |
|-------|-------|------|-----------|
| 1 — Architecture | Architect + DevOps | 30 min | Running skeleton, ADRs |
| 2 — Database | Backend | 45 min | Schema, migrations, seed data |
| 3 — Scheduling APIs | Backend + Reviewer | 45 min | REST API for booking |
| 4 — Voice Agent | Voice Engineer | 60 min | Full Twilio ↔ OpenAI bridge |
| 5 — Matching | Backend + Voice | 30 min | Robust technician matching |
| 6 — Docker | DevOps | 30 min | Single-command deployment |
| 7 — Testing | QA + Reviewer | 30 min | Full coverage, QA sign-off |
| **Tier 1+2 Total** | | **~4 hrs** | |
| Tier 3 — Vision | Backend + Voice | +45 min | Image diagnosis |
