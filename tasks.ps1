#requires -Version 5.1
<#
.SYNOPSIS
    FlowCare AI task runner — boot the stack with one command.
.EXAMPLE
    .\tasks.ps1 setup      # one-time: venv + python + frontend deps
    .\tasks.ps1 test       # run the backend test suite
    .\tasks.ps1 api        # run the API locally (SQLite + in-memory queue)
    .\tasks.ps1 web        # run the Next.js frontend
    .\tasks.ps1 docker     # full stack via docker compose
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'test', 'ci', 'migrate', 'makemigration', 'api', 'web', 'docker', 'clean', 'help')]
    [string]$Command = 'help',

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$VenvPy = Join-Path $Backend '.venv\Scripts\python.exe'

function Assert-Venv {
    if (-not (Test-Path $VenvPy)) {
        Write-Host "No backend venv found. Run:  .\tasks.ps1 setup" -ForegroundColor Yellow
        exit 1
    }
}

function Set-LocalEnv {
    # Local dev profile: SQLite + in-memory Celery (tasks run inline, no Redis needed).
    if (-not $env:DATABASE_URL) { $env:DATABASE_URL = 'sqlite+pysqlite:///./flowcare.db' }
    $env:CELERY_BROKER_URL = 'memory://'
    $env:CELERY_RESULT_BACKEND = 'cache+memory://'
    if (-not $env:STORAGE_BACKEND) { $env:STORAGE_BACKEND = 'local' }
    if (-not $env:SECRET_KEY) {
        $env:SECRET_KEY = 'local-dev-secret-0123456789abcdef0123456789abcdef'
    }
}

function Invoke-Setup {
    Write-Host "==> Creating backend venv + installing Python deps" -ForegroundColor Cyan
    if (-not (Test-Path $VenvPy)) { python -m venv (Join-Path $Backend '.venv') }
    # Note: --disable-pip-version-check avoids pip's self-upgrade prompt; we don't
    # upgrade pip in place (that step is flaky when OneDrive is syncing .venv).
    & $VenvPy -m pip install --disable-pip-version-check -r (Join-Path $Backend 'requirements.txt')
    if ($LASTEXITCODE -ne 0) {
        Write-Host "pip install was interrupted. If this path is under OneDrive, pause" -ForegroundColor Yellow
        Write-Host "OneDrive sync and retry, or just run:  .\tasks.ps1 test" -ForegroundColor Yellow
        exit 1
    }

    Write-Host "==> Installing frontend deps" -ForegroundColor Cyan
    Push-Location $Frontend
    try { npm install } finally { Pop-Location }
    Write-Host "Setup complete. Try:  .\tasks.ps1 test" -ForegroundColor Green
}

function Invoke-Test {
    Assert-Venv
    Push-Location $Backend
    try { & $VenvPy -m pytest @Rest } finally { Pop-Location }
}

function Invoke-Ci {
    # Mirrors .github/workflows/ci.yml so you can catch failures before pushing.
    Assert-Venv
    Write-Host "==> Backend: tests + coverage (fail under 80%)" -ForegroundColor Cyan
    Push-Location $Backend
    try {
        & $VenvPy -m pytest --cov=app --cov-report=term-missing --cov-fail-under=80
        if ($LASTEXITCODE -ne 0) { Write-Host "Backend CI failed." -ForegroundColor Red; exit 1 }
    }
    finally { Pop-Location }

    Write-Host "==> Frontend: typecheck + build" -ForegroundColor Cyan
    Push-Location $Frontend
    try {
        npx tsc --noEmit
        if ($LASTEXITCODE -ne 0) { Write-Host "Typecheck failed." -ForegroundColor Red; exit 1 }
        npm run build
        if ($LASTEXITCODE -ne 0) { Write-Host "Frontend build failed." -ForegroundColor Red; exit 1 }
    }
    finally { Pop-Location }
    Write-Host "CI checks passed." -ForegroundColor Green
}

function Invoke-Migrate {
    # Apply Alembic migrations to the configured database (DATABASE_URL / .env).
    Assert-Venv
    Push-Location $Backend
    try { & $VenvPy -m alembic upgrade head @Rest } finally { Pop-Location }
}

function Invoke-MakeMigration {
    # Autogenerate a migration from model changes:  .\tasks.ps1 makemigration "add foo"
    Assert-Venv
    $msg = if ($Rest) { $Rest -join ' ' } else { 'migration' }
    Push-Location $Backend
    try { & $VenvPy -m alembic revision --autogenerate -m $msg } finally { Pop-Location }
}

function Invoke-Api {
    Assert-Venv
    Set-LocalEnv
    Write-Host "==> API -> http://localhost:8000/docs   (DB: $env:DATABASE_URL)" -ForegroundColor Cyan
    if ($env:ANTHROPIC_API_KEY) {
        Write-Host "    LLM extraction: Claude ($env:ANTHROPIC_MODEL)" -ForegroundColor Green
    }
    else {
        Write-Host "    LLM extraction: template fallback (set ANTHROPIC_API_KEY for Claude)" -ForegroundColor Yellow
    }
    # --reload omitted by default: on a OneDrive-synced path the file watcher
    # triggers constant restarts and slows startup. Opt in:  .\tasks.ps1 api --reload
    Push-Location $Backend
    try { & $VenvPy -m uvicorn app.main:app --host 127.0.0.1 --port 8000 @Rest } finally { Pop-Location }
}

function Invoke-Web {
    Write-Host "==> Frontend -> http://localhost:3000" -ForegroundColor Cyan
    Push-Location $Frontend
    try { npm run dev @Rest } finally { Pop-Location }
}

function Invoke-Docker {
    Push-Location $Root
    try {
        if (-not (Test-Path (Join-Path $Root '.env'))) {
            Copy-Item (Join-Path $Root '.env.example') (Join-Path $Root '.env')
            Write-Host "Created .env from .env.example" -ForegroundColor Green
        }
        docker compose up --build @Rest
    }
    finally { Pop-Location }
}

function Invoke-Clean {
    Remove-Item (Join-Path $Backend 'flowcare.db') -ErrorAction SilentlyContinue
    Write-Host "Removed local SQLite database (if present)." -ForegroundColor Green
}

function Show-Help {
    Write-Host @"
FlowCare AI - task runner

Usage:  .\tasks.ps1 <command> [extra args]

  setup    One-time: create backend venv, install Python + frontend deps
  test     Run the backend test suite (pytest)
  ci       Run the full CI checks locally (backend tests+coverage, frontend typecheck+build)
  migrate  Apply Alembic migrations (alembic upgrade head) to DATABASE_URL
  makemigration <msg>   Autogenerate a migration from model changes
  api      Run the API locally (SQLite + in-memory queue) -> http://localhost:8000/docs
  web      Run the Next.js frontend -> http://localhost:3000
  docker   Bring up the full stack (Postgres/Redis/MinIO/workers/Grafana) via docker compose
  clean    Delete the local SQLite database
  help     Show this message

Extra args pass through to the underlying tool, e.g.:
  .\tasks.ps1 test tests/test_twilio.py -v
  .\tasks.ps1 api --port 8001

Seeded admin login:  admin@flowcare.ai / admin12345
"@
}

switch ($Command) {
    'setup' { Invoke-Setup }
    'test' { Invoke-Test }
    'ci' { Invoke-Ci }
    'migrate' { Invoke-Migrate }
    'makemigration' { Invoke-MakeMigration }
    'api' { Invoke-Api }
    'web' { Invoke-Web }
    'docker' { Invoke-Docker }
    'clean' { Invoke-Clean }
    default { Show-Help }
}
