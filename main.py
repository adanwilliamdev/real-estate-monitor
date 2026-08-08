"""
main.py — CLI do Real Estate Monitor.

Comandos:
  python main.py run        -> roda o pipeline e abre o dashboard
  python main.py scrape     -> só roda a coleta/limpeza/armazenamento
  python main.py dashboard  -> só abre o dashboard (usa dados já salvos)
  python main.py serve      -> abre o dashboard em modo "produção"
  python main.py api        -> sobe a API REST (FastAPI) em modo dev
  python main.py api --serve -> sobe a API REST em modo produção (0.0.0.0)

Todos os comandos que sobem um servidor aceitam --port <numero> para
trocar a porta padrão (útil se 8501/8000 já estiverem ocupadas).
"""
import subprocess
import sys

import click

from src.logging_setup import logger
from src.orchestration.pipeline import run_pipeline

APP_PATH = "src/visualization/app.py"


@click.group()
def cli():
    """Real Estate Monitor CLI"""


@cli.command()
@click.option("--city", default="sao-paulo", help="Cidade a coletar")
@click.option(
    "--source",
    default="demo",
    type=click.Choice(["demo", "live"]),
    help="Fonte de dados: 'demo' (sintética, sempre funciona) ou 'live' (scraping real)",
)
@click.option("--n-listings", default=300, help="Quantidade de imóveis (fonte demo)")
@click.option("--no-scrape", is_flag=True, help="Pula a coleta e usa dados já existentes")
@click.option("--port", default=8501, help="Porta do dashboard")
def run(city, source, n_listings, no_scrape, port):
    """Roda o pipeline completo e em seguida abre o dashboard."""
    if not no_scrape:
        logger.info(f"Rodando pipeline para {city} (fonte={source})")
        result = run_pipeline(city=city, source=source, n_listings=n_listings)
        logger.info(f"Pipeline concluído: {result.get('saved_count', 0)} imóveis salvos")
    else:
        logger.info("Usando dados existentes (--no-scrape)")

    logger.info(f"Iniciando dashboard na porta {port}...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", APP_PATH, "--server.port", str(port)])


@cli.command()
@click.option("--port", default=8501, help="Porta do dashboard")
def dashboard(port):
    """Abre apenas o dashboard (sem rodar coleta)."""
    logger.info(f"Abrindo dashboard na porta {port}")
    subprocess.run([sys.executable, "-m", "streamlit", "run", APP_PATH, "--server.port", str(port)])


@cli.command()
@click.option("--city", default="sao-paulo", help="Cidade a coletar")
@click.option(
    "--source",
    default="demo",
    type=click.Choice(["demo", "live"]),
)
@click.option("--n-listings", default=300, help="Quantidade de imóveis (fonte demo)")
def scrape(city, source, n_listings):
    """Roda apenas a coleta/limpeza/armazenamento (sem abrir dashboard)."""
    result = run_pipeline(city=city, source=source, n_listings=n_listings)
    logger.info(f"Coletados {result.get('scraped_count', 0)} imóveis")
    click.echo(result.get("report", ""))


@cli.command()
@click.option("--port", default=8501, help="Porta do dashboard")
def serve(port):
    """Serve o dashboard em modo produção (bind em 0.0.0.0)."""
    subprocess.run(
        [
            sys.executable, "-m", "streamlit", "run", APP_PATH,
            "--server.port", str(port),
            "--server.address", "0.0.0.0",
            "--server.headless", "true",
        ]
    )


@cli.command()
@click.option("--port", default=8000, help="Porta da API")
@click.option("--serve", "production", is_flag=True, help="Modo produção (bind 0.0.0.0, sem reload)")
def api(port, production):
    """Sobe a API REST (FastAPI/uvicorn) com endpoints de dados, ML e investimento."""
    cmd = [sys.executable, "-m", "uvicorn", "src.api.main:app", "--port", str(port)]
    if production:
        cmd += ["--host", "0.0.0.0"]
    else:
        cmd += ["--host", "127.0.0.1", "--reload"]
    logger.info(f"Subindo API REST em {'0.0.0.0' if production else '127.0.0.1'}:{port} (docs em /docs)")
    subprocess.run(cmd)


if __name__ == "__main__":
    cli()
