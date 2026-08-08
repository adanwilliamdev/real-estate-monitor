# scripts/quick_start.ps1
# Quick start script for Windows

Write-Host "Iniciando Real Estate Monitor..." -ForegroundColor Cyan

$pythonVersion = python --version 2>$null
if (-not $pythonVersion) {
    Write-Host "Python nao encontrado. Por favor, instale Python 3.9+" -ForegroundColor Red
    exit 1
}
Write-Host "Encontrado: $pythonVersion" -ForegroundColor Green

Write-Host "Criando ambiente virtual..." -ForegroundColor Yellow
python -m venv venv

Write-Host "Ativando ambiente virtual..." -ForegroundColor Yellow
. .\venv\Scripts\Activate.ps1

Write-Host "Instalando dependencias..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt

if (-not (Test-Path .env)) {
    Write-Host "Criando arquivo .env..." -ForegroundColor Yellow
    Copy-Item .env.example .env
}

Write-Host "Iniciando a aplicacao (dados de demonstracao)..." -ForegroundColor Green
python main.py run --source demo
