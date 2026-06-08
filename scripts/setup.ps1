$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,
        [Parameter(Mandatory = $true)]
        [string] $InstallHint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Error "$Name is required. $InstallHint"
    }
}

Assert-Command "uv" "Install uv from https://docs.astral.sh/uv/ and rerun this script."
Assert-Command "node" "Install Node.js 18+ and rerun this script."
Assert-Command "npm" "Install npm with Node.js and rerun this script."

Write-Host "Setting up backend Python environment..."
uv sync --project backend --frozen --link-mode=copy

Write-Host "Installing frontend dependencies..."
Push-Location frontend
npm ci
Pop-Location

if (-not (Test-Path "backend/.env") -and (Test-Path "backend/.env.example")) {
    Copy-Item "backend/.env.example" "backend/.env"
    Write-Host "Created backend/.env from backend/.env.example"
}

if (-not (Test-Path "frontend/.env") -and (Test-Path "frontend/.env.example")) {
    Copy-Item "frontend/.env.example" "frontend/.env"
    Write-Host "Created frontend/.env from frontend/.env.example"
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run backend:  uv run --project backend --frozen python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
Write-Host "Run frontend: cd frontend; npm run dev"
