#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

require_command() {
  local name="$1"
  local hint="$2"
  if ! command -v "${name}" >/dev/null 2>&1; then
    echo "${name} is required. ${hint}" >&2
    exit 1
  fi
}

require_command "uv" "Install uv from https://docs.astral.sh/uv/ and rerun this script."
require_command "node" "Install Node.js 18+ and rerun this script."
require_command "npm" "Install npm with Node.js and rerun this script."

echo "Setting up backend Python environment..."
uv sync --project backend --frozen --link-mode=copy

echo "Installing frontend dependencies..."
npm ci --prefix frontend

if [[ ! -f backend/.env && -f backend/.env.example ]]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env from backend/.env.example"
fi

if [[ ! -f frontend/.env && -f frontend/.env.example ]]; then
  cp frontend/.env.example frontend/.env
  echo "Created frontend/.env from frontend/.env.example"
fi

echo
echo "Setup complete."
echo "Run backend:  uv run --project backend --frozen python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
echo "Run frontend: cd frontend && npm run dev"
