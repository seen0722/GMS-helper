# Internal Restricted Network Deployment Guide

This guide is specifically for deploying GMS-helper in internal environments with limited internet access (only **Docker Hub** and **GitHub** allowed).

## 🚀 Tomorrow's Action Plan

### 1. Pre-requisites
Ensure the target server has **Docker** and **Docker Compose** installed.
- Check: `docker --version`
- Check: `docker compose version` (or `docker-compose --version`)

> [!IMPORTANT]
> Since general `apt-get` or `get.docker.com` might be blocked, ensure these are ready before proceeding or use your internal software mirror.

### 2. One-Click Deployment
On the target server, run the following command to download and execute the setup script directly from GitHub:

```bash
# Download the deployment script
curl -o deploy_docker.sh https://raw.githubusercontent.com/seen0722/GMS-helper/main/deploy_docker.sh

# Make it executable
chmod +x deploy_docker.sh

# Run the deployment
# This will pull the latest image from Docker Hub and start the app
./deploy_docker.sh
```

### 3. Verification of "Auto-Bootstrapping"
You **do not need to seed any data manually**. 
The app is designed to initialize itself on the first run.

1.  Access the UI: `http://<SERVER_IP>:9000`
2.  Log in (if prompted).
3.  Go to **Dashboard**.
4.  Even with no uploads, the system backend has already automatically created the standard GMS Suite configurations (CTS, VTS, GTS, etc.) in the database.

### 4. Customizing Environment
If you need to change the LLM Provider or API keys, edit the `.env` file created in `~/gms-helper/.env`:

```bash
nano ~/gms-helper/.env
# After editing, restart:
cd ~/gms-helper && docker compose up -d
```

## 🛠️ Offline Considerations
- **Image Persistence**: If you need to move the app to a *totally* offline machine, use `docker save` on a connected machine and `docker load` on the target.
- **Database**: The database is located at `~/gms-helper/data/gms_analysis.db`. You can back this file up easily.
