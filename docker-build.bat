@echo off
REM YouTube Comment AI Agent - Docker Build & Push Script (Windows)
REM Author: Tiz Lion AI
REM Repository: https://hub.docker.com/r/tiz20lion/youbute-comment-ai-agent

setlocal enabledelayedexpansion

REM Configuration
set DOCKER_USERNAME=tiz20lion
set IMAGE_NAME=youbute-comment-ai-agent
set DOCKER_REPO=%DOCKER_USERNAME%/%IMAGE_NAME%

REM Get version from command line argument or use 'latest'
set VERSION=%1
if "%VERSION%"=="" set VERSION=latest

echo.
echo ================================
echo 🐳 YouTube Comment AI Agent
echo Docker Build ^& Push Script
echo ================================
echo Repository: %DOCKER_REPO%
echo Version: %VERSION%
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not running. Please start Docker and try again.
    pause
    exit /b 1
)

REM Check Docker Hub authentication
echo 🔐 Checking Docker Hub authentication...
docker info | find "Username" >nul
if errorlevel 1 (
    echo ⚠️  Not logged in to Docker Hub. Please login:
    docker login
    if errorlevel 1 (
        echo ❌ Docker login failed!
        pause
        exit /b 1
    )
)

REM Build the Docker image
echo.
echo 🔨 Building Docker image...
docker build -t %DOCKER_REPO%:%VERSION% -t %DOCKER_REPO%:latest .

if errorlevel 1 (
    echo ❌ Docker build failed!
    pause
    exit /b 1
) else (
    echo ✅ Docker image built successfully!
)

REM Show image information
echo.
echo 📊 Image information:
docker images %DOCKER_REPO%:%VERSION%

REM Ask for confirmation before pushing
echo.
set /p PUSH_CONFIRM="🚀 Push to Docker Hub? (y/N): "
if /i "%PUSH_CONFIRM%"=="y" (
    echo.
    echo 📤 Pushing to Docker Hub...
    
    REM Push version tag
    docker push %DOCKER_REPO%:%VERSION%
    if errorlevel 1 (
        echo ❌ Failed to push %VERSION% tag!
        pause
        exit /b 1
    )
    
    REM Push latest tag if version is not latest
    if not "%VERSION%"=="latest" (
        docker push %DOCKER_REPO%:latest
        if errorlevel 1 (
            echo ❌ Failed to push latest tag!
            pause
            exit /b 1
        )
    )
    
    echo.
    echo 🎉 Successfully pushed to Docker Hub!
    echo 🔗 Repository: https://hub.docker.com/r/%DOCKER_REPO%
    echo.
    echo 📋 To run the container:
    echo docker run -d -p 8080:8080 --name youtube-ai %DOCKER_REPO%:%VERSION%
    echo.
    echo 📋 Or use Docker Compose:
    echo docker-compose up -d
) else (
    echo ⏹️  Push cancelled.
)

echo.
echo ✨ Docker operations completed!
pause 