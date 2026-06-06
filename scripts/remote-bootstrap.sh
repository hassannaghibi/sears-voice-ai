#!/bin/bash
set -euo pipefail
APP_DIR=/opt/sears-voice-ai
REPO=https://github.com/hassannaghibi/sears-voice-ai.git

ENV_FILE=""
if [ -f "$APP_DIR/.env" ]; then
  ENV_FILE=$(mktemp)
  cp "$APP_DIR/.env" "$ENV_FILE"
fi

if [ ! -d "$APP_DIR/.git" ]; then
  rm -rf "$APP_DIR"
  git clone -b dev "$REPO" "$APP_DIR"
else
  cd "$APP_DIR"
  git fetch origin dev
  git checkout dev
  git reset --hard origin/dev
fi

cd "$APP_DIR"

if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
  cp "$ENV_FILE" .env
  rm -f "$ENV_FILE"
elif [ ! -f .env ]; then
  cat > .env <<'EOF'
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=sears_voice
POSTGRES_USER=sears
POSTGRES_PASSWORD=SearsDevPass2026!
OPENAI_API_KEY=sk-placeholder-for-tests
TWILIO_ACCOUNT_SID=ACtest0000000000000000000000000000
TWILIO_AUTH_TOKEN=test_auth_token_for_dev
TWILIO_PHONE_NUMBER=+15555550100
BASE_URL=https://165-245-212-11.sslip.io
APP_ENV=development
SECRET_KEY=dev-secret-key-32-characters-min
LOG_LEVEL=INFO
SENDGRID_API_KEY=
FROM_EMAIL=alex@sears-voice.example.com
UPLOAD_LINK_TTL_HOURS=24
EOF
fi

# Always point BASE_URL at HTTPS domain for Twilio
sed -i 's|^BASE_URL=.*|BASE_URL=https://165-245-212-11.sslip.io|' .env

chmod +x scripts/deploy.sh scripts/setup-nginx-ssl.sh entrypoint.sh
echo "=== GIT HEAD ==="
git log -1 --oneline
echo "=== DOCKER DEPLOY ==="
./scripts/deploy.sh
