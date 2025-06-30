# ====================================================================
#  Tiz Lion AI Agent - Docker Build & Push Script (PowerShell) 
# ====================================================================
# Builds and pushes Docker image to Docker Hub
# Repository: tiz20lion/youtube-comment-ai-agent
# Updated: 2025-06-30 - Fixed syntax errors and enhanced functionality
# ====================================================================

param(
    [string]$Version = "latest",
    [switch]$NoPush,
    [switch]$Help
)

# Configuration
$DOCKER_REPO = "tiz20lion/youtube-comment-ai-agent"
$DOCKER_HUB_URL = "https://hub.docker.com/r/$DOCKER_REPO"

# Function to display help
function Write-Help {
    Write-Host ""
    Write-Host " Docker Build & Push Script for Tiz Lion AI Agent" -ForegroundColor Green
    Write-Host ""
    Write-Host "USAGE:" -ForegroundColor Yellow
    Write-Host "  .\docker-build.ps1 [OPTIONS]" -ForegroundColor White
    Write-Host ""
    Write-Host "OPTIONS:" -ForegroundColor Yellow
    Write-Host "  -Version <string>    Docker image version (default: 'latest')" -ForegroundColor White
    Write-Host "  -NoPush              Build only, skip push to Docker Hub" -ForegroundColor White
    Write-Host "  -Help                Show this help message" -ForegroundColor White
    Write-Host ""
    Write-Host "EXAMPLES:" -ForegroundColor Yellow
    Write-Host "  .\docker-build.ps1                          # Build with 'latest' tag" -ForegroundColor Gray
    Write-Host "  .\docker-build.ps1 -Version 'v2.0.0'       # Build with 'v2.0.0' tag" -ForegroundColor Gray
    Write-Host "  .\docker-build.ps1 -Version 'v2.0.0' -NoPush # Build only, no push" -ForegroundColor Gray
    Write-Host ""
}

# Function to print header
function Write-Header {
    Write-Host ""
    Write-Host "" -ForegroundColor Cyan
    Write-Host "                                                                              " -ForegroundColor Cyan
    Write-Host "                     TIZ LION AI AGENT DOCKER BUILD                      " -ForegroundColor Cyan
    Write-Host "                                                                              " -ForegroundColor Cyan
    Write-Host "                       Building for Docker Hub                           " -ForegroundColor Cyan
    Write-Host "                     Updated: 2025-06-30 (Latest)                          " -ForegroundColor Cyan
    Write-Host "                                                                              " -ForegroundColor Cyan
    Write-Host "" -ForegroundColor Cyan
    Write-Host ""
}

# Function to check Docker status
function Test-DockerStatus {
    Write-Host " Checking Docker installation..." -ForegroundColor Yellow
    
    # Check if Docker command exists
    try {
        $dockerVersion = docker --version 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Docker not found"
        }
        Write-Host " Docker found: $dockerVersion" -ForegroundColor Green
    }
    catch {
        Write-Host " ERROR: Docker is not installed or not in PATH." -ForegroundColor Red
        Write-Host "   Please install Docker Desktop from: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
        exit 1
    }
    
    # Check if Docker daemon is running
    try {
        docker info | Out-Null 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Docker daemon not running"
        }
        Write-Host " Docker daemon is running" -ForegroundColor Green
    }
    catch {
        Write-Host " ERROR: Docker daemon is not running." -ForegroundColor Red
        Write-Host "   Please start Docker Desktop and try again." -ForegroundColor Yellow
        exit 1
    }
}

# Function to check Docker Hub login status
function Test-DockerLogin {
    Write-Host " Checking Docker Hub authentication..." -ForegroundColor Yellow
    
    try {
        $dockerInfo = docker info 2>$null
        if ($dockerInfo -match "Username:") {
            $username = ($dockerInfo | Select-String "Username:" | ForEach-Object { $_.Line.Split(":")[1].Trim() })
            Write-Host " Logged in to Docker Hub as: $username" -ForegroundColor Green
            return $true
        }
        else {
            Write-Host "  Not logged in to Docker Hub" -ForegroundColor Yellow
            return $false
        }
    }
    catch {
        Write-Host "  Could not determine Docker Hub login status" -ForegroundColor Yellow
        return $false
    }
}

# Function to build Docker image
function New-DockerImage {
    param([string]$ImageVersion)
    
    Write-Host "🔨 Building Docker image..." -ForegroundColor Yellow
    Write-Host "📝 Repository: $DOCKER_REPO" -ForegroundColor Blue
    Write-Host "🏷️  Version: $ImageVersion" -ForegroundColor Blue
    Write-Host "🚀 Startup: python -m uvicorn app.main:app --host 0.0.0.0 --port 7844" -ForegroundColor Blue
    Write-Host "🔧 Port: 7844" -ForegroundColor Blue
    Write-Host ""
    
    try {
        Write-Host "⏳ Building... (this may take a few minutes)" -ForegroundColor Yellow
        
        # Build with both version and latest tags
        docker build -t "${DOCKER_REPO}:${ImageVersion}" -t "${DOCKER_REPO}:latest" .
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Docker image built successfully!" -ForegroundColor Green
            Write-Host "🏷️  Tagged as: ${DOCKER_REPO}:${ImageVersion}" -ForegroundColor Blue
            Write-Host "🏷️  Tagged as: ${DOCKER_REPO}:latest" -ForegroundColor Blue
            return $true
        }
        else {
            throw "Docker build failed with exit code $LASTEXITCODE"
        }
    }
    catch {
        Write-Host "❌ ERROR: Docker build failed" -ForegroundColor Red
        Write-Host "   $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

# Function to push to Docker Hub
function Send-DockerImage {
    param([string]$ImageVersion)
    
    # Check if user wants to push
    if ($NoPush) {
        Write-Host "⏭️  Skipping push (NoPush flag specified)" -ForegroundColor Yellow
        Write-LocalImageInfo -ImageVersion $ImageVersion
        return
    }
    
    Write-Host ""
    $pushConfirm = Read-Host "📤 Push to Docker Hub? (y/N)"
    
    if ($pushConfirm -eq 'y' -or $pushConfirm -eq 'Y') {
        # Ensure user is logged in
        if (-not (Test-DockerLogin)) {
            Write-Host "🔐 Please log in to Docker Hub:" -ForegroundColor Yellow
            docker login
            if ($LASTEXITCODE -ne 0) {
                Write-Host "❌ ERROR: Docker login failed" -ForegroundColor Red
                exit 1
            }
        }
        
        Write-Host "📤 Pushing to Docker Hub..." -ForegroundColor Yellow
        
        try {
            # Push version tag
            Write-Host "   Pushing ${DOCKER_REPO}:${ImageVersion}..." -ForegroundColor Gray
            docker push "${DOCKER_REPO}:${ImageVersion}"
            if ($LASTEXITCODE -ne 0) { throw "Failed to push version tag" }
            
            # Push latest tag
            Write-Host "   Pushing ${DOCKER_REPO}:latest..." -ForegroundColor Gray
            docker push "${DOCKER_REPO}:latest"
            if ($LASTEXITCODE -ne 0) { throw "Failed to push latest tag" }
            
            Write-SuccessInfo -ImageVersion $ImageVersion
        }
        catch {
            Write-Host "❌ ERROR: Docker push failed" -ForegroundColor Red
            Write-Host "   $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "   Make sure you are logged in: docker login" -ForegroundColor Yellow
            exit 1
        }
    }
    else {
        Write-Host "⏭️  Skipping push to Docker Hub" -ForegroundColor Yellow
        Write-LocalImageInfo -ImageVersion $ImageVersion
    }
}

# Function to show success information
function Write-SuccessInfo {
    param([string]$ImageVersion)
    
    Write-Host ""
    Write-Host "🎉 SUCCESS! Docker image pushed to Docker Hub" -ForegroundColor Green
    Write-Host ""
    Write-Host "📦 DOCKER HUB INFORMATION:" -ForegroundColor Yellow
    Write-Host "🐳 Repository: $DOCKER_REPO" -ForegroundColor Blue
    Write-Host "🏷️  Tags: $ImageVersion, latest" -ForegroundColor Blue
    Write-Host "🌐 URL: $DOCKER_HUB_URL" -ForegroundColor Blue
    Write-Host ""
    Write-Host "🚀 USAGE COMMANDS:" -ForegroundColor Yellow
    Write-Host "   Pull image:" -ForegroundColor Gray
    Write-Host "     docker pull ${DOCKER_REPO}:${ImageVersion}" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   Run container:" -ForegroundColor Gray
    Write-Host "     docker run -p 7844:7844 --env-file .env ${DOCKER_REPO}:${ImageVersion}" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   Run with volume mount:" -ForegroundColor Gray
    Write-Host "     docker run -p 7844:7844 --env-file .env -v \"`$((Get-Location).Path)/data:/app/data\" ${DOCKER_REPO}:${ImageVersion}" -ForegroundColor Cyan
}

# Function to show local image information
function Write-LocalImageInfo {
    param([string]$ImageVersion)
    
    Write-Host ""
    Write-Host "🏠 LOCAL IMAGE INFORMATION:" -ForegroundColor Yellow
    Write-Host "🏷️  Local tags: ${DOCKER_REPO}:${ImageVersion}, ${DOCKER_REPO}:latest" -ForegroundColor Blue
    Write-Host ""
    Write-Host "🧪 TEST LOCALLY:" -ForegroundColor Yellow
    Write-Host "   docker run -p 7844:7844 --env-file .env ${DOCKER_REPO}:${ImageVersion}" -ForegroundColor Cyan
    Write-Host "   Then open: http://localhost:7844" -ForegroundColor Gray
}

# Main execution
function Main {
    # Show help if requested
    if ($Help) {
        Write-Help
        return
    }
    
    # Show header
    Write-Header
    
    # Validate Docker
    Test-DockerStatus
    
    # Build image
    New-DockerImage -ImageVersion $Version
    
    # Push image (with user confirmation)
    Send-DockerImage -ImageVersion $Version
    
    Write-Host ""
    Write-Host "✅ Operation completed successfully!" -ForegroundColor Green
    Write-Host ""
}

# Run main function
try {
    Main
}
catch {
    Write-Host ""
    Write-Host " FATAL ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
