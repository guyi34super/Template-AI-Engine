#!/bin/bash
# AI-RAG Engine Startup Script for Linux/Mac

echo "============================================"
echo "AI-RAG Document Processing Engine"
echo "============================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    echo ""
    exit 1
fi

# Load environment variables
echo "Loading environment variables..."
export $(grep -v '^#' .env | xargs)

echo ""
echo "Starting server..."
echo "Host: ${HOST:-0.0.0.0}"
echo "Port: ${PORT:-8000}"
echo ""
echo "API Documentation: http://localhost:${PORT:-8000}/docs"
echo ""

python3 api_server.py

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Server failed to start"
    exit 1
fi
