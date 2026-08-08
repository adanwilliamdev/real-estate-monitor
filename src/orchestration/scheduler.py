"""
src/orchestration/scheduler.py

Agendador leve (usa a biblioteca `schedule`) para rodar o pipeline
periodicamente sem precisar de um orquestrador externo. Opcional: só é
usado se o operador executar este script diretamente.
"""
import time

from src.logging_setup import logger
from src.orchestration.pipeline import run_pipeline


class Scheduler:
    """Agenda execuções periódicas do pipeline de coleta/análise."""

    def __init__(self, city: str = "sao-paulo", source: str = "demo"):
        self.city = city
        self.source = source

    def setup_schedule(self):
        import schedule

        schedule.every().day.at("08:00").do(self.run_scrape)
        schedule.every().monday.at("09:00").do(self.run_scrape)
        logger.info("Agendador configurado (diário às 08:00)")
        return schedule

    def run_scrape(self):
        logger.info("Executando coleta agendada")
        try:
            run_pipeline(city=self.city, source=self.source)
            logger.info("Coleta agendada concluída")
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Coleta agendada falhou: {exc}")

    def run_forever(self):
        schedule = self.setup_schedule()
        logger.info("Scheduler iniciado (Ctrl+C para parar)")
        while True:
            schedule.run_pending()
            time.sleep(60)


if __name__ == "__main__":
    Scheduler().run_forever()
