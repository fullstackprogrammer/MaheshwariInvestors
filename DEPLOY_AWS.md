# Deploying Maheshwari Investors to AWS

This guide covers two deployment options. **Option A (single EC2)** is the simplest and keeps backend and frontend on one server. **Option B** uses S3 + CloudFront for the frontend and EC2 or Elastic Beanstalk for the API.

---

## Prerequisites

- AWS account
- [AWS CLI](https://aws.amazon.com/cli/) installed and configured (`aws configure`)
- Git (to clone or upload your project)

---

## Option A: Single EC2 Instance (Recommended to start)

One Linux instance runs the FastAPI backend and serves the built React app (e.g. via Nginx). Good for low traffic and simple ops.

### 1. Launch an EC2 instance

1. In **AWS Console → EC2 → Launch Instance**:
   - **Name:** `maheshwari-investors`
   - **AMI:** Amazon Linux 2023 (or Ubuntu 22.04)
   - **Instance type:** `t3.small` or `t3.medium` (backend uses some CPU/memory for yfinance)
   - **Key pair:** Create or select one (you need the `.pem` to SSH)
   - **Security group:** Create one with:
     - **SSH (22)** – Your IP (or 0.0.0.0/0 only if you accept the risk)
     - **HTTP (80)** – 0.0.0.0/0 (for Nginx)
     - **HTTPS (443)** – 0.0.0.0/0 if you add SSL later
     - **Custom TCP 8000** – 0.0.0.0/0 only if you want to hit the API directly; otherwise leave closed and use Nginx proxy only

2. Launch and note the **public IP** (e.g. `3.14.15.92`).

### 2. Connect and install dependencies

```bash
ssh -i your-key.pem ec2-user@YOUR_PUBLIC_IP
# Ubuntu: ssh -i your-key.pem ubuntu@YOUR_PUBLIC_IP
```

**Amazon Linux 2023:**

```bash
sudo dnf update -y
sudo dnf install -y python3.11 python3.11-pip nodejs npm nginx git
```

**Ubuntu 22.04:**

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm nginx git
```

### 3. Deploy the app

**3a. Clone or upload the project** (e.g. under `/home/ec2-user`):

```bash
cd /home/ec2-user
git clone https://github.com/YOUR_ORG/MaheshwariInvestors.git
cd MaheshwariInvestors
# Or upload via scp/rsync from your machine
```

**3b. Backend**

```bash
cd /home/ec2-user/MaheshwariInvestors/backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Ensure CSV is present (project root or data/)
ls -la ../DFWInvestors2026StockPicks.csv   # or ../data/investors.csv
```

**3c. Frontend (build with API URL)**

Set the backend URL to this server (same host). Use the public IP or a domain you’ll point here:

```bash
cd /home/ec2-user/MaheshwariInvestors/frontend
npm ci
export VITE_API_BASE_URL=http://YOUR_PUBLIC_IP:8000
# Or same-origin (Nginx will proxy): export VITE_API_BASE_URL=
npm run build
```

If you will put Nginx in front and proxy `/api` to the backend, you can use same-origin:

```bash
# Same-origin: no env or empty so frontend uses relative URLs
npm run build
```

Then Nginx must proxy requests (e.g. `/api` → `http://127.0.0.1:8000`). The app currently calls root paths like `/health`, `/metrics`; you can either keep the backend on a port and set `VITE_API_BASE_URL=http://YOUR_DOMAIN:8000`, or add an Nginx location that proxies to 8000 (see below).

**3d. Run backend (test)**

```bash
cd /home/ec2-user/MaheshwariInvestors/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
# Ctrl+C after verifying; we'll run it with a process manager next
```

### 4. Nginx: serve frontend and proxy API (optional but recommended)

Use Nginx to serve the built frontend and proxy `/api` to the backend so the frontend can use the same origin (no CORS, same host).

Example Nginx config (Amazon Linux: `/etc/nginx/conf.d/maheshwari.conf`; Ubuntu: `/etc/nginx/sites-available/maheshwari` then symlink into `sites-enabled`):

```nginx
server {
    listen 80;
    server_name _;   # or your domain

    root /home/ec2-user/MaheshwariInvestors/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API to FastAPI
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
    }
}
```

Then the frontend must call the API under `/api`. Your app uses paths like `/health`, `/metrics`. Two options:

- **A)** Build frontend with `VITE_API_BASE_URL=http://YOUR_PUBLIC_IP` and proxy the whole backend under `/` (e.g. `location /api/` → `http://127.0.0.1:8000/` and set `VITE_API_BASE_URL=http://YOUR_IP/api`), **or**
- **B)** Simpler: proxy by path prefix. Example: proxy `http://YOUR_IP/` to backend for `/health`, `/metrics`, `/investors`, etc. So:

```nginx
location / {
    # Try static first, then backend
    try_files $uri $uri/ @backend;
}
location @backend {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 180s;
}
```

That requires the SPA to be served from a different path (e.g. `/app`) or the backend to not use root paths. **Easier for now:** run backend on 8000 and frontend build with `VITE_API_BASE_URL=http://YOUR_PUBLIC_IP:8000`, and serve only the frontend with Nginx on 80:

```nginx
server {
    listen 80;
    server_name _;
    root /home/ec2-user/MaheshwariInvestors/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Then users open `http://YOUR_PUBLIC_IP` and the React app calls `http://YOUR_PUBLIC_IP:8000` (you opened port 8000 in the security group). For production you’d put a load balancer or CloudFront in front and use one hostname.

Reload Nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 5. Run backend permanently (systemd)

Create `/etc/systemd/system/maheshwari-api.service`:

```ini
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
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable maheshwari-api
sudo systemctl start maheshwari-api
sudo systemctl status maheshwari-api
```

### 6. Open the app

- **Frontend:** `http://YOUR_PUBLIC_IP` (Nginx on 80)
- **API:** `http://YOUR_PUBLIC_IP:8000` (used by the frontend if you set `VITE_API_BASE_URL` to that)

Log in with `maheshai` / `admin$123`.

### 7. (Optional) HTTPS and domain

- Point a domain (e.g. `investors.example.com`) to the EC2 public IP (A record).
- Install certbot and get a certificate: `sudo dnf install certbot python3-certbot-nginx -y` (or apt on Ubuntu), then `sudo certbot --nginx -d investors.example.com`.
- Update Nginx to listen on 443 and use the cert. Restrict security group to 80/443 and close 8000 from the internet if you proxy through Nginx.

---

## Option B: Frontend on S3 + CloudFront, Backend on EC2 or Elastic Beanstalk

- **Frontend:** Build React app, upload `frontend/dist` to an S3 bucket, enable static website hosting or use CloudFront with S3 origin.
- **Backend:** Deploy FastAPI on EC2 (as in Option A) or use **Elastic Beanstalk** (Python platform, single instance).

**Frontend (S3 + CloudFront):**

1. Build with the backend URL (your API domain):
   ```bash
   cd frontend
   export VITE_API_BASE_URL=https://api.yourdomain.com
   npm run build
   ```
2. Create S3 bucket, upload contents of `dist/`, set bucket policy for CloudFront (or public read if you don’t use CloudFront).
3. Create CloudFront distribution with origin = S3 (or the S3 website endpoint). Use default root object `index.html` and error pages redirect to `index.html` (for SPA).
4. Point your domain to the CloudFront distribution (CNAME or Route 53 alias).

**Backend (Elastic Beanstalk):**

1. Install EB CLI: `pip install awsebcli`
2. In `backend/`: `eb init -p python-3.11 maheshwari-api --region us-east-1`
3. Create Procfile: `web: uvicorn main:app --host 0.0.0.0 --port 8000`
4. Ensure `requirements.txt` is in `backend/`. Deploy: `eb create` (or `eb deploy`). Upload your CSV (e.g. via `.ebextensions` or after first deploy).
5. Set `VITE_API_BASE_URL` to the EB environment URL (e.g. `https://your-env.region.elasticbeanstalk.com`).

**CORS:** Backend already has `allow_origins=["*"]`. For production you can restrict to your CloudFront/frontend origin.

---

## Environment summary

| Where        | Variable             | Example / note                                      |
|-------------|----------------------|-----------------------------------------------------|
| Build time  | `VITE_API_BASE_URL`  | `http://YOUR_EC2_IP:8000` or `https://api.domain.com` |
| Backend     | CSV path             | Default: project root `DFWInvestors2026StockPicks.csv` or `data/investors.csv` |

---

## Security checklist

- Restrict SSH (security group) to your IP or a bastion.
- Prefer HTTPS (certbot or ALB/CloudFront) and redirect HTTP → HTTPS.
- Do not commit `.env` or `.pem` files; use secrets or IAM for production.
- Consider moving to a single origin (Nginx proxy) so the API is not exposed on a separate port.

---

## Docker (optional)

You can run the backend in a container and later deploy it to **ECS Fargate** or **App Runner**.

**Build and run (from repo root):**

```bash
# Ensure DFWInvestors2026StockPicks.csv exists in project root
docker build -f backend/Dockerfile -t maheshwari-api .
docker run -p 8000:8000 maheshwari-api
```

Then deploy the image to ECR and run it on ECS Fargate or AWS App Runner. The frontend can be built with `VITE_API_BASE_URL` set to the load balancer or App Runner URL.

---

## Quick reference (Option A)

```bash
# On EC2 after first-time setup
cd /home/ec2-user/MaheshwariInvestors
git pull   # or rsync from local

cd backend && source venv/bin/activate && pip install -r requirements.txt
sudo systemctl restart maheshwari-api

cd ../frontend && npm ci && npm run build   # set VITE_API_BASE_URL if needed
# Nginx already serves frontend/dist
```
