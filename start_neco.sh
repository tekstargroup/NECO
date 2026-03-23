#!/bin/bash

# NECO Startup Script
# Starts the Next-Gen Compliance Engine

echo "🚀 Starting NECO - Next-Gen Compliance Engine"
echo "=============================================="

# Navigate to project directory
cd "$(dirname "$0")"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "Creating .env from template..."
    cp env.example .env
    echo "✅ .env file created"
    echo "⚠️  IMPORTANT: Edit .env and add your ANTHROPIC_API_KEY"
    echo ""
    read -p "Press Enter to continue (make sure you've added your API key)..."
fi

# Start Docker services (PostgreSQL + Redis)
echo ""
echo "📦 Starting Docker services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for database to be ready..."
sleep 5

# Activate virtual environment if it exists
if [ -d "venv_neco" ]; then
    echo "🐍 Activating virtual environment..."
    source venv_neco/bin/activate
else
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv venv_neco
    source venv_neco/bin/activate
    echo "📦 Installing dependencies..."
    pip install -r backend/requirements.txt
fi

# Start the backend server
echo ""
echo "🌐 Starting NECO backend on http://localhost:9001"
echo "=============================================="
echo "📖 API Documentation: http://localhost:9001/docs"
echo "🏥 Health Check: http://localhost:9001/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 9001 --reload


