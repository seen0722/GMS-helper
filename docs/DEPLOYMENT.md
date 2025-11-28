# Vultr + Cloudflare Deployment Guide

This comprehensive guide will help you deploy the GMS Certification Analyzer to a Vultr VPS using Cloudflare for DNS and security.

## 🏗️ Architecture Overview

- **Host**: Vultr VPS (Ubuntu 22.04 LTS)
- **DNS & Security**: Cloudflare
- **Web Server**: Nginx (Reverse Proxy)
- **App Server**: Uvicorn + FastAPI
- **Process Manager**: Supervisor
- **Database**: SQLite (Embedded)

---

## ✅ Prerequisites

1. **Vultr Account**: [Create account](https://www.vultr.com/)
2. **Cloudflare Account**: [Create account](https://dash.cloudflare.com/)
3. **Domain Name**: You need a domain (e.g., `zmlab.io`)
4. **GitHub Account**: To access the repository

---

## 🚀 Phase 1: Vultr VPS Setup

### 1. Deploy New Server
1. Log in to Vultr.
2. Click **Deploy New Server**.
3. Choose:
   - **Server Type**: Cloud Compute - Shared CPU
   - **Location**: Choose closest to you (e.g., Tokyo, Singapore)
   - **Server Image**: Ubuntu 22.04 LTS x64
   - **Server Size**: 
     - Minimum: 2GB RAM / 1 vCPU
     - **Recommended**: 4GB RAM / 2 vCPU (for better AI analysis performance)
4. **SSH Keys**: Click "Add New" if you don't have one.

### 2. Generate SSH Key (If needed)
If you need to generate a new SSH key on your local machine:

**Mac/Linux Terminal:**
```bash
# IMPORTANT: Use straight quotes ("), not curly quotes (“)
ssh-keygen -t ed25519 -C "your_email@example.com"
```
- Press Enter to save to default location.
- Press Enter for no passphrase (or set one if preferred).
- Copy the public key: `cat ~/.ssh/id_ed25519.pub`
- Paste this key into Vultr.

### 3. Deploy
Click **Deploy Now** and wait for the server to start. Copy the **IP Address**.

---

## ☁️ Phase 2: Cloudflare DNS Setup

### 1. Add Site to Cloudflare
1. Log in to Cloudflare.
2. Click **Add a Site**.
3. Enter your domain (e.g., `zmlab.io`).
4. Select the **Free** plan.
5. Update your domain registrar's nameservers to the ones Cloudflare provides.

### 2. Configure DNS Records
Go to **DNS** > **Records** and add an A record:

| Type | Name | Content (IPv4) | Proxy Status | Purpose |
|------|------|----------------|--------------|---------|
| A | `gms` | `YOUR_VPS_IP` | ⚪ **DNS Only** (Grey Cloud) | Main App |

> **⚠️ IMPORTANT:** Set Proxy Status to **DNS Only (Grey Cloud)** initially.
> This bypasses Cloudflare's 100MB upload limit, allowing you to upload large XML test files directly.
> You can enable Proxy (Orange Cloud) later if you set up a separate upload subdomain.

---

## 💻 Phase 3: Server Configuration

### 1. Connect to VPS
```bash
ssh root@YOUR_VPS_IP
```

### 2. Add GitHub Access
To clone the private repository, generate an SSH key on the VPS and add it to GitHub:

```bash
# Generate key on VPS
ssh-keygen -t ed25519 -C "vps-key"
# (Press Enter for all prompts)

# Show public key
cat ~/.ssh/id_ed25519.pub
```
1. Copy the output.
2. Go to GitHub > Settings > SSH and GPG keys > **New SSH key**.
3. Title: "Vultr VPS", Key: Paste the key.
4. Click **Add SSH key**.

### 3. Run Automated Deployment
We have a script that sets up everything (Python, Nginx, Supervisor, Firewall).

```bash
# Download deployment script
curl -o deploy.sh https://raw.githubusercontent.com/seen0722/GMS-helper/main/deploy_vultr.sh

# Make executable
chmod +x deploy.sh

# Run it
./deploy.sh
```

The script will:
- Install Python 3.10+, Nginx, Supervisor, Git
- Clone the repository to `/var/www/gms-analyzer`
- Create a virtual environment and install dependencies
- Configure Nginx to listen on port 80
- Start the application

### 4. Manual Supervisor Configuration (If needed)
If the automated script fails or you need to configure Supervisor manually, create the configuration file:

```bash
sudo vim /etc/supervisor/conf.d/gms-analyzer.conf
```

**Configuration Content:**
```ini
[program:gms-analyzer]
directory=/var/www/gms-analyzer
command=/var/www/gms-analyzer/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
user=root
autostart=true
autorestart=true
stderr_logfile=/var/log/gms-analyzer.err.log
stdout_logfile=/var/log/gms-analyzer.out.log
```

**Apply Changes:**
```bash
sudo supervisorctl reread
sudo supervisorctl update


### 5. Manual Nginx Configuration (If needed)
If you need to manually enable the Nginx site:

```bash
# Enable Nginx site
echo "✅ Enabling Nginx site..."
sudo ln -sf /etc/nginx/sites-available/gms-analyzer /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test and restart Nginx
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🔒 Phase 4: SSL & Domain Configuration

Now that the app is running on IP, let's switch to your domain with SSL.

### 1. Install Certbot (SSL Tool)
```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 2. Update Nginx for Domain
Edit the Nginx config:
```bash
sudo vim /etc/nginx/sites-available/gms-analyzer
```

Find `server_name _;` and change it to your domain (e.g., `gms.zmlab.io`):
```nginx
server {
    listen 80;
    server_name gms.zmlab.io;  # <--- Update this
    
    # ... rest of config ...
}
```
Save: `Ctrl+O`, `Enter`, `Ctrl+X`.

### 3. Generate SSL Certificate
```bash
sudo certbot --nginx -d gms.zmlab.io
```
- Enter your email.
- Agree to terms (Y).
- Select **2** to Redirect HTTP to HTTPS.

### 4. Verify Nginx Configuration
After Certbot finishes, your Nginx configuration should automatically update. You can verify it matches the following secure configuration:

```bash
sudo vim /etc/nginx/sites-available/gms-analyzer
```

**Final Configuration Reference:**
```nginx
server {
    listen 80;
    server_name gms.zmlab.io;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name gms.zmlab.io;
    client_max_body_size 1000M;

    ssl_certificate /etc/letsencrypt/live/gms.zmlab.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gms.zmlab.io/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 5. Verify Access
Open `https://gms.zmlab.io` in your browser. You should see the GMS Analyzer!

---

## ⚙️ Phase 5: Application Setup

### 1. Configure API Keys
1. Go to **Settings** in the web interface.
2. Enter your **OpenAI API Key** (required for AI analysis).
3. (Optional) Enter Redmine URL and API Key.

### 2. Test Large File Upload
1. Upload a large XML file (>100MB).
2. Since we used **DNS Only** (Grey Cloud) in Cloudflare, it should work perfectly.

---

## 🛠️ Maintenance & Troubleshooting

### Update Code
To update the app with the latest code from GitHub:
```bash
cd /var/www/gms-analyzer
git pull
sudo supervisorctl restart gms-analyzer
```

### View Logs
```bash
# App logs
tail -f /var/log/gms-analyzer.out.log

# Error logs
tail -f /var/log/gms-analyzer.err.log
```

### Restart Services
```bash
sudo supervisorctl restart gms-analyzer
sudo systemctl restart nginx
```

### "Database Locked" Error
If you see database errors, ensure only one process is accessing it. Supervisor handles this, but if you run manual scripts, be careful.

### SSH Key Issues
If `ssh-keygen` fails with "Too many arguments" or similar:
- Check your quotes! Use `"` (straight), not `“` (curly).
- Type the command manually instead of pasting.

---

## 🛡️ Security Best Practices

1. **Firewall (UFW)**: The deployment script enables UFW allowing ports 22, 80, 443.
2. **Fail2Ban**: Recommended to prevent brute-force SSH attacks.
   ```bash
   sudo apt install -y fail2ban
   sudo systemctl enable fail2ban
   sudo systemctl start fail2ban
   ```
3. **Backups**: Regularly backup `gms_analysis.db`.
   ```bash
   # Copy to local machine
   scp root@YOUR_IP:/var/www/gms-analyzer/gms_analysis.db ./backup.db
   ```
