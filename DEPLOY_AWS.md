# Deploying Maheshwari Investors to AWS

This guide covers two deployment options. **Option A (single EC2)** is the simplest and keeps backend and frontend on one server. **Option B** uses S3 + CloudFront for the frontend and EC2 or Elastic Beanstalk for the API.

---

## Automated deploy (configure once, redeploy easily)

To avoid repeating manual steps when you set up a new instance or redeploy:

| Goal | What to use |
|------|-------------|
| **Security group** (22, 80, 443, 8000) in one go | CloudFormation: `deploy/cloudformation-security-group.yaml` |
| **Bootstrap a fresh EC2** (packages, Nginx, systemd) | Run once on the instance: `deploy/ec2-bootstrap.sh` |
| **Redeploy frontend** (build + upload + restart) | `deploy/deploy.ps1` (PowerShell) or `deploy/deploy.sh` (Bash) |

**One-time setup**

1. **Security group:** Create the group and attach it to your instance:
   ```bash
   # Get your default VPC ID
   aws ec2 describe-vpcs --query "Vpcs[?IsDefault].VpcId" --output text
   # Deploy stack (replace vpc-xxxxx)
   aws cloudformation deploy --template-file deploy/cloudformation-security-group.yaml \
     --stack-name maheshwari-sg --parameter-overrides VpcId=vpc-xxxxx
   ```
   Then in EC2 Console → your instance → Security → Change security group → add the created group (e.g. `maheshwari-investors-sg`).

2. **Bootstrap EC2 (new instance only):** Copy `deploy/ec2-bootstrap.sh` to the instance and run it once. Then clone the repo, set up backend venv + frontend build, and start the API + Nginx (see script output).

**Redeploy (frontend or full app)**

1. Copy `deploy/config.example` to `deploy/config` and set `EC2_IP` and `KEY_PATH` (and `EC2_USER` if not `ec2-user`).
2. From the **repo root**:
   - **PowerShell:** `.\deploy\deploy.ps1` (frontend only) or `.\deploy\deploy.ps1 -BackendToo` (frontend + backend + data).
   - **Bash/WSL:** `./deploy/deploy.sh` or `./deploy/deploy.sh --backend-too`.

The script builds the frontend with `VITE_API_BASE_URL=http://YOUR_EC2_IP:8000`, uploads `frontend/dist` to the server, and reloads Nginx. **Backend is restarted only when using `-BackendToo` / `--backend-too`**, so a frontend-only deploy does not clear the in-memory cache and avoids 503s and 2–3 minute cache warming.

---

## Deploy frontend when backend is already on EC2 (port 8000)

If the backend is already running on an EC2 instance at port 8000, use one of these:

### Option 1: Same EC2 – Nginx serves frontend on port 80

1. **On your EC2 instance**, install Nginx and Node (if not already):
   ```bash
   # Amazon Linux 2023
   sudo dnf install -y nginx nodejs npm
   # Ubuntu
   sudo apt update && sudo apt install -y nginx nodejs npm
   ```

2. **Get your app on the server** (clone or upload):
   ```bash
   cd /home/ec2-user
   git clone https://github.com/YOUR_ORG/MaheshwariInvestors.git
   cd MaheshwariInvestors
   ```

3. **Build the frontend** with the API URL set to this server (replace `YOUR_EC2_PUBLIC_IP` with your instance’s public IP or domain):
   ```bash
   cd /home/ec2-user/MaheshwariInvestors/frontend
   npm ci
   export VITE_API_BASE_URL=http://YOUR_EC2_PUBLIC_IP:8000
   npm run build
   ```
   If users will use a domain (e.g. `https://stocks.example.com`), use that instead:  
   `export VITE_API_BASE_URL=https://stocks.example.com:8000` or your API domain.

4. **Configure Nginx** to serve the built app (e.g. create `/etc/nginx/conf.d/maheshwari.conf` on Amazon Linux, or a file in `/etc/nginx/sites-available/` on Ubuntu):
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

5. **Reload Nginx:**
   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```

6. **Security group:** Ensure the instance allows **HTTP (80)** from `0.0.0.0/0` (or your allowed IPs) so users can open the site. **Also allow Custom TCP port 8000** from `0.0.0.0/0` (or your IPs) so the browser can reach the API at `http://YOUR_EC2_PUBLIC_IP:8000`.

7. **Open the app:** `http://YOUR_EC2_PUBLIC_IP` — the React app will call `http://YOUR_EC2_PUBLIC_IP:8000` for the API.

**If you see "API Connection Error" or "Backend did not respond in time":**
- **Port 8000:** In AWS Console → EC2 → Security Groups → your instance’s group, add **Inbound rule**: Type = Custom TCP, Port = 8000, Source = 0.0.0.0/0 (or your IP).
- **Backend running:** On EC2 run `curl http://127.0.0.1:8000/health`; if it fails, start the backend (see §5) with `uvicorn main:app --host 0.0.0.0 --port 8000`.
- **Listen on all interfaces:** Backend must use `--host 0.0.0.0` so it accepts connections from the browser (not just `127.0.0.1`).

### Option 2: Build locally, upload only `dist/`

1. **On your Windows machine** (in the project):
   ```powershell
   cd frontend
   $env:VITE_API_BASE_URL="http://YOUR_EC2_PUBLIC_IP:8000"
   npm run build
   ```

2. **Upload the built folder** to EC2 (from PowerShell, using your `.pem` and EC2 IP):
   ```powershell
   scp -i your-key.pem -r dist ec2-user@YOUR_EC2_PUBLIC_IP:/home/ec2-user/MaheshwariInvestors/frontend/
   ```

3. **On EC2:** Install and configure Nginx as in Option 1 (steps 1, 4, 5). Point `root` to `/home/ec2-user/MaheshwariInvestors/frontend/dist`.

### Option 3: Frontend on S3 + CloudFront (backend stays on EC2)

1. **Build** with the backend URL (your EC2 API or a domain pointing to it):
   ```bash
   cd frontend
   export VITE_API_BASE_URL=http://YOUR_EC2_PUBLIC_IP:8000
   npm run build
   ```

2. **Create an S3 bucket** (e.g. `mai-frontend-yourname`), enable static website hosting (optional if using CloudFront).

3. **Upload** the contents of `frontend/dist/` to the bucket (all files in `dist/`, not the `dist` folder itself).

4. **Create a CloudFront distribution:** Origin = your S3 bucket (or S3 website endpoint). Default root object = `index.html`. Add a custom error response: HTTP 403 and 404 → return `200` with `/index.html` (for SPA routing).

5. **CORS:** Backend already allows `*`. If the frontend and API are on different origins, keep that or restrict to your CloudFront domain.

6. **Open the app** via the CloudFront URL (e.g. `https://d1234abcd.cloudfront.net`). The app will call `http://YOUR_EC2_PUBLIC_IP:8000`; for production, put the API behind a domain or same CloudFront with path routing.

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

If you start the backend manually in an SSH session (`uvicorn main:app ...`), it will stop when you close the SSH window. Use a **systemd service** so the backend keeps running after you disconnect and restarts on reboot.

#### Create the service file

**Option A – One command (copy-paste on EC2):**

```bash
sudo tee /etc/systemd/system/maheshwari-api.service << 'EOF'
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
EOF
```

**Option B – Create with an editor:**

```bash
sudo nano /etc/systemd/system/maheshwari-api.service
```

Paste the same `[Unit]` / `[Service]` / `[Install]` contents as above, then save (Ctrl+O, Enter) and exit (Ctrl+X).

If your repo lives somewhere other than `/home/ec2-user/MaheshwariInvestors/backend`, edit `WorkingDirectory`, `Environment`, and `ExecStart` to use that path.

#### Enable and start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable maheshwari-api
sudo systemctl start maheshwari-api
sudo systemctl status maheshwari-api
```

**Useful commands:**

| Action   | Command |
|----------|--------|
| Start    | `sudo systemctl start maheshwari-api` |
| Stop     | `sudo systemctl stop maheshwari-api` |
| Restart  | `sudo systemctl restart maheshwari-api` |
| Logs     | `journalctl -u maheshwari-api -f` |

**Backend resilience (overnight / Yahoo throttling):** The app is built to avoid crashes from yfinance timeouts or throttling:

- Each Yahoo fetch runs with a **30s timeout**; the refresh loop never blocks indefinitely.
- The cache is **merged** on refresh (successful fetches only); failed or timed-out symbols keep their previous cached data, so the app keeps serving.
- Exceptions in the background refresh are logged and the loop continues; uvicorn is not taken down.
- To monitor: `journalctl -u maheshwari-api -f` and look for `[Cache refresh]` (success/fail counts, timeouts) and `[yfinance]` (per-symbol errors).

### 6. Open the app

- **Frontend:** `http://YOUR_PUBLIC_IP` (Nginx on 80)
- **API:** `http://YOUR_PUBLIC_IP:8000` (used by the frontend if you set `VITE_API_BASE_URL` to that)

Log in with `maheshai` / `admin$123`.

### 6a. Troubleshooting: "Frontend not connecting to backend" (backend is running)

If `sudo systemctl status maheshwari-api` shows **active (running)** but the site still shows "API Connection Error", the frontend is calling `https://maheshai.com/api` and that request must go through **Nginx** to the backend. If Nginx is not running, the API calls never reach the backend.

**1. Check and start Nginx (on EC2):**

```bash
sudo systemctl status nginx
```

If it says **inactive** or **failed**:

```bash
sudo systemctl enable nginx
sudo systemctl start nginx
sudo systemctl status nginx
```

**2. Ensure Nginx starts on boot** (so it survives reboot and terminal close):

```bash
sudo systemctl enable nginx
```

**3. Verify the API is reachable through Nginx (on EC2):**

```bash
# Backend directly (should work if maheshwari-api is running)
curl -s http://127.0.0.1:8000/health

# Through Nginx (must work for the site to work)
curl -s http://127.0.0.1/api/health
```

If the first succeeds but the second fails, Nginx is not proxying `/api/` correctly. Check that you have a `location /api/ { proxy_pass http://127.0.0.1:8000/; ... }` block in your Nginx config (e.g. `/etc/nginx/conf.d/maheshai.conf` or `sites-enabled`). See §4 above for the config snippet.

**4. Reload Nginx after any config change:**

```bash
sudo nginx -t && sudo systemctl reload nginx
```

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

## SMS alert when backend stops responding

To get a text to your phone when the API goes down (e.g. after closing SSH or an overnight crash), see **[docs/SMS_ALERT_BACKEND_DOWN.md](docs/SMS_ALERT_BACKEND_DOWN.md)**. It covers:

- **Option 1:** AWS SNS + Lambda (scheduled health check every 5 min; sends SMS on failure).
- **Option 2:** Free external uptime monitors (e.g. UptimeRobot) with email/SMS.

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
