"""
src/alerts/alert_engine.py

Motor de alertas: compara o snapshot de mercado mais recente com o
anterior (por cidade) e sinaliza variações relevantes de preço, além de
picos de anomalias detectados pelo `RealEstateAnalytics`. Os alertas são
persistidos via `DatabaseManager.save_alerts` e ficam disponíveis no
dashboard e na API.

Regras (configuráveis via construtor):
- `price_change_threshold`: variação % do preço médio por m² entre a
  coleta atual e a anterior, por cidade, que dispara um alerta de
  queda/alta de preço.
- `anomaly_ratio_threshold`: % de imóveis marcados como anomalia no lote
  atual que dispara um alerta de "pico de anomalias".
"""
from typing import Dict, List

import pandas as pd

from src.data_storage.database import DatabaseManager
from src.logging_setup import logger


class AlertEngine:
    def __init__(
        self,
        price_change_threshold: float = 0.05,
        anomaly_ratio_threshold: float = 0.15,
    ):
        self.price_change_threshold = price_change_threshold
        self.anomaly_ratio_threshold = anomaly_ratio_threshold

    def evaluate(self, df: pd.DataFrame, db: DatabaseManager) -> List[Dict]:
        """Avalia o DataFrame limpo (pós-pipeline) e retorna alertas globais gerados."""
        alerts: List[Dict] = []
        if df is None or df.empty:
            return alerts

        alerts.extend(self._check_price_changes(df, db))
        alerts.extend(self._check_anomaly_spike(df))

        if alerts:
            db.save_alerts(alerts)
            logger.info(f"{len(alerts)} alerta(s) global(is) gerado(s)")
        return alerts

    def evaluate_saved_searches(self, df: pd.DataFrame, db: DatabaseManager) -> List[Dict]:
        """Confere as buscas salvas (alertas pessoais) de todos os usuários
        contra o lote de anúncios coletado nesta execução do pipeline.

        Gera um alerta pessoal (`user_id` preenchido) quando o número de
        imóveis compatíveis com os critérios de uma busca aumenta em
        relação à última execução — evita repetir o mesmo alerta a cada
        rodada quando nada de novo aparece.
        """
        alerts: List[Dict] = []
        if df is None or df.empty:
            return alerts

        searches = db.get_all_active_saved_searches()
        if searches.empty:
            return alerts

        for _, search in searches.iterrows():
            matches = self._filter_by_search(df, search)
            match_count = len(matches)
            previous_count = int(search.get("last_match_count") or 0)

            if match_count > 0 and match_count != previous_count:
                avg_price = matches["price"].mean() if "price" in matches.columns else None
                alerts.append(
                    {
                        "severity": "info",
                        "category": "saved_search_match",
                        "city": search.get("city"),
                        "neighborhood": search.get("neighborhood"),
                        "message": (
                            f"{match_count} imóvel(is) encontrados para a busca salva "
                            f"'{search.get('name')}'"
                            + (f" (preço médio R$ {avg_price:,.0f})." if avg_price else ".")
                        ),
                        "value": float(match_count),
                        "user_id": int(search["user_id"]),
                        "saved_search_id": int(search["id"]),
                    }
                )

            db.update_saved_search_match_count(int(search["id"]), match_count)

        if alerts:
            db.save_alerts(alerts)
            logger.info(f"{len(alerts)} alerta(s) pessoal(is) gerado(s)")
        return alerts

    @staticmethod
    def _filter_by_search(df: pd.DataFrame, search: pd.Series) -> pd.DataFrame:
        """Filtra o DataFrame de anúncios pelos critérios de uma `SavedSearch`."""
        result = df

        def _get(field):
            value = search.get(field)
            return None if value is None or pd.isna(value) else value

        city = _get("city")
        if city and "city" in result.columns:
            result = result[result["city"].str.contains(str(city), case=False, na=False)]

        neighborhood = _get("neighborhood")
        if neighborhood and "neighborhood" in result.columns:
            result = result[
                result["neighborhood"].str.contains(str(neighborhood), case=False, na=False)
            ]

        min_price = _get("min_price")
        if min_price is not None and "price" in result.columns:
            result = result[result["price"] >= min_price]

        max_price = _get("max_price")
        if max_price is not None and "price" in result.columns:
            result = result[result["price"] <= max_price]

        min_area = _get("min_area")
        if min_area is not None and "area" in result.columns:
            result = result[result["area"] >= min_area]

        max_area = _get("max_area")
        if max_area is not None and "area" in result.columns:
            result = result[result["area"] <= max_area]

        min_rooms = _get("min_rooms")
        if min_rooms is not None and "rooms" in result.columns:
            result = result[result["rooms"] >= min_rooms]

        return result

    def _check_price_changes(self, df: pd.DataFrame, db: DatabaseManager) -> List[Dict]:
        alerts: List[Dict] = []
        if "city" not in df.columns or "price_per_m2" not in df.columns:
            return alerts

        history = db.get_snapshots()
        if history.empty:
            return alerts

        current_avg = df.groupby("city")["price_per_m2"].mean()

        for city, current_value in current_avg.items():
            city_hist = history[history["city"] == city].sort_values("captured_at")
            if len(city_hist) < 1:
                continue
            previous_value = city_hist.iloc[-1]["avg_price_per_m2"]
            if not previous_value or pd.isna(previous_value):
                continue

            pct_change = (current_value - previous_value) / previous_value
            if abs(pct_change) < self.price_change_threshold:
                continue

            if pct_change > 0:
                severity = "warning" if pct_change < 0.15 else "critical"
                message = (
                    f"Preço médio por m² em {city} subiu {pct_change:.1%} "
                    f"desde a última coleta (R$ {previous_value:,.0f} → R$ {current_value:,.0f})."
                )
                category = "price_spike"
            else:
                severity = "info"
                message = (
                    f"Preço médio por m² em {city} caiu {abs(pct_change):.1%} "
                    f"desde a última coleta (R$ {previous_value:,.0f} → R$ {current_value:,.0f})."
                )
                category = "price_drop"

            alerts.append(
                {
                    "severity": severity,
                    "category": category,
                    "city": city,
                    "message": message,
                    "value": round(pct_change * 100, 2),
                }
            )

        return alerts

    def _check_anomaly_spike(self, df: pd.DataFrame) -> List[Dict]:
        alerts: List[Dict] = []
        if "is_anomaly" not in df.columns or df.empty:
            return alerts

        for city, group in df.groupby("city"):
            ratio = group["is_anomaly"].mean()
            if ratio >= self.anomaly_ratio_threshold:
                alerts.append(
                    {
                        "severity": "warning",
                        "category": "anomaly_spike",
                        "city": city,
                        "message": (
                            f"{ratio:.1%} dos imóveis em {city} apresentam preço/área "
                            "estatisticamente anômalos nesta coleta."
                        ),
                        "value": round(ratio * 100, 2),
                    }
                )
        return alerts
