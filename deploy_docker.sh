#!/bin/bash
# Docker Deployment Script for GMS Certification Analyzer

set -e

echo "=========================================="
echo "GMS Certification Analyzer - Docker Setup"
echo "=========================================="

APP_DIR=~/gms-helper
mkdir -p $APP_DIR
cd $APP_DIR

# 1. Install Docker (One-click)
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "Please log out and log back in for group changes to take effect."
    echo "Or run: 'newgrp docker'"
fi

# 2. Check for Docker Compose
if ! docker compose version &> /dev/null; then
    echo "📦 Installing Docker Compose..."
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
fi

# 3. Create .env file
if [ ! -f .env ]; then
    echo "⚙️  Creating default .env file..."
    cat > .env << EOF
LLM_PROVIDER=internal
INTERNAL_LLM_URL=https://api.cambrian.pegatroncorp.com
INTERNAL_LLM_MODEL=LLAMA 3.3 70B
INTERNAL_LLM_API_KEY=
INTERNAL_LLM_VERIFY_SSL=0
EOF
    echo "⚠️  Created .env file. Please edit it to add your API Key!"
fi

# 4. Create docker-compose.yml
echo "📄 Creating docker-compose.yml..."
cat > docker-compose.yml << EOF
version: '3.8'

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
    env_file:
      - .env
    # Fix for OpenBLAS threading issue on some hosts
    security_opt:
      - seccomp:unconfined
    environment:
      - OPENBLAS_NUM_THREADS=1
      - DATABASE_URL=sqlite:////app/data/gms_analysis.db
    networks:
      - default
      - redmine-docker_default

networks:
  redmine-docker_default:
    external: true
EOF

# 5. Run it!
echo "🚀 Starting services..."
echo "Running: docker compose pull && docker compose up -d"
docker compose pull
docker compose up -d

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo "Access your app at: http://$(curl -s ifconfig.me):9000"
echo ""
echo "To view logs: docker compose logs -f"
echo "To update: docker compose pull && docker compose up -d"
