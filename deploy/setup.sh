#!/usr/bin/env bash
set -euo pipefail

python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

cat <<'SERVICE' | sudo tee /etc/systemd/system/affiliate-agent.service >/dev/null
[Unit]
Description=Affiliate Commission Agent API
After=network.target

[Service]
WorkingDirectory=$(pwd)/backend
ExecStart=$(pwd)/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable affiliate-agent
sudo systemctl restart affiliate-agent
