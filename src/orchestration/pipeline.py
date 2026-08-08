"""
src/orchestration/pipeline.py

Pipeline de coleta -> limpeza -> armazenamento -> análise, em Python puro.
Não depende de Prefect/Airflow para rodar (o que tornaria o projeto pesado
e frágil neste ambiente); esses orquestradores continuam disponíveis como
camada opcional em `prefect_flows.py` para quem quiser agendar execuções.
"""
from datetime import datetime
from typing import Dict

import pandas as pd

from src.alerts.alert_engine import AlertEngine
from src.data_ingestion.demo_data import generate_synthetic_listings
from src.data_ingestion.scraper import RealEstateScraper
from src.data_processing.analytics import RealEstateAnalytics
from src.data_processing.cleaner import DataCleaner
from src.data_processing.ml_models import train_and_save_model
from src.data_storage.database import DatabaseManager
from src.logging_setup import logger


def collect_properties(city: str, source: str = "demo", n_listings: int = 300) -> pd.DataFrame:
    """Coleta anúncios da fonte escolhida.

    source="demo": gera dados sintéticos (sempre funciona).
    source="live": tenta raspar o site real; se não retornar nada, cai
                   automaticamente para dados sintéticos.
    """
    if source == "live":
        logger.info(f"Tentando scraping ao vivo para {city}")
        scraper = RealEstateScraper()
        df = scraper.scrape_zapimoveis(city)
        scraper.close()
        if not df.empty:
            return df
        logger.warning("Scraping ao vivo falhou ou não retornou dados; usando dados demo")

    return generate_synthetic_listings(city, n_listings=n_listings)


def clean_properties(df: pd.DataFrame) -> pd.DataFrame:
    cleaner = DataCleaner()
    return cleaner.clean_listings(df)


def save_properties(df: pd.DataFrame, db: DatabaseManager) -> int:
    return db.save_listings(df)


def analyze_data(db: DatabaseManager) -> Dict:
    df = db.get_listings()
    if df.empty:
        return {}

    # Campos derivados (price_per_m2, categorias, etc.) não são persistidos
    # no banco, então recalculamos aqui a partir dos dados brutos salvos.
    cleaner = DataCleaner()
    df = cleaner.clean_listings(df)
    if df.empty:
        return {}

    stats = cleaner.calculate_market_metrics(df)
    neighborhood_stats = cleaner.calculate_neighborhood_stats(df)

    return {
        "statistics": stats,
        "neighborhood_stats": neighborhood_stats.reset_index().to_dict(orient="records"),
        "timestamp": datetime.utcnow().isoformat(),
    }


def generate_report(analysis_results: Dict) -> str:
    stats = analysis_results.get("statistics", {})
    report_lines = [
        "📊 Relatório de Mercado Imobiliário",
        "=" * 34,
        f"Data: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC",
        "",
        "Métricas Gerais:",
        f"- Total de Imóveis: {stats.get('total_listings', 0)}",
        f"- Preço Médio: R$ {stats.get('average_price', 0):,.0f}",
        f"- Preço Mediano: R$ {stats.get('median_price', 0):,.0f}",
        f"- Preço por m² Médio: R$ {stats.get('average_price_per_m2', 0):,.0f}",
        "",
        "Principais Bairros por Preço Médio:",
    ]

    neighborhood_stats = analysis_results.get("neighborhood_stats", [])
    sorted_hoods = sorted(
        neighborhood_stats, key=lambda x: x.get("price_mean", 0) or 0, reverse=True
    )[:5]
    for hood in sorted_hoods:
        name = hood.get("neighborhood", "N/D")
        report_lines.append(f"- {name}: R$ {hood.get('price_mean', 0):,.0f}")

    return "\n".join(report_lines)


def run_pipeline(
    city: str = "sao-paulo",
    source: str = "demo",
    n_listings: int = 300,
    replace_existing: bool = True,
    train_model: bool = True,
    check_alerts: bool = True,
) -> Dict:
    """Executa o pipeline completo e retorna um resumo do resultado.

    Além de coletar -> limpar -> salvar -> analisar, esta versão também:
    - grava um snapshot agregado do mercado (para séries temporais);
    - roda o `AlertEngine` comparando com o snapshot anterior;
    - re-treina o modelo de previsão de preços com os dados mais recentes.
    """
    logger.info(f"Iniciando pipeline para '{city}' (fonte={source})")

    df = collect_properties(city, source=source, n_listings=n_listings)
    if df.empty:
        logger.warning("Nenhum imóvel coletado; pipeline interrompido")
        return {"scraped_count": 0, "saved_count": 0, "analysis": {}, "alerts": [], "model": {}}

    df_clean = clean_properties(df)

    db = DatabaseManager()
    if replace_existing:
        db.clear_listings()
    saved_count = save_properties(df_clean, db)

    # Enriquece com anomalias (necessário para o AlertEngine) antes do snapshot
    analytics = RealEstateAnalytics()
    df_enriched = analytics.detect_anomalies(df_clean)

    alerts: list = []
    if check_alerts:
        try:
            alert_engine = AlertEngine()
            alerts = alert_engine.evaluate(df_enriched, db)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Falha ao avaliar alertas: {exc}")

    # Snapshot é salvo DEPOIS da avaliação de alertas, para comparar com o anterior
    db.save_snapshot(df_enriched)

    model_result: Dict = {}
    if train_model:
        try:
            # Usa todo o histórico salvo (não só o lote atual) quando disponível
            training_df = clean_properties(db.get_listings())
            result = train_and_save_model(training_df if not training_df.empty else df_clean)
            model_result = {
                "trained": result.trained,
                "n_samples": result.n_samples,
                "mae": result.mae,
                "mape": result.mape,
                "r2": result.r2,
                "message": result.message,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Falha ao treinar modelo de preço: {exc}")
            model_result = {"trained": False, "message": str(exc)}

    analysis_results = analyze_data(db)
    report = generate_report(analysis_results)
    logger.info("\n" + report)

    return {
        "scraped_count": len(df),
        "saved_count": saved_count,
        "analysis": analysis_results,
        "report": report,
        "alerts": alerts,
        "model": model_result,
    }


# Alias mantido para compatibilidade com o nome usado no restante do projeto
real_estate_pipeline = run_pipeline


if __name__ == "__main__":
    run_pipeline()
