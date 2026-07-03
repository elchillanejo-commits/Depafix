#!/bin/bash
set -e
echo "=== SETUP VPS DEPAFIX/GESTALT $(date) ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -q && apt-get install -y ufw fail2ban postgresql python3-pip nginx certbot python3-certbot-nginx -q
ufw allow 22/tcp; ufw allow 80/tcp; ufw allow 443/tcp; ufw --force enable
systemctl enable fail2ban && systemctl start fail2ban
sudo -u postgres psql -c "CREATE USER depafix WITH PASSWORD 'CAMBIAR_PWD_VPS';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE depafix OWNER depafix;" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE depafix TO depafix;"
pip3 install fastapi uvicorn psycopg2-binary requests beautifulsoup4 python-jose passlib anthropic reportlab pillow -q
mkdir -p /home/ubuntu/depafix/logs /home/ubuntu/depafix/static
cat > /etc/systemd/system/depafix-api.service << 'SVC'
[Unit]
Description=Depafix API Gestalt
After=network.target postgresql.service
[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/depafix
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
EnvironmentFile=/home/ubuntu/depafix/.env
[Install]
WantedBy=multi-user.target
SVC
systemctl daemon-reload && systemctl enable depafix-api
echo "=== VPS LISTO. Ejecutar deploy_gestalt.sh desde laptop ==="
