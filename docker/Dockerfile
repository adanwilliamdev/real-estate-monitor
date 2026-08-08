FROM python:3.11-slim

WORKDIR /app

# Dependências de sistema mínimas (gcc necessário para compilar algumas libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/cache data/processed data/raw logs

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Porta do dashboard Streamlit (8501) e da API REST FastAPI (8000).
# O comando efetivo (dashboard ou API) é definido em docker-compose.yml.
EXPOSE 8501 8000

CMD ["streamlit", "run", "src/visualization/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
