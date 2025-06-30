@echo off
REM ====================================================================
REM  Tiz Lion AI Agent - Docker Build & Push Script (Windows Batch) 
REM ====================================================================
REM Builds and pushes Docker image to Docker Hub
REM Repository: tiz20lion/youtube-comment-ai-agent
REM Updated: 2025-06-30 - Enhanced Windows batch script
REM ====================================================================

setlocal enabledelayedexpansion

REM Configuration
set DOCKER_REPO=tiz20lion/youtube-comment-ai-agent
set DOCKER_HUB_URL=https://hub.docker.com/r/%DOCKER_REPO%
set VERSION=%1
if "%VERSION%"=="" set VERSION=latest

REM Print header
echo.
echo ================================================================================
echo                     TIZ LION AI AGENT DOCKER BUILD 
echo                            Building for Docker Hub 
echo                         Updated: 2025-06-30 (Latest)
echo ================================================================================
echo.

REM Check if Docker is installed
echo  Checking Docker installation...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Docker is not installed or not in PATH.
    echo    Please install Docker Desktop from: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
echo  Docker found and working

REM Check if Docker daemon is running
echo  Checking Docker daemon...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Docker daemon is not running.
    echo    Please start Docker Desktop and try again.
    pause
    exit /b 1
)
echo  Docker daemon is running

REM Build Docker image
echo.
echo  Building Docker image...
echo  Repository: %DOCKER_REPO%
echo   Version: %VERSION%
echo  Startup: python -m uvicorn app.main:app --host 0.0.0.0 --port 7844
echo  Port: 7844
echo.
echo  Building... (this may take a few minutes)

docker build -t "%DOCKER_REPO%:%VERSION%" -t "%DOCKER_REPO%:latest" .
if %errorlevel% neq 0 (
    echo  ERROR: Docker build failed
    pause
    exit /b 1
)

echo  Docker image built successfully!
echo   Tagged as: %DOCKER_REPO%:%VERSION%
echo   Tagged as: %DOCKER_REPO%:latest

REM Ask user about pushing
echo.
set /p push_confirm=" Push to Docker Hub? (y/N): "
if /i "%push_confirm%"=="y" (
    goto :push_image
) else (
    goto :show_local_info
)

:push_image
echo.
echo  Pushing to Docker Hub...

REM Push version tag
echo    Pushing %DOCKER_REPO%:%VERSION%...
docker push "%DOCKER_REPO%:%VERSION%"
if %errorlevel% neq 0 (
    echo  ERROR: Failed to push version tag
    echo    Make sure you are logged in: docker login
    pause
    exit /b 1
)

REM Push latest tag
echo    Pushing %DOCKER_REPO%:latest...
docker push "%DOCKER_REPO%:latest"
if %errorlevel% neq 0 (
    echo  ERROR: Failed to push latest tag
    echo    Make sure you are logged in: docker login
    pause
    exit /b 1
)

echo.
echo  SUCCESS! Docker image pushed to Docker Hub
echo.
echo  DOCKER HUB INFORMATION:
echo  Repository: %DOCKER_REPO%
echo   Tags: %VERSION%, latest
echo  URL: %DOCKER_HUB_URL%
echo.
echo  USAGE COMMANDS:
echo    Pull image:
echo      docker pull %DOCKER_REPO%:%VERSION%
echo.
echo    Run container:
echo      docker run -p 7844:7844 --env-file .env %DOCKER_REPO%:%VERSION%
echo.
echo    Run with volume mount:
echo      docker run -p 7844:7844 --env-file .env -v "%CD%\data:/app/data" %DOCKER_REPO%:%VERSION%
goto :end

:show_local_info
echo.
echo   Skipping push to Docker Hub
echo.
echo  LOCAL IMAGE INFORMATION:
echo   Local tags: %DOCKER_REPO%:%VERSION%, %DOCKER_REPO%:latest
echo.
echo  TEST LOCALLY:
echo    docker run -p 7844:7844 --env-file .env %DOCKER_REPO%:%VERSION%
echo    Then open: http://localhost:7844

:end
echo.
echo  Operation completed successfully!
echo.
pause
