#!/bin/bash
# Quick script to run Alembic migration

# Navigate to backend directory
cd "/Users/stevenbigio/Cursor Projects/NECO/backend"

# Activate virtual environment
source ../venv_neco/bin/activate

# Verify alembic is available
if ! command -v alembic &> /dev/null; then
    echo "❌ Error: alembic not found. Make sure virtual environment is activated."
    echo "   Try: source ../venv_neco/bin/activate"
    exit 1
fi

# Verify alembic.ini exists
if [ ! -f "alembic.ini" ]; then
    echo "❌ Error: alembic.ini not found in current directory"
    echo "   Current directory: $(pwd)"
    exit 1
fi

# Run migration
echo "✅ Running Alembic migration..."
alembic upgrade head

