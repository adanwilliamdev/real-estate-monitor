#!/usr/bin/env bash
# scripts/quick_start.sh
# Quick start script para Linux/macOS
set -e

echo "Iniciando Real Estate Monitor..."

if ! command -v python3 &> /dev/null; then
    echo "Python 3 nao encontrado. Instale Python 3.9+"
    exit 1
fi
echo "Encontrado: $(python3 --version)"

echo "Criando ambiente virtual..."
python3 -m venv venv

echo "Ativando ambiente virtual..."
# shellcheck disable=SC1091
source venv/bin/activate

echo "Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
    echo "Criando arquivo .env..."
    cp .env.example .env
fi

echo "Iniciando a aplicacao (dados de demonstracao)..."
python main.py run --source demo
