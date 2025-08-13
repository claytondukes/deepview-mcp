# DeepView MCP Docker Image
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies including curl for health checks
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies first (for better caching)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY deepview_mcp /app/deepview_mcp
COPY LICENSE README.md compress.py setup.py /app/

# Install the package in development mode
RUN pip install -e .

# Create necessary directories
RUN mkdir -p /data /app/logs /app/codebase && \
    touch /data/dummy-codebase.txt

# Expose the MCP port (default 8019, configurable via docker-compose port mapping)
EXPOSE 8019

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default command (can be overridden in docker-compose)
CMD [ "python", "-m", "deepview_mcp.cli" ]
