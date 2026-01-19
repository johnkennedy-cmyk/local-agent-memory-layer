# FML Server Dockerfile
FROM python:3.11-slim

LABEL maintainer="FML Server"
LABEL description="Firebolt Memory Layer - MCP Server for LLM Memory Management"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (for better caching)
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy remaining files
COPY config/ ./config/
COPY scripts/ ./scripts/

# Create a non-root user for security
RUN useradd -m -u 1000 fml && chown -R fml:fml /app
USER fml

# Environment variables (can be overridden)
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health check - verify Ollama and Firebolt are reachable
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://host.docker.internal:11434/api/tags', timeout=5)" || exit 1

# Default command - run the HTTP API (MCP server runs via stdio, managed by Cursor)
CMD ["python", "-m", "src.http_api"]
