#!/usr/bin/env bash
set -euo pipefail

# Build script for Render single-service deployment.
# Installs backend Python deps and builds the React frontend into backend/static.

echo "==> Installing backend dependencies"
pip install --upgrade pip
pip install -r backend/requirements.txt

echo "==> Building frontend"
# Node/npm are provided by Render's Python runtime build image.
cd frontend
npm install
npm run build
cd ..

echo "==> Copying frontend build into backend/static"
mkdir -p backend/static
cp -r frontend/dist/. backend/static/

echo "==> Build complete"
ls -la backend/static
