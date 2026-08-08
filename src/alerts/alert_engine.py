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
        """Avalia o DataFrame limpo (pós-pipeline) e retorna alertas gerados."""
        alerts: List[Dict] = []
        if df is None or df.empty:
            return alerts

        alerts.extend(self._check_price_changes(df, db))
        alerts.extend(self._check_anomaly_spike(df))

        if alerts:
            db.save_alerts(alerts)
            logger.info(f"{len(alerts)} alerta(s) gerado(s)")
        return alerts

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
