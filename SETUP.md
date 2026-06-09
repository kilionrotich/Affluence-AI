# Setup Guide

## 1) Backend Setup

```bash
cd /tmp/workspace/kilionrotich/Affluence-AI
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Create environment variables (example values):

```bash
export DATABASE_URL='sqlite:///./affiliate.db'        # Dev (Production: postgresql+psycopg://...)
export ADMIN_TOKEN='admin-token'
export VIEWER_TOKEN='viewer-token'
export REFUND_PERIOD_DAYS='7'
export PAYOUT_THRESHOLD='50'
export REQUIRE_HTTPS='false'
```

Run API:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run backend tests:

```bash
cd backend
python3 -m pytest -q
```

## 2) Frontend Setup

```bash
cd /tmp/workspace/kilionrotich/Affluence-AI/frontend
npm install
```

Set frontend env vars:

```bash
export VITE_API_BASE_URL='http://localhost:8000'
export VITE_ADMIN_TOKEN='admin-token'
export VITE_VIEWER_TOKEN='viewer-token'
```

Run frontend:

```bash
npm run dev
```

Build and lint:

```bash
npm run lint
npm run build
```

## 3) Workflow
1. Call `POST /scan`
2. Record purchases with `POST /purchase`
3. Validate with `POST /validate`
4. Trigger payout using `POST /payout`
5. Open dashboard and refresh report data

## 4) Production Hosting (VPS)
- Supported targets: Hetzner, DigitalOcean, AWS Lightsail
- Reverse proxy with Nginx using `deploy/nginx.conf`
- Obtain TLS certificates with Let's Encrypt (`certbot`)
- Run API with systemd (`deploy/setup.sh` template)
- Keep scheduler enabled for background polling/validation jobs

## 5) Integrations
Adapters are scaffolded for:
- Amazon Associates
- ClickBank
- CJ Affiliate
- Jumia Partners
- PayPal Payouts
- M-Pesa Daraja

Replace adapter internals with provider credentials and API calls.
