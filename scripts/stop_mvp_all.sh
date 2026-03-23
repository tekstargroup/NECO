#!/bin/bash
#
# NECO MVP — Stop All Services

echo "Stopping NECO MVP services..."

pkill -f "uvicorn app.main" 2>/dev/null && echo "  Stopped backend" || true
pkill -f "next-server" 2>/dev/null && echo "  Stopped frontend" || true
pkill -f "celery.*worker" 2>/dev/null && echo "  Stopped Celery worker" || true
pkill -f "celery.*beat" 2>/dev/null && echo "  Stopped Celery beat" || true

echo "Done. (Docker containers still running; use 'docker-compose down' to stop them.)"
