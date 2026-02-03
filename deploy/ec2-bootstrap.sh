#!/bin/bash
# Run ONCE on a fresh EC2 (Amazon Linux 2023 or Ubuntu 22.04) to install packages,
# Nginx config, and systemd unit. After this, clone the repo and run first deploy.
# Usage: copy to EC2 and run:   bash ec2-bootstrap.sh
# Or as User Data (only first boot): paste this script into Launch Instance → User data.

set -e
APP_USER="${APP_USER:-ec2-user}"
APP_DIR="/home/${APP_USER}/MaheshwariInvestors"

# --- Detect OS ---
if [ -f /etc/os-release ]; then
  . /etc/os-release
  OS_ID="${ID:-unknown}"
else
  OS_ID="unknown"
fi

# --- Install packages ---
if [[ "$OS_ID" == "amzn" ]] || [[ "$OS_ID" == "rhel" ]]; then
  sudo dnf update -y
  sudo dnf install -y python3.11 python3.11-pip nodejs npm nginx git
elif [[ "$OS_ID" == "ubuntu" ]]; then
  sudo apt-get update -y
  sudo apt-get install -y python3.11 python3.11-venv python3-pip nodejs npm nginx git
else
  echo "Unsupported OS: $OS_ID. Install python3.11, node, npm, nginx, git manually."
  exit 1
fi

# --- App directory ---
sudo mkdir -p "$APP_DIR"
sudo chown -R "${APP_USER}:${APP_USER}" "$APP_DIR"

# --- Nginx config (frontend only on 80; API on 8000) ---
NGINX_CONF="/etc/nginx/conf.d/maheshwari.conf"
if [[ "$OS_ID" == "ubuntu" ]]; then
  NGINX_CONF="/etc/nginx/sites-available/maheshwari"
  sudo touch "$NGINX_CONF"
fi

sudo tee "$NGINX_CONF" > /dev/null << 'NGINX_EOF'
server {
    listen 80;
    server_name _;
    root /home/ec2-user/MaheshwariInvestors/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX_EOF

if [[ "$OS_ID" == "ubuntu" ]]; then
  sudo ln -sf /etc/nginx/sites-available/maheshwari /etc/nginx/sites-enabled/maheshwari 2>/dev/null || true
  sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
fi

# --- Systemd unit for FastAPI ---
sudo tee /etc/systemd/system/maheshwari-api.service > /dev/null << SVC_EOF
[Unit]
Description=Maheshwari Investors FastAPI
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/MaheshwariInvestors/backend
Environment="PATH=/home/ec2-user/MaheshwariInvestors/backend/venv/bin"
ExecStart=/home/ec2-user/MaheshwariInvestors/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVC_EOF

sudo systemctl daemon-reload

# --- Ensure Nginx can read frontend/dist (after you build) ---
# Run after first build: sudo chmod -R a+rX /home/ec2-user/MaheshwariInvestors/frontend/dist
echo "Bootstrap done. Next steps:"
echo "  1. Clone repo into $APP_DIR (or upload code)"
echo "  2. Backend: cd $APP_DIR/backend && python3.11 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
echo "  3. Frontend: cd $APP_DIR/frontend && npm ci && export VITE_API_BASE_URL=http://YOUR_PUBLIC_IP:8000 && npm run build"
echo "  4. Permissions: sudo chmod -R a+rX $APP_DIR/frontend/dist"
echo "  5. Start: sudo systemctl enable maheshwari-api && sudo systemctl start maheshwari-api && sudo systemctl enable nginx && sudo systemctl start nginx && sudo nginx -t && sudo systemctl reload nginx"
