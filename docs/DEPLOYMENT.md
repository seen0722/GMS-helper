# GMS Certification Analyzer Deployment Guide

This guide covers how to deploy the GMS Certification Analyzer in various environments.

## 🐳 Primary Method: Docker Deployment (Recommended)

Docker is the easiest and most robust way to deploy the app. It handles all dependencies, environment setup, and the new **Auto-Bootstrapping** mechanism.

### 1. One-Click Setup (Ubuntu/Linux)

Run this command on your server to download and run the automated deployment script:

```bash
curl -o deploy_docker.sh https://raw.githubusercontent.com/seen0722/GMS-helper/main/deploy_docker.sh
chmod +x deploy_docker.sh
./deploy_docker.sh
```

**This script will:**
- Install Docker & Docker Compose (if missing)
- Pull the latest image (`seen0516/gms-helper:latest`)
- Setup persistence for `data/` and `uploads/`
- Configure a default `.env`
- **Automatically Initialize** all standard GMS test suites (CTS, VTS, GTS, etc.)

### 2. Manual Docker Compose

If you prefer manual control, use the following `docker-compose.yml`:

```yaml
services:
  gms-helper:
    image: seen0516/gms-helper:latest
    container_name: gms-helper
    restart: unless-stopped
    ports:
      - "9000:8000"
    volumes:
      - ./data:/app/data
      - ./uploads:/app/uploads
    environment:
      - DATABASE_URL=sqlite:////app/data/gms_analysis.db
```

---

## 🔒 Restricted Network Deployment

If you are deploying in an internal network with only **Docker Hub** and **GitHub** access:

👉 **See the [Internal Restricted Deployment Guide](INTERNAL_RESTRICTED_DEPLOYMENT.md)**

---

## 🛠️ Advanced: Manual "Bare Metal" Setup

For environments where Docker is not available, follow these legacy steps.

### 1. Prerequisites
- Python 3.10+
- Nginx (for reverse proxy)
- Supervisor (for process management)

### 2. Setup Procedure
1. Clone repo: `git clone https://github.com/seen0722/GMS-helper.git`
2. Create VENV: `python -m venv .venv && source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. **Important**: You must manually run migrations: `python migrate_db.py`
5. Start app: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`

---

## 🛡️ Maintenance

### Update Image
```bash
docker compose pull && docker compose up -d
```

### Check Logs
```bash
docker compose logs -f gms-helper
```
