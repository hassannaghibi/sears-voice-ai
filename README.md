# Sears Home Services — Voice AI

Inbound voice agent for home appliance diagnostics and technician scheduling. Built with **FastAPI**, **Twilio Media Streams**, **OpenAI Realtime API**, and **PostgreSQL**.

## Quick start (Docker)

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY, TWILIO_*, BASE_URL (public HTTPS URL for webhooks)

docker compose up --build
curl http://localhost:8000/health
```

On first boot the container runs Alembic migrations, seeds 8 Chicago-area technicians, and starts Uvicorn on port **8000**.

## Architecture

```
Caller → Twilio → POST /voice/inbound (TwiML Stream)
              → WebSocket /voice/stream/{call_sid}
              → OpenAI Realtime API (Alex persona + tools)
              → SchedulingService → PostgreSQL
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the sequence diagram and [docs/TECHNICAL_DESIGN.md](docs/TECHNICAL_DESIGN.md) for design rationale.

## API overview

| Route | Purpose |
|-------|---------|
| `GET /health` | Health check |
| `GET /api/v1/technicians` | List / search technicians by zip, specialty, date |
| `POST /api/v1/appointments` | Book appointment |
| `POST /voice/inbound` | Twilio inbound webhook |
| `WebSocket /voice/stream/{call_sid}` | Audio bridge |
| `POST /api/v1/images/upload-link` | Tier 3 — email upload link |
| `POST /api/v1/images/{token}/analyze` | Tier 3 — GPT-4o Vision analysis |

## Twilio + ngrok (local dev)

```bash
ngrok http 8000
# Set BASE_URL=https://YOUR_SUBDOMAIN.ngrok-free.app (no trailing slash)
```

In Twilio Console → Phone Number → Voice:
- **Webhook URL:** `{BASE_URL}/voice/inbound`
- **Status callback:** `{BASE_URL}/voice/status`

## CI/CD — deploy to dev server

Pushes to the **`dev`** branch trigger [.github/workflows/deploy-dev.yml](.github/workflows/deploy-dev.yml), which SSHs into the server, pulls latest code, writes `.env` from GitHub Secrets, and runs `docker compose up --build`.

### Required GitHub Secrets

The workflow uses **`environment: dev`**. Add secrets under **Settings → Environments → dev → Environment secrets** (not only repository secrets). Missing `SSH_HOST` causes: `Error: missing server host`.

| Secret | Required | Value for dev server |
|--------|----------|----------------------|
| `SSH_HOST` | Yes | `165.245.212.11` |
| `SSH_USER` | Yes | `root` |
| `SSH_PASSWORD` | Yes | *(your server password — GitHub only)* |
| `POSTGRES_PASSWORD` | Yes | `SearsDevPass2026!` |
| `OPENAI_API_KEY` | Yes | Real `sk-...` key (server currently has placeholder) |
| `TWILIO_ACCOUNT_SID` | Yes | Real `AC...` SID (server currently has placeholder) |
| `TWILIO_AUTH_TOKEN` | Yes | Real auth token |
| `TWILIO_PHONE_NUMBER` | Yes | Real `+1...` number |
| `BASE_URL` | Yes | `https://165-245-212-11.sslip.io` |
| `SECRET_KEY` | Yes | 32+ char random string |
| `NGINX_SERVER_NAME` | First deploy | `165-245-212-11.sslip.io` |
| `CERTBOT_EMAIL` | First deploy | Your email for Let's Encrypt |
| `SENDGRID_API_KEY` | Tier 3 | SendGrid API key |
| `FROM_EMAIL` | Tier 3 | Verified sender address |

Server app directory: `/opt/sears-voice-ai`

Full audit (what is set vs placeholder on the server): [docs/SECRETS.md](docs/SECRETS.md)

## Testing

```bash
# Unit + integration (SQLite in-memory)
pytest tests/unit tests/integration -v --cov=app --cov-fail-under=80

# E2E smoke (against running stack)
E2E_BASE_URL=http://localhost:8000 pytest tests/e2e -m e2e -v
```

## Project docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — sequence diagrams
- [docs/TECHNICAL_DESIGN.md](docs/TECHNICAL_DESIGN.md) — design rationale
- [docs/SECRETS.md](docs/SECRETS.md) — credentials & deploy secrets
- [docs/adr/](docs/adr/) — architecture decision records
