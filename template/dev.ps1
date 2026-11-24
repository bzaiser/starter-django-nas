param(
    [switch]$Update,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvDir = Join-Path $PSScriptRoot ".venv"
$py = Join-Path $venvDir "Scripts\python.exe"
$firstRun = $false

if (-not (Test-Path $py)) {
    Write-Host "[1/4] Erstelle .venv..." -ForegroundColor Cyan
    python -m venv $venvDir
    $firstRun = $true
}

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[ok] .env aus .env.example erstellt" -ForegroundColor Green
}

if ($firstRun -or $Update) {
    Write-Host "[2/4] Installiere requirements.txt & lokale Kits (editable)..." -ForegroundColor Cyan
    & $py -m pip install -r requirements.txt
    $parentDir = Split-Path $PSScriptRoot -Parent
    $kitArgs = @()
    $dsPath = Join-Path $parentDir "django-design-studio"
    if (Test-Path $dsPath) { $kitArgs += @("-e", $dsPath) }
    Get-ChildItem $parentDir -Directory -Filter "*-django-kit" | ForEach-Object {
        $kitArgs += @("-e", $_.FullName)
    }
    if ($kitArgs.Count -gt 0) {
        & $py -m pip install --no-deps @kitArgs
    }
}

Write-Host "[3/4] Prüfe Migrationen..." -ForegroundColor Cyan
& $py manage.py migrate --noinput

$hasAdmin = & $py -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from django.contrib.auth import get_user_model; print(1 if get_user_model().objects.filter(is_superuser=True).exists() else 0)"
if ($hasAdmin.Trim() -eq "0") {
    Write-Host "[!] Noch kein Admin vorhanden — bitte jetzt anlegen:" -ForegroundColor Yellow
    & $py manage.py createsuperuser
}

Write-Host "[4/4] Starte Dev-Server (Auto-Reload aktiv) auf http://127.0.0.1:$Port ..." -ForegroundColor Green
& $py manage.py runserver "0.0.0.0:$Port"
