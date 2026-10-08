"""
src/orchestration/pipeline.py

Pipeline de coleta -> limpeza -> armazenamento -> análise, em Python puro.
Não depende de Prefect/Airflow para rodar (o que tornaria o projeto pesado
e frágil neste ambiente); esses orquestradores continuam disponíveis como
camada opcional em `prefect_flows.py` para quem quiser agendar execuções.
"""
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from src.alerts.alert_engine import AlertEngine
from src.data_ingestion.demo_data import (
    display_name_for,
    evolve_synthetic_listings,
    generate_synthetic_listings,
)
from src.data_ingestion.scraper import RealEstateScraper
from src.data_processing.analytics import RealEstateAnalytics
from src.data_processing.cleaner import DataCleaner
from src.data_processing.lifecycle import LifecycleDiff, diff_listings
from src.data_processing.opportunities import OpportunityFinder
from src.data_processing.serialization import df_to_records
from src.data_storage.database import DatabaseManager
from src.logging_setup import logger


def collect_properties(
    city: str,
    source: str = "demo",
    n_listings: int = 300,
    previous: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Coleta anúncios da fonte escolhida.

    source="demo": gera dados sintéticos (sempre funciona). Se `previous` (lote
                   já salvo da mesma cidade) for informado, o mercado *evolui*
                   a partir dele (vendidos, novos e reduções de preço) em vez
                   de ser regerado do zero; ver `evolve_synthetic_listings`.
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

    if previous is not None and not previous.empty:
        return evolve_synthetic_listings(previous, city, n_listings=n_listings)
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


def generate_report(
    analysis_results: Dict,
    events: Optional[Dict] = None,
    opportunities: Optional[List[Dict]] = None,
) -> str:
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

    if events and not events.get("is_first_snapshot"):
        report_lines += [
            "",
            "Movimento desde a última coleta:",
            f"- {events.get('new', 0)} novos | {events.get('removed', 0)} saíram do ar | "
            f"{events.get('price_drops', 0)} reduções de preço",
        ]

    if opportunities:
        report_lines += ["", "Melhores oportunidades (vs. valor justo estimado):"]
        for opp in opportunities[:3]:
            flag = " ⚠ verificar" if opp.get("needs_review") else ""
            report_lines.append(
                f"- {opp.get('neighborhood') or 'N/D'} ({opp.get('city')}): "
                f"R$ {opp.get('price', 0):,.0f}, {opp.get('discount_pct', 0):.0f}% abaixo do valor justo{flag}"
            )

    return "\n".join(report_lines)


def run_pipeline(
    city: str = "sao-paulo",
    source: str = "demo",
    n_listings: int = 300,
    replace_existing: bool = True,
    train_model: bool = True,
    check_alerts: bool = True,
    track_events: bool = True,
) -> Dict:
    """Executa o pipeline completo e retorna um resumo do resultado.

    Coletar -> limpar -> salvar -> analisar, e ainda:
    - atualiza **apenas as cidades coletadas** (rodar o Rio não apaga São Paulo);
    - compara com a coleta anterior (anúncios novos, retirados, reduções de preço);
    - grava um snapshot agregado do mercado (para séries temporais);
    - roda o `AlertEngine` (mercado, ciclo de vida, buscas salvas, oportunidades);
    - treina o modelo de preço e ranqueia oportunidades pelo valor justo.
    """
    logger.info(f"Iniciando pipeline para '{city}' (fonte={source})")

    db = DatabaseManager()

    previous_batch: Optional[pd.DataFrame] = None
    if source == "demo":
        try:
            previous_batch = db.get_listings(city=display_name_for(city))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Não foi possível ler o lote anterior: {exc}")

    df = collect_properties(city, source=source, n_listings=n_listings, previous=previous_batch)
    if df.empty:
        logger.warning("Nenhum imóvel coletado; pipeline interrompido")
        return {
            "scraped_count": 0, "saved_count": 0, "analysis": {}, "alerts": [],
            "model": {}, "listing_events": {}, "opportunities": [],
        }

    df_clean = clean_properties(df)

    # Substitui só as cidades coletadas e guarda o lote anterior para o diff
    diff = LifecycleDiff()
    if replace_existing:
        cities = df_clean["city"].dropna().unique().tolist() if "city" in df_clean else []
        stored = db.get_listings()
        previous_listings = (
            stored[stored["city"].isin(cities)] if not stored.empty and "city" in stored else stored
        )
        db.clear_listings(cities=cities)
        if track_events:
            diff = diff_listings(previous_listings, df_clean)
    saved_count = save_properties(df_clean, db)

    # Visão do mercado inteiro (todas as cidades salvas): usada pelas buscas
    # salvas e pelo treino/oportunidades.
    market_df = clean_properties(db.get_listings())
    if market_df.empty:
        market_df = df_clean

    # Enriquece com anomalias (necessário para o AlertEngine) antes do snapshot
    analytics = RealEstateAnalytics()
    df_enriched = analytics.detect_anomalies(df_clean)

    alerts: list = []
    if check_alerts:
        try:
            alert_engine = AlertEngine()
            alerts = alert_engine.evaluate(df_enriched, db)
            if track_events:
                alerts += alert_engine.evaluate_listing_events(diff, db)
            use_new = track_events and replace_existing and not diff.is_first_snapshot
            alerts += alert_engine.evaluate_saved_searches(
                market_df, db, new_listings=diff.new if use_new else None
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Falha ao avaliar alertas: {exc}")

    # Snapshot é salvo DEPOIS da avaliação de alertas, para comparar com o anterior
    db.save_snapshot(df_enriched)

    model_result: Dict = {}
    opportunities = pd.DataFrame()
    try:
        finder = OpportunityFinder()
        opportunities = finder.rank(market_df, top_n=20)
        res = finder.training_result_
        if train_model and res is not None:
            if res.trained and finder.model_ is not None:
                finder.model_.save()
            model_result = {
                "trained": res.trained,
                "n_samples": res.n_samples,
                "mae": res.mae,
                "mape": res.mape,
                "r2": res.r2,
                "model_name": res.model_name,
                "baseline_mape": res.baseline_mape,
                "best_ml_mape": res.best_ml_mape,
                "ml_beats_baseline": res.ml_beats_baseline,
                "message": res.message,
            }
        if check_alerts and not opportunities.empty:
            alerts += AlertEngine().evaluate_opportunities(opportunities, db)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Falha ao treinar modelo / ranquear oportunidades: {exc}")
        if train_model:
            model_result = {"trained": False, "message": str(exc)}

    analysis_results = analyze_data(db)
    events = {**diff.counts(), "is_first_snapshot": diff.is_first_snapshot}
    top_opportunities = df_to_records(opportunities.head(10))
    report = generate_report(analysis_results, events=events, opportunities=top_opportunities)
    logger.info("\n" + report)

    return {
        "scraped_count": len(df),
        "saved_count": saved_count,
        "analysis": analysis_results,
        "report": report,
        "alerts": alerts,
        "model": model_result,
        "listing_events": events,
        "opportunities": top_opportunities,
    }


# Alias mantido para compatibilidade com o nome usado no restante do projeto
real_estate_pipeline = run_pipeline


if __name__ == "__main__":
    run_pipeline()
