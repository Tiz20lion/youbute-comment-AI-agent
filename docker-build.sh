#!/bin/bash
# ====================================================================
#  Tiz Lion AI Agent - Docker Build & Push Script (Bash) 
# ====================================================================
# Builds and pushes Docker image to Docker Hub
# Repository: tiz20lion/youtube-comment-ai-agent
# Updated: 2025-06-30 - Enhanced with security and multi-platform support
# ====================================================================

set -e  # Exit on any error

# Configuration
DOCKER_REPO="tiz20lion/youtube-comment-ai-agent"
DOCKER_HUB_URL="https://hub.docker.com/r/$DOCKER_REPO"
VERSION="${1:-latest}"
NO_PUSH="$2"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# Function to display help
show_help() {
    echo ""
    echo -e "${GREEN} Docker Build & Push Script for Tiz Lion AI Agent${NC}"
    echo ""
    echo -e "${YELLOW}USAGE:${NC}"
    echo -e "  ${NC}./docker-build.sh [VERSION] [--no-push]${NC}"
    echo ""
    echo -e "${YELLOW}ARGUMENTS:${NC}"
    echo -e "  ${NC}VERSION      Docker image version (default: 'latest')${NC}"
    echo -e "  ${NC}--no-push    Build only, skip push to Docker Hub${NC}"
    echo ""
    echo -e "${YELLOW}EXAMPLES:${NC}"
    echo -e "  ${GRAY}./docker-build.sh                    # Build with 'latest' tag${NC}"
    echo -e "  ${GRAY}./docker-build.sh v2.0.0             # Build with 'v2.0.0' tag${NC}"
    echo -e "  ${GRAY}./docker-build.sh v2.0.0 --no-push   # Build only, no push${NC}"
    echo ""
}

# Function to print header
show_header() {
    echo ""
    echo -e "${CYAN}${NC}"
    echo -e "${CYAN}                                                                              ${NC}"
    echo -e "${CYAN}                     TIZ LION AI AGENT DOCKER BUILD                      ${NC}"
    echo -e "${CYAN}                                                                              ${NC}"
    echo -e "${CYAN}                       Building for Docker Hub                           ${NC}"
    echo -e "${CYAN}                     Updated: 2025-06-30 (Latest)                          ${NC}"
    echo -e "${CYAN}                                                                              ${NC}"
    echo -e "${CYAN}${NC}"
    echo ""
}

# Function to check Docker status
check_docker() {
    echo -e "${YELLOW} Checking Docker installation...${NC}"
    
    # Check if Docker command exists
    if ! command -v docker &> /dev/null; then
        echo -e "${RED} ERROR: Docker is not installed or not in PATH.${NC}"
        echo -e "${YELLOW}   Please install Docker from: https://docs.docker.com/get-docker/${NC}"
        exit 1
    fi
    
    echo -e "${GREEN} Docker found: $(docker --version)${NC}"
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        echo -e "${RED} ERROR: Docker daemon is not running.${NC}"
        echo -e "${YELLOW}   Please start Docker and try again.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN} Docker daemon is running${NC}"
}

# Function to check Docker Hub login status
check_docker_login() {
    echo -e "${YELLOW} Checking Docker Hub authentication...${NC}"
    
    if docker info 2>/dev/null | grep -q "Username:"; then
        username=$(docker info 2>/dev/null | grep "Username:" | awk '{print $2}')
        echo -e "${GREEN} Logged in to Docker Hub as: $username${NC}"
        return 0
    else
        echo -e "${YELLOW}  Not logged in to Docker Hub${NC}"
        return 1
    fi
}

# Function to build Docker image
build_image() {
    local version="$1"
    
    echo -e "${YELLOW} Building Docker image...${NC}"
    echo -e "${BLUE} Repository: $DOCKER_REPO${NC}"
    echo -e "${BLUE}  Version: $version${NC}"
    echo -e "${BLUE} Startup: python -m uvicorn app.main:app --host 0.0.0.0 --port 7844${NC}"
    echo -e "${BLUE} Port: 7844${NC}"
    echo ""
    
    echo -e "${YELLOW} Building... (this may take a few minutes)${NC}"
    
    # Build with both version and latest tags
    if docker build -t "${DOCKER_REPO}:${version}" -t "${DOCKER_REPO}:latest" .; then
        echo -e "${GREEN} Docker image built successfully!${NC}"
        echo -e "${BLUE}  Tagged as: ${DOCKER_REPO}:${version}${NC}"
        echo -e "${BLUE}  Tagged as: ${DOCKER_REPO}:latest${NC}"
    else
        echo -e "${RED} ERROR: Docker build failed${NC}"
        exit 1
    fi
}

# Function to push to Docker Hub
push_image() {
    local version="$1"
    
    # Check if user wants to push
    if [[ "$NO_PUSH" == "--no-push" ]]; then
        echo -e "${YELLOW}  Skipping push (--no-push flag specified)${NC}"
        show_local_info "$version"
        return
    fi
    
    echo ""
    read -p " Push to Docker Hub? (y/N): " push_confirm
    
    if [[ "$push_confirm" =~ ^[Yy]$ ]]; then
        # Ensure user is logged in
        if ! check_docker_login; then
            echo -e "${YELLOW} Please log in to Docker Hub:${NC}"
            docker login
        fi
        
        echo -e "${YELLOW} Pushing to Docker Hub...${NC}"
        
        # Push version tag
        echo -e "${GRAY}   Pushing ${DOCKER_REPO}:${version}...${NC}"
        docker push "${DOCKER_REPO}:${version}"
        
        # Push latest tag
        echo -e "${GRAY}   Pushing ${DOCKER_REPO}:latest...${NC}"
        docker push "${DOCKER_REPO}:latest"
        
        show_success_info "$version"
    else
        echo -e "${YELLOW}  Skipping push to Docker Hub${NC}"
        show_local_info "$version"
    fi
}

# Function to show success information
show_success_info() {
    local version="$1"
    
    echo ""
    echo -e "${GREEN} SUCCESS! Docker image pushed to Docker Hub${NC}"
    echo ""
    echo -e "${YELLOW} DOCKER HUB INFORMATION:${NC}"
    echo -e "${BLUE} Repository: $DOCKER_REPO${NC}"
    echo -e "${BLUE}  Tags: $version, latest${NC}"
    echo -e "${BLUE} URL: $DOCKER_HUB_URL${NC}"
    echo ""
    echo -e "${YELLOW} USAGE COMMANDS:${NC}"
    echo -e "${GRAY}   Pull image:${NC}"
    echo -e "${CYAN}     docker pull ${DOCKER_REPO}:${version}${NC}"
    echo ""
    echo -e "${GRAY}   Run container:${NC}"
    echo -e "${CYAN}     docker run -p 7844:7844 --env-file .env ${DOCKER_REPO}:${version}${NC}"
    echo ""
    echo -e "${GRAY}   Run with volume mount:${NC}"
    echo -e "${CYAN}     docker run -p 7844:7844 --env-file .env -v \"$(pwd)/data:/app/data\" ${DOCKER_REPO}:${version}${NC}"
}

# Function to show local image information
show_local_info() {
    local version="$1"
    
    echo ""
    echo -e "${YELLOW} LOCAL IMAGE INFORMATION:${NC}"
    echo -e "${BLUE}  Local tags: ${DOCKER_REPO}:${version}, ${DOCKER_REPO}:latest${NC}"
    echo ""
    echo -e "${YELLOW} TEST LOCALLY:${NC}"
    echo -e "${CYAN}   docker run -p 7844:7844 --env-file .env ${DOCKER_REPO}:${version}${NC}"
    echo -e "${GRAY}   Then open: http://localhost:7844${NC}"
}

# Main function
main() {
    # Show help if requested
    if [[ "$1" == "--help" || "$1" == "-h" ]]; then
        show_help
        exit 0
    fi
    
    # Show header
    show_header
    
    # Check Docker
    check_docker
    
    # Build image
    build_image "$VERSION"
    
    # Push image (with user confirmation)
    push_image "$VERSION"
    
    echo ""
    echo -e "${GREEN} Operation completed successfully!${NC}"
    echo ""
}

# Run main function
main "$@"
