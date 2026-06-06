# Secrets & Credentials

Single reference for local `.env`, GitHub Actions deploy secrets, and server status.

**Server:** `165.245.212.11` · **App dir:** `/opt/sears-voice-ai` · **Public URL:** `https://165-245-212-11.sslip.io`

> Never commit real secrets to git. Store deploy credentials only in GitHub **Environment secrets** (`dev`) or server `.env`.

---

## GitHub Actions secrets (required for deploy)

The workflow [`.github/workflows/deploy-dev.yml`](../.github/workflows/deploy-dev.yml) uses `environment: dev`. Add **all** secrets under:

**GitHub → Settings → Environments → dev → Environment secrets**

If `SSH_HOST` (or any secret below) is missing, deploy fails with `Error: missing server host`.

| Secret | Required | Example / current value | Purpose |
|--------|----------|-------------------------|---------|
| `SSH_HOST` | **Yes** | `165.245.212.11` | Deploy SSH target |
| `SSH_USER` | **Yes** | `root` | Deploy SSH user |
| `SSH_PASSWORD` | **Yes** | *(set in GitHub only)* | Deploy SSH password |
| `POSTGRES_PASSWORD` | **Yes** | `SearsDevPass2026!` | PostgreSQL password (must match server) |
| `OPENAI_API_KEY` | **Yes** | `sk-...` (real key) | OpenAI Realtime + Vision |
| `TWILIO_ACCOUNT_SID` | **Yes** | `AC...` (real SID) | Twilio account |
| `TWILIO_AUTH_TOKEN` | **Yes** | *(real token)* | Twilio webhook validation |
| `TWILIO_PHONE_NUMBER` | **Yes** | `+1...` (real number) | Inbound voice number |
| `BASE_URL` | **Yes** | `https://165-245-212-11.sslip.io` | Public HTTPS URL (no trailing slash) |
| `SECRET_KEY` | **Yes** | 32+ random chars | App signing / internal use |
| `NGINX_SERVER_NAME` | First deploy | `165-245-212-11.sslip.io` | TLS certificate domain |
| `CERTBOT_EMAIL` | First deploy | your email | Let's Encrypt registration |
| `SENDGRID_API_KEY` | Tier 3 | `SG....` | Upload-link emails |
| `FROM_EMAIL` | Tier 3 | verified SendGrid sender | Email From header |

After adding secrets, push to **`dev`** or re-run the failed Actions job.

---

## Application environment variables

Written to `/opt/sears-voice-ai/.env` on each deploy. See [`.env.example`](../.env.example) for local development.

| Variable | Tier | Server status (2026-06-06) | Notes |
|----------|------|--------------------------|-------|
| `POSTGRES_HOST` | Core | ✅ `db` | Docker service name |
| `POSTGRES_PORT` | Core | ✅ `5432` | |
| `POSTGRES_DB` | Core | ✅ `sears_voice` | |
| `POSTGRES_USER` | Core | ✅ `sears` | |
| `POSTGRES_PASSWORD` | Core | ✅ Set | Real password configured |
| `OPENAI_API_KEY` | Core | ❌ **Placeholder** | `sk-placeholder-for-tests` — voice will not work |
| `TWILIO_ACCOUNT_SID` | Core | ❌ **Placeholder** | `ACtest...` — webhooks/calls will not work |
| `TWILIO_AUTH_TOKEN` | Core | ❌ **Placeholder** | Test token — signature validation fails with real Twilio |
| `TWILIO_PHONE_NUMBER` | Core | ❌ **Placeholder** | `+15555550100` |
| `BASE_URL` | Core | ✅ Set | Matches nginx + TLS |
| `APP_ENV` | Core | ⚠️ `development` | Recommend `production` on server |
| `SECRET_KEY` | Core | ⚠️ Dev default | Replace with strong random value |
| `LOG_LEVEL` | Core | ✅ `INFO` | |
| `SENDGRID_API_KEY` | Tier 3 | ❌ **Empty** | Email upload links disabled |
| `FROM_EMAIL` | Tier 3 | ⚠️ Placeholder | `alex@sears-voice.example.com` |
| `UPLOAD_LINK_TTL_HOURS` | Tier 3 | ✅ `24` | |

---

## Server infrastructure status (2026-06-06)

| Check | Status |
|-------|--------|
| Docker `api` + `db` | ✅ Healthy |
| `GET /health` | ✅ `{"status":"ok","version":"1.0.0"}` |
| nginx reverse proxy | ✅ `165-245-212-11.sslip.io` |
| TLS (Let's Encrypt) | ✅ Valid until 2026-09-04 |

---

## Twilio console (after real credentials)

Configure on your Twilio phone number:

| Setting | URL |
|---------|-----|
| Voice webhook (POST) | `https://165-245-212-11.sslip.io/voice/inbound` |
| Status callback (POST) | `https://165-245-212-11.sslip.io/voice/status` |

---

## What blocks live voice today

1. **GitHub Actions** — `SSH_HOST` / other secrets not set → deploy workflow fails before updating server.
2. **Server `.env`** — OpenAI and Twilio are still placeholders → REST API works; live calls do not.
3. **Tier 3** — `SENDGRID_API_KEY` empty → upload-link emails will fail.

Once real keys are in GitHub `dev` environment secrets and deploy succeeds, the workflow overwrites server `.env` automatically.
