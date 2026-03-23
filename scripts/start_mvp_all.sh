#!/bin/bash
#
# NECO MVP — Start All Services

set -e

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

# Ensure logs dir exists
mkdir -p logs

# Detect venv
if [ -d "$PROJECT_ROOT/backend/venv" ]; then
    VENV_ACTIVATE="$PROJECT_ROOT/backend/venv/bin/activate"
elif [ -d "$PROJECT_ROOT/venv_neco" ]; then
    VENV_ACTIVATE="$PROJECT_ROOT/venv_neco/bin/activate"
else
    echo "No virtual environment found. Create backend/venv or venv_neco first."
    exit 1
fi

echo "NECO MVP — Starting all services"
echo "================================"

# 1. Docker
echo "Starting Docker (Postgres + Redis)..."
docker-compose up -d
sleep 3

# 2. Backend
echo "Starting backend..."
nohup ./start_neco.sh >> logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"
sleep 2

# 3. Frontend
echo "Starting frontend..."
cd frontend
nohup npm run dev >> ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"
cd ..
sleep 2

# 4. Celery worker
echo "Starting Celery worker..."
source "$VENV_ACTIVATE"
cd backend
nohup celery -A app.core.celery_app worker -l info >> ../logs/celery-worker.log 2>&1 &
WORKER_PID=$!
echo "  Celery worker PID: $WORKER_PID"
cd ..
sleep 2

# 5. Celery beat
echo "Starting Celery beat..."
cd backend
nohup celery -A app.core.celery_app beat -l info >> ../logs/celery-beat.log 2>&1 &
BEAT_PID=$!
echo "  Celery beat PID: $BEAT_PID"
cd ..

echo ""
echo "================================"
echo "All services started."
echo ""
echo "Backend:    http://localhost:9001"
echo "Frontend:   http://localhost:3001"
echo "API docs:   http://localhost:9001/docs"
echo ""
echo "Logs:"
echo "  logs/backend.log"
echo "  logs/frontend.log"
echo "  logs/celery-worker.log"
echo "  logs/celery-beat.log"
echo ""
echo "To stop all: ./scripts/stop_mvp_all.sh"
echo ""
