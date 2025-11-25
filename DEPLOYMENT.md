# Vultr VPS Deployment Guide

This guide will help you deploy the GMS Certification Analyzer to a Vultr VPS.

## Prerequisites

- A Vultr account
- SSH access to your VPS
- Your GitHub SSH key added to the VPS

## Quick Deployment

### 1. Create a Vultr VPS

1. Log in to [Vultr](https://my.vultr.com/)
2. Click "Deploy New Server"
3. Choose:
   - **Server Type**: Cloud Compute - Shared CPU
   - **Location**: Choose closest to you
   - **Server Image**: Ubuntu 22.04 LTS x64
   - **Server Size**: At least 2GB RAM (recommended: 4GB for better performance)
   - **SSH Keys**: Add your SSH key
4. Click "Deploy Now"

### 2. Connect to Your VPS

```bash
ssh root@YOUR_VPS_IP
```

### 3. Add GitHub SSH Key to VPS

```bash
# Generate SSH key on VPS
ssh-keygen -t ed25519 -C "your_email@example.com"

# Display the public key
cat ~/.ssh/id_ed25519.pub
```

Copy the output and add it to GitHub:
- Go to https://github.com/settings/ssh/new
- Paste the key and save

### 4. Run Deployment Script

```bash
# Download and run the deployment script
curl -o deploy.sh https://raw.githubusercontent.com/seen0722/GMS-helper/main/deploy_vultr.sh
chmod +x deploy.sh
./deploy.sh
```

The script will automatically:
- Install all dependencies (Python, Nginx, Supervisor)
- Clone your repository
- Set up the virtual environment
- Configure Nginx as reverse proxy
- Set up Supervisor for process management
- Configure firewall rules
- Start the application

### 5. Access Your Application

After deployment completes, access your application at:
```
http://YOUR_VPS_IP
```

## Manual Deployment (Alternative)

If you prefer to deploy manually, follow these steps:

### 1. Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install Dependencies
```bash
sudo apt install -y python3 python3-pip python3-venv nginx supervisor git
```

### 3. Clone Repository
```bash
sudo mkdir -p /var/www/gms-analyzer
sudo chown -R $USER:$USER /var/www/gms-analyzer
cd /var/www/gms-analyzer
git clone git@github.com:seen0722/GMS-helper.git .
```

### 4. Set Up Python Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Configure Supervisor
Create `/etc/supervisor/conf.d/gms-analyzer.conf`:
```ini
[program:gms-analyzer]
directory=/var/www/gms-analyzer
command=/var/www/gms-analyzer/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
user=YOUR_USERNAME
autostart=true
autorestart=true
stderr_logfile=/var/log/gms-analyzer.err.log
stdout_logfile=/var/log/gms-analyzer.out.log
```

### 6. Configure Nginx
Create `/etc/nginx/sites-available/gms-analyzer`:
```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;
    client_max_body_size 1000M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/gms-analyzer /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### 7. Start Services
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start gms-analyzer
```

## Post-Deployment Configuration

### Set Up SSL (Recommended for Production)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate (replace with your domain)
sudo certbot --nginx -d your-domain.com

# Auto-renewal is set up automatically
```

### Configure Application Settings

1. Access your application at `http://YOUR_VPS_IP`
2. Go to Settings
3. Configure:
   - OpenAI API key (for AI analysis)
   - Redmine URL and API key (if using Redmine integration)

## Maintenance

### Update Application
```bash
cd /var/www/gms-analyzer
git pull
sudo supervisorctl restart gms-analyzer
```

### View Logs
```bash
# Application logs
sudo tail -f /var/log/gms-analyzer.out.log

# Error logs
sudo tail -f /var/log/gms-analyzer.err.log

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Restart Services
```bash
# Restart application
sudo supervisorctl restart gms-analyzer

# Restart Nginx
sudo systemctl restart nginx
```

### Backup Database
```bash
# Create backup
cp /var/www/gms-analyzer/gms_analysis.db ~/gms_backup_$(date +%Y%m%d).db

# Download to local machine
scp root@YOUR_VPS_IP:~/gms_backup_*.db ./
```

## Troubleshooting

### Application Not Starting
```bash
# Check Supervisor status
sudo supervisorctl status

# Check logs
sudo tail -100 /var/log/gms-analyzer.err.log
```

### Nginx Issues
```bash
# Test configuration
sudo nginx -t

# Check status
sudo systemctl status nginx
```

### Port Already in Use
```bash
# Check what's using port 8000
sudo lsof -i :8000

# Kill the process if needed
sudo kill -9 PID
```

## Security Recommendations

1. **Change default SSH port** (optional but recommended)
2. **Set up fail2ban** to prevent brute force attacks
3. **Enable SSL/HTTPS** using Let's Encrypt
4. **Regular backups** of the database
5. **Keep system updated**: `sudo apt update && sudo apt upgrade`
6. **Use strong passwords** for all accounts
7. **Restrict SSH access** to specific IPs if possible

## Resource Requirements

- **Minimum**: 2GB RAM, 1 CPU, 25GB SSD
- **Recommended**: 4GB RAM, 2 CPU, 50GB SSD
- **For large test files**: 8GB RAM, 4 CPU, 100GB SSD

## Cost Estimate

Vultr pricing (as of 2024):
- **2GB RAM**: ~$12/month
- **4GB RAM**: ~$24/month
- **8GB RAM**: ~$48/month

Choose based on your expected usage and test file sizes.
