#!/bin/bash
# Install nginx + Let's Encrypt TLS for Twilio webhooks.
# Usage: SERVER_NAME=165-245-212-11.sslip.io CERTBOT_EMAIL=you@example.com ./scripts/setup-nginx-ssl.sh
set -euo pipefail

SERVER_NAME="${SERVER_NAME:-165-245-212-11.sslip.io}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-admin@${SERVER_NAME}}"
APP_DIR="${APP_DIR:-/opt/sears-voice-ai}"

echo "==> Installing nginx and certbot..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx

mkdir -p /var/www/certbot

echo "==> Installing nginx site config for ${SERVER_NAME}..."
sed "s/SERVER_NAME/${SERVER_NAME}/g" "${APP_DIR}/deploy/nginx/sears-voice-ai.conf" \
  > /etc/nginx/sites-available/sears-voice-ai

# Bootstrap HTTP-only config for certbot (certs don't exist yet)
cat > /etc/nginx/sites-available/sears-voice-ai-bootstrap <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${SERVER_NAME};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/sears-voice-ai-bootstrap /etc/nginx/sites-enabled/sears-voice-ai
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

echo "==> Requesting TLS certificate..."
certbot certonly --webroot -w /var/www/certbot \
  -d "${SERVER_NAME}" \
  --non-interactive --agree-tos -m "${CERTBOT_EMAIL}" \
  --no-eff-email || certbot --nginx -d "${SERVER_NAME}" \
  --non-interactive --agree-tos -m "${CERTBOT_EMAIL}" --no-eff-email

echo "==> Enabling full HTTPS config..."
ln -sf /etc/nginx/sites-available/sears-voice-ai /etc/nginx/sites-enabled/sears-voice-ai
nginx -t
systemctl reload nginx

echo "==> Updating BASE_URL in ${APP_DIR}/.env ..."
if [ -f "${APP_DIR}/.env" ]; then
  sed -i "s|^BASE_URL=.*|BASE_URL=https://${SERVER_NAME}|" "${APP_DIR}/.env"
  cd "${APP_DIR}" && docker compose up -d api 2>/dev/null || true
else
  echo "WARN: ${APP_DIR}/.env not found — set BASE_URL=https://${SERVER_NAME} manually"
fi

echo "==> Done. HTTPS URL: https://${SERVER_NAME}"
echo "    Health: curl -s https://${SERVER_NAME}/health"
