#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Initialize database schema and default admin/teacher accounts
python -c "import sys; sys.path.insert(0, 'backend'); from app.init_db import initialize_database; initialize_database(seed_data=True)"
