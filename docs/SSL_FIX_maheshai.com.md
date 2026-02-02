# Fix SSL Error on maheshai.com (ERR_SSL_VERSION_OR_CIPHER_MISMATCH)

Modern browsers (Chrome, Firefox, etc.) reject old TLS versions and weak ciphers. Your server is likely offering TLS 1.0/1.1 or outdated ciphers. Fix by allowing **only TLS 1.2 and 1.3** and **modern ciphers**.

---

## If you use **Nginx** on EC2 (most common)

### 1. SSH into the server

```bash
ssh -i your-key.pem ec2-user@your-ec2-ip
```

### 2. Find your SSL server block

Usually in `/etc/nginx/nginx.conf` or `/etc/nginx/conf.d/maheshai.conf` (or `sites-enabled` on Ubuntu). Look for a `server { ... }` block that has `listen 443 ssl;`.

### 3. Set protocols and ciphers

Inside the `server { }` block for port 443, add or update:

```nginx
listen 443 ssl http2;
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
```

**Full example** (replace paths and domain as needed):

```nginx
server {
    listen 443 ssl http2;
    server_name maheshai.com www.maheshai.com;

    # Only TLS 1.2 and 1.3 (required for modern browsers)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Certificates (Certbot usually sets these)
    ssl_certificate /etc/letsencrypt/live/maheshai.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/maheshai.com/privkey.pem;

    root /home/ec2-user/MaheshwariInvestors/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }

    # If API is on same server
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 4. Test and reload Nginx

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 5. If you don’t have HTTPS yet (only HTTP)

Get a free certificate with Certbot, then add the SSL block above:

```bash
sudo dnf install certbot python3-certbot-nginx -y   # Amazon Linux 2023
# or
sudo apt install certbot python3-certbot-nginx -y  # Ubuntu

sudo certbot --nginx -d maheshai.com -d www.maheshai.com
```

Certbot will configure HTTPS. Then add the `ssl_protocols` and `ssl_ciphers` lines above so only TLS 1.2/1.3 are used.

---

## If you use **CloudFront** in front of the site

- CloudFront already uses modern TLS; the error is usually from the **origin** (your EC2 or load balancer).
- If the origin is an EC2 with Nginx, apply the Nginx fix above.
- In CloudFront: **Behaviors** → your behavior → **Viewer Protocol Policy**: set to **Redirect HTTP to HTTPS**. **Origin Protocol Policy**: HTTPS only if your origin has a valid cert.

---

## If you use **Application Load Balancer (ALB)**

1. AWS Console → **EC2** → **Load Balancers** → select your ALB.
2. **Listeners** → HTTPS:443 → **Edit**.
3. **Security policy**: choose a modern policy, e.g. **ELBSecurityPolicy-TLS13-1-2-2021-06** (TLS 1.2 and 1.3).
4. Save.

---

## Quick checklist

- [ ] Nginx: `ssl_protocols TLSv1.2 TLSv1.3;` (no `TLSv1` or `SSLv3`)
- [ ] Nginx: `ssl_ciphers` set to a modern list (like above)
- [ ] Reload Nginx after changes
- [ ] Port 443 open in EC2 security group
- [ ] Cert is valid (e.g. Let’s Encrypt not expired)

After changing config and reloading, test in a private/incognito window: `https://maheshai.com`.
