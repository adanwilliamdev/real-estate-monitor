"""
src/orchestration/prefect_flows.py

Camada OPCIONAL de orquestração com Prefect, para quem quiser agendar/
monitorar execuções via Prefect UI/Server. Não é necessária para rodar o
projeto (veja `pipeline.py` para o pipeline puro em Python), e o pacote
`prefect` só é importado se estiver instalado — caso contrário, este
módulo simplesmente informa como instalá-lo.
"""
from src.logging_setup import logger
from src.orchestration.pipeline import run_pipeline

try:
    from prefect import flow, task

    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False


if PREFECT_AVAILABLE:

    @task(retries=2, retry_delay_seconds=30)
    def run_pipeline_task(city: str, source: str, n_listings: int):
        return run_pipeline(city=city, source=source, n_listings=n_listings)

    @flow(name="Real Estate Monitor Flow")
    def real_estate_pipeline(city: str = "sao-paulo", source: str = "demo", n_listings: int = 300):
        """Flow do Prefect que envolve o pipeline principal."""
        return run_pipeline_task(city, source, n_listings)

else:

    def real_estate_pipeline(city: str = "sao-paulo", source: str = "demo", n_listings: int = 300):
        """Fallback: roda o pipeline puro em Python se Prefect não estiver instalado."""
        logger.info(
            "Pacote 'prefect' não instalado; executando pipeline sem orquestração "
            "(instale com `pip install prefect` para usar flows/agendamento)"
        )
        return run_pipeline(city=city, source=source, n_listings=n_listings)


if __name__ == "__main__":
    real_estate_pipeline()
