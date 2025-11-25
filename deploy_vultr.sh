#!/bin/bash
# Vultr VPS Deployment Script for GMS Certification Analyzer
# This script sets up the application on a fresh Ubuntu/Debian VPS

set -e  # Exit on error

echo "=========================================="
echo "GMS Certification Analyzer - VPS Setup"
echo "=========================================="

# Update system packages
echo "📦 Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install Python 3.10+ and pip
echo "🐍 Installing Python..."
sudo apt install -y python3 python3-pip python3-venv

# Install Nginx
echo "🌐 Installing Nginx..."
sudo apt install -y nginx

# Install Supervisor (for process management)
echo "👷 Installing Supervisor..."
sudo apt install -y supervisor

# Install Git
echo "📚 Installing Git..."
sudo apt install -y git

# Create application directory
echo "📁 Setting up application directory..."
sudo mkdir -p /var/www/gms-analyzer
sudo chown -R $USER:$USER /var/www/gms-analyzer
cd /var/www/gms-analyzer

# Clone repository
echo "📥 Cloning repository..."
git clone git@github.com:seen0722/GMS-helper.git .

# Create virtual environment
echo "🔧 Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create uploads directory
echo "📂 Creating uploads directory..."
mkdir -p uploads

# Set up environment variables
echo "⚙️  Setting up environment variables..."
cat > .env << EOF
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_PATH=/var/www/gms-analyzer/gms_analysis.db
EOF

# Create Supervisor configuration
echo "👷 Configuring Supervisor..."
sudo tee /etc/supervisor/conf.d/gms-analyzer.conf > /dev/null << EOF
[program:gms-analyzer]
directory=/var/www/gms-analyzer
command=/var/www/gms-analyzer/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
user=$USER
autostart=true
autorestart=true
stderr_logfile=/var/log/gms-analyzer.err.log
stdout_logfile=/var/log/gms-analyzer.out.log
environment=PATH="/var/www/gms-analyzer/.venv/bin"
EOF

# Create Nginx configuration
echo "🌐 Configuring Nginx..."
sudo tee /etc/nginx/sites-available/gms-analyzer > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 1000M;  # Allow large XML file uploads

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support (if needed in future)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts for large file uploads
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
        proxy_read_timeout 600;
        send_timeout 600;
    }
}
EOF

# Enable Nginx site
echo "✅ Enabling Nginx site..."
sudo ln -sf /etc/nginx/sites-available/gms-analyzer /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
echo "🧪 Testing Nginx configuration..."
sudo nginx -t

# Reload services
echo "🔄 Starting services..."
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start gms-analyzer
sudo systemctl restart nginx

# Set up firewall
echo "🔥 Configuring firewall..."
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS (for future SSL)
sudo ufw --force enable

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "Your GMS Analyzer is now running at:"
echo "http://$(curl -s ifconfig.me)"
echo ""
echo "Useful commands:"
echo "  - Check status: sudo supervisorctl status gms-analyzer"
echo "  - View logs: sudo tail -f /var/log/gms-analyzer.out.log"
echo "  - Restart app: sudo supervisorctl restart gms-analyzer"
echo "  - Update code: cd /var/www/gms-analyzer && git pull && sudo supervisorctl restart gms-analyzer"
echo ""
echo "Next steps:"
echo "  1. Configure your OpenAI API key in the web interface"
echo "  2. Configure Redmine integration (if needed)"
echo "  3. Set up SSL certificate (recommended for production)"
echo ""
