#!/bin/bash

# Docker build script for YouTube Comment AI Agent
# Author: Tiz Lion AI
# Description: Builds Docker image with automatic encoding fixes

set -e  # Exit on any error

echo "🐳 Building YouTube Comment AI Agent Docker Image"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="tiz20lion/youbute-comment-ai-agent"
TAG="latest"
DOCKERFILE="Dockerfile"

# Check if Dockerfile exists
if [ ! -f "$DOCKERFILE" ]; then
    echo -e "${RED}❌ Error: $DOCKERFILE not found!${NC}"
    exit 1
fi

# Check if docker-entrypoint.sh exists
if [ ! -f "docker-entrypoint.sh" ]; then
    echo -e "${RED}❌ Error: docker-entrypoint.sh not found!${NC}"
    exit 1
fi

# Check if fix_encoding.sh exists
if [ ! -f "fix_encoding.sh" ]; then
    echo -e "${RED}❌ Error: fix_encoding.sh not found!${NC}"
    exit 1
fi

echo -e "${BLUE}📋 Build Configuration:${NC}"
echo "   Image Name: $IMAGE_NAME"
echo "   Tag: $TAG"
echo "   Dockerfile: $DOCKERFILE"
echo "   Context: $(pwd)"
echo ""

echo -e "${YELLOW}🔧 Features in this build:${NC}"
echo "   ✅ Automatic encoding fix for docker-entrypoint.sh"
echo "   ✅ Cross-platform line ending compatibility"
echo "   ✅ UTF-8 BOM removal"
echo "   ✅ Proper script permissions"
echo ""

# Start build
echo -e "${GREEN}🚀 Starting Docker build...${NC}"
echo ""

# Build with progress output
docker build \
    --tag "$IMAGE_NAME:$TAG" \
    --file "$DOCKERFILE" \
    --progress=plain \
    . || {
    echo -e "${RED}❌ Docker build failed!${NC}"
    exit 1
}

echo ""
echo -e "${GREEN}✅ Docker build completed successfully!${NC}"
echo ""

# Display image info
echo -e "${BLUE}📊 Image Information:${NC}"
docker images "$IMAGE_NAME:$TAG" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

echo ""
echo -e "${GREEN}🎉 Build Complete!${NC}"
echo ""
echo -e "${YELLOW}🚀 To run the container:${NC}"
echo "   docker run -it --rm -p 8080:8080 --env-file .env $IMAGE_NAME:$TAG"
echo ""
echo -e "${YELLOW}🐳 To push to Docker Hub:${NC}"
echo "   docker push $IMAGE_NAME:$TAG"
echo ""
echo -e "${BLUE}📋 The build automatically fixed encoding issues in docker-entrypoint.sh${NC}"
echo -e "${GREEN}   Your container is ready to run on any platform! 🌍${NC}" 