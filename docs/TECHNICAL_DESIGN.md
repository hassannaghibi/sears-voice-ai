# Technical Design Document
## Sears Home Services Voice AI

### 1. Problem

Homeowners call when an appliance fails. They often cannot self-diagnose. We need an inbound voice agent that gathers symptoms, offers safe troubleshooting, and schedules a qualified technician when needed.

### 2. Solution overview

A **FastAPI** backend accepts Twilio inbound calls, bridges audio to the **OpenAI Realtime API** (`gpt-4o-realtime-preview`), and exposes tool functions the model invokes for persistence and scheduling. PostgreSQL stores technicians, availability, appointments, and per-call conversation state.

### 3. Key technology choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Telephony | Twilio Media Streams | Mature PSTN + bidirectional WebSocket audio; minimal custom SIP |
| Voice AI | OpenAI Realtime API | Single WebSocket for STT + LLM + TTS; low integration surface |
| Backend | FastAPI + async SQLAlchemy | Native async fits WebSocket + DB concurrency |
| Database | PostgreSQL 15 | Relational scheduling data; JSONB for call context |
| Email (Tier 3) | SendGrid | Simple transactional email for upload links |
| Vision (Tier 3) | GPT-4o | Same vendor as voice; strong appliance photo understanding |
| Deployment | Docker Compose | Single-command reproducible stack |

See [adr/](adr/) for detailed ADRs.

### 4. Conversation design

**Persona:** Alex, Sears Home Services advisor — warm, concise, professional.

**State machine:** GREETING → APPLIANCE_ID → SYMPTOM_COLLECTION → DIAGNOSIS → RESOLUTION_CHECK → (optional) SCHEDULING → CONFIRMATION. Context is stored in `call_sessions.context` so the agent never re-asks collected fields.

**Tools:** Six functions bridge the LLM to backend services — symptom capture, technician search (with zip validation and next-date fallback), booking, callback capture, image upload link, and explicit state updates.

### 5. Scheduling model

Technicians have **service areas** (zip codes), **specialties** (appliance types), and **availability slots**. Booking uses `SELECT … FOR UPDATE` on the slot row to prevent double-booking (HTTP 409 / voice tool error).

Matching ranks technicians by open slot count and returns the top three for the agent to offer verbally.

### 6. Security

- Twilio webhook signature validation on `/voice/inbound` and `/voice/status`
- Secrets via environment variables only
- Upload tokens are random, time-limited, and bound to `call_sessions`

### 7. Tradeoffs

| Tradeoff | Accepted limitation |
|----------|---------------------|
| Realtime API cost/latency | Simpler than separate STT+LLM+TTS pipeline |
| Upload token lookup scans JSON context | Good enough at take-home scale; would index in production |
| Single Uvicorn worker | Sufficient for demo; scale with multiple workers + sticky sessions for WS |

### 8. Future improvements

- Dedicated `upload_tokens` table with TTL index
- Redis for call state hot path
- Nginx TLS termination on the dev/prod host
- Human handoff queue for no-coverage zip codes
