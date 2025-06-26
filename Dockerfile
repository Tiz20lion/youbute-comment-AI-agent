# Use Python 3.11 slim image for better performance
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies including bash
RUN apt-get update && apt-get install -y \
    bash \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/data/channels \
    && mkdir -p /app/logs \
    && mkdir -p /app/temp

# Copy application code
COPY app/ ./app/
COPY startup.py ./
COPY oauth2_setup.py ./
COPY example.env ./

# Copy entrypoint script and encoding fix script
COPY docker-entrypoint.sh ./
COPY fix_encoding.sh ./

# Run encoding fix during build to ensure proper line endings and encoding
RUN chmod +x fix_encoding.sh \
    && ./fix_encoding.sh \
    && rm fix_encoding.sh fix_encoding.sh.backup docker-entrypoint.sh.backup 2>/dev/null || true

# Create a non-root user for security
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose the port the app runs on
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Use bash to run the entrypoint script
ENTRYPOINT ["/bin/bash", "./docker-entrypoint.sh"]