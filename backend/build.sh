#!/bin/bash
# Redirect all output to build.log
exec > build.log 2>&1

echo "Starting build process..."
pip install poetry
echo "Poetry version:"
poetry --version

echo "Installing dependencies..."
poetry install --no-root

echo "Running Alembic..."
poetry run alembic upgrade head

echo "Running init_checkpointer..."
poetry run python scripts/init_checkpointer.py

echo "Build process finished."
exit 0
