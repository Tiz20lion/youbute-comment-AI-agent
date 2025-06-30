# ====================================================================
# 🚀 Tiz Lion AI Agent - YouTube Comment Automation
# ====================================================================
# Optimized Docker image with FastAPI + Uvicorn server
# GitHub: https://github.com/Tiz20lion/youtube-comment-AI-agent
# Docker Hub: https://hub.docker.com/r/tiz20lion/youtube-comment-ai-agent
# Updated: 2025-06-30 - Simplified single-stage build
# ====================================================================

FROM python:3.11-slim

# Set build arguments
ARG BUILD_DATE
ARG VERSION=latest

# Set metadata labels
LABEL maintainer="Tiz Lion AI <contact@tizlionai.com>" \
      version="${VERSION}" \
      description="YouTube Comment AI Agent - Intelligent automation system" \
      build-date="${BUILD_DATE}"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=7844 \
    HOST=0.0.0.0 \
    WORKERS=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code with proper ownership
COPY --chown=appuser:appuser . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/data /app/logs /app/temp && \
    chown -R appuser:appuser /app && \
    chmod +x startup.py

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 7844

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:7844/health || exit 1

# Set default command
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7844", "--workers", "1"]
