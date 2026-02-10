#!/bin/bash
# Build and push GMS-helper to Docker Hub

# Set variables
IMAGE_NAME="seen0516/gms-helper"
VERSION=$(date +%Y%m%d-%H%M)

echo "🚀 Building and Pushing to Docker Hub..."
echo "Image: $IMAGE_NAME"
echo "Version: $VERSION"

# Ensure docker buildx is available (for multi-arch builds)
if ! docker buildx version > /dev/null 2>&1; then
    echo "❌ Docker Buildx not found! Please enable it in Docker Desktop settings."
    exit 1
fi

# Create builder instance if not exists
docker buildx create --use --name mybuilder || true

# Build and Push
# Target both amd64 (VPS) and arm64 (Mac)
echo "📦 Building for linux/amd64 and linux/arm64..."
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --no-cache \
  -t $IMAGE_NAME:latest \
  -t $IMAGE_NAME:$VERSION \
  --push .

echo "✅ Successfully pushed to Docker Hub!"
echo "Tags:"
echo "  - $IMAGE_NAME:latest"
echo "  - $IMAGE_NAME:$VERSION"
