#!/bin/bash

# DeepView MCP Setup Script

echo "Setting up DeepView MCP for Docker Compose..."

# Create necessary directories
echo "Creating directories..."
mkdir -p codebase logs data

# Copy environment template if .env doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env file and set your GEMINI_API_KEY"
else
    echo ".env file already exists"
fi

# Check if codebase directory has files
if [ -z "$(ls -A codebase/)" ]; then
    echo "Codebase directory is empty - sample file already created"
else
    echo "Codebase directory contains files"
fi

echo ""
echo "Setup complete! Next steps:"
echo "1. Edit .env file and set your GEMINI_API_KEY"
echo "2. Add your codebase files to the codebase/ directory"
echo "3. Run: docker compose up"
echo ""

# Read port from .env file if it exists, otherwise use default
if [ -f .env ]; then
    MCP_PORT=$(grep "^MCP_PORT=" .env 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'")
fi

# Use default port if not found in .env
if [ -z "$MCP_PORT" ]; then
    MCP_PORT=8019
fi

echo "The service will be available at http://localhost:${MCP_PORT}"
echo "Health check endpoint: http://localhost:${MCP_PORT}/health"
echo ""
echo "Note: Port and other settings can be configured in the .env file"
