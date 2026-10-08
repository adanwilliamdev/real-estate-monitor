"""
src/data_processing/opportunities.py

Motor de oportunidades: responde "quais anúncios estão baratos *para o que
valem*?" em vez de "quais têm o maior yield?".

Como funciona
-------------
1. **Valor justo** de cada anúncio, estimado por `PricePredictionModel` com
   previsões *out-of-fold* (o modelo nunca vê o próprio anúncio que está
   avaliando; sem isso, o modelo "decora" o preço e o desconto some).
2. **Desconto** = quanto o preço pedido está abaixo do valor justo, e se ele
   cai *abaixo do intervalo de ~90%* (sinal estatisticamente mais forte que
   um desconto pontual).
3. **Yield líquido** estimado com o aluguel calculado sobre o valor justo
   (ver `InvestmentAnalyzer.analyze(fair_value=...)`).
4. **Score 0-100** transparente (pesos configuráveis) + texto com o motivo.
5. **Alerta de verificação**: descontos muito grandes costumam ser erro de
   digitação, anúncio desatualizado ou golpe, não pechincha. Esses casos são
   marcados com `needs_review=True` em vez de serem celebrados.

Quando há poucos dados (ou faltam colunas) para treinar o modelo, usa-se como
fallback a mediana de R$/m² do grupo (excluindo o próprio anúncio), sem
intervalo, e o score de confiança fica reduzido.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.data_processing.investment import InvestmentAnalyzer
from src.data_processing.ml_models import PricePredictionModel, TrainingResult
from src.logging_setup import logger

DEFAULT_WEIGHTS: Tuple[float, float, float] = (0.60, 0.25, 0.15)  # desconto, yield, confiança

OUTPUT_COLUMNS = [
    "source", "source_id", "url", "address", "city", "neighborhood", "price", "area", "rooms",
    "fair_value", "fair_value_low", "fair_value_high", "discount_pct", "below_interval",
    "net_yield_annual_pct", "payback_years", "score", "needs_review", "reason",
    "valuation_method",
]


class OpportunityFinder:
    """Pontua e ranqueia anúncios por desconto sobre o valor justo."""

    def __init__(
        self,
        min_discount_pct: float = 5.0,
        review_discount_pct: float = 40.0,
        weights: Tuple[float, float, float] = DEFAULT_WEIGHTS,
        analyzer: Optional[InvestmentAnalyzer] = None,
    ):
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("Os pesos devem somar 1.0")
        self.min_discount_pct = min_discount_pct
        self.review_discount_pct = review_discount_pct
        self.weights = weights
        self.analyzer = analyzer or InvestmentAnalyzer()
        # Preenchidos após `score_all`/`rank`:
        self.model_: Optional[PricePredictionModel] = None
        self.training_result_: Optional[TrainingResult] = None

    # ------------------------------------------------------------------
    # Valor justo
    # ------------------------------------------------------------------
    def _fair_values(self, df: pd.DataFrame) -> Tuple[pd.Series, Optional[float], str]:
        """Retorna (valor justo por linha, quantil log do intervalo ou None, método)."""
        df_model = df.copy()
        if "bathrooms" in df_model.columns:
            df_model["bathrooms"] = df_model["bathrooms"].fillna(1)

        model = PricePredictionModel()
        result = model.train(df_model)
        self.model_, self.training_result_ = model, result

        if result.trained and model.oof_fair_value_ is not None:
            q = float(model.metadata["conformal_log_q"])
            return model.oof_fair_value_.reindex(df.index), q, model.metadata["model_name"]

        logger.warning(
            f"Modelo indisponível para valor justo ({result.message}); "
            "usando mediana de R$/m² do grupo como fallback."
        )
        return self._fallback_fair_values(df), None, "median_fallback"

    @staticmethod
    def _fallback_fair_values(df: pd.DataFrame) -> pd.Series:
        """Mediana de R$/m² do grupo (cidade/bairro) × área, excluindo o próprio anúncio."""
        ppm2 = (df["price"] / df["area"]).where(df["area"] > 0)
        keys = [c for c in ("city", "neighborhood") if c in df.columns]
        groups = df.groupby(keys).indices.values() if keys else [np.arange(len(df))]

        fair = pd.Series(np.nan, index=df.index, dtype=float)
        values = ppm2.to_numpy(dtype=float)
        for idx in groups:
            for i in idx:
                others = values[idx[idx != i]]
                others = others[~np.isnan(others)]
                if len(others):
                    fair.iloc[i] = float(np.median(others)) * df["area"].iloc[i]
        return fair

    # ------------------------------------------------------------------
    # Pontuação
    # ------------------------------------------------------------------
    def score_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pontua todos os anúncios com preço/área válidos (sem filtrar nem ordenar)."""
        if df is None or df.empty or not {"price", "area"}.issubset(df.columns):
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        df = df.reset_index(drop=True).copy()
        df = df[(df["price"] > 0) & (df["area"] > 0)].reset_index(drop=True)
        if df.empty:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        fair, q, method = self._fair_values(df)
        out = df.copy()
        out["fair_value"] = fair
        out = out[out["fair_value"].notna() & (out["fair_value"] > 0)].copy()
        if out.empty:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        if q is not None:
            out["fair_value_low"] = out["fair_value"] * math.exp(-q)
            out["fair_value_high"] = out["fair_value"] * math.exp(q)
            out["below_interval"] = out["price"] < out["fair_value_low"]
        else:
            out["fair_value_low"] = np.nan
            out["fair_value_high"] = np.nan
            out["below_interval"] = False

        out["discount_pct"] = (out["fair_value"] - out["price"]) / out["fair_value"] * 100

        yields, paybacks = [], []
        for _, r in out.iterrows():
            a = self.analyzer.analyze(
                price=float(r["price"]),
                city=r.get("city"),
                area=float(r["area"]),
                fair_value=float(r["fair_value"]),
            )
            yields.append(a.net_yield_annual)
            paybacks.append(a.payback_years_with_costs)
        out["net_yield_annual_pct"] = yields
        out["payback_years"] = paybacks

        w_disc, w_yield, w_conf = self.weights
        disc_norm = ((out["discount_pct"] + 10) / 40).clip(0, 1)  # -10% -> 0 ; +30% -> 1
        yield_norm = out["net_yield_annual_pct"].rank(pct=True)
        if q is not None:
            conf = np.where(out["below_interval"], 1.0, np.where(out["discount_pct"] > 0, 0.5, 0.0))
        else:  # sem intervalo calibrado, a confiança nunca é máxima
            conf = np.where(out["discount_pct"] >= self.min_discount_pct, 0.5, 0.0)
        out["score"] = (100 * (w_disc * disc_norm + w_yield * yield_norm + w_conf * conf)).round(1)

        out["needs_review"] = out["discount_pct"] >= self.review_discount_pct
        out["valuation_method"] = method
        out["reason"] = out.apply(self._reason, axis=1)

        for col in OUTPUT_COLUMNS:
            if col not in out.columns:
                out[col] = None
        return out[OUTPUT_COLUMNS]

    @staticmethod
    def _reason(r: pd.Series) -> str:
        parts = []
        if r["discount_pct"] > 0:
            parts.append(
                f"{r['discount_pct']:.0f}% abaixo do valor justo estimado "
                f"(R$ {r['fair_value']:,.0f})"
            )
        else:
            parts.append(
                f"{abs(r['discount_pct']):.0f}% acima do valor justo estimado "
                f"(R$ {r['fair_value']:,.0f})"
            )
        if r["below_interval"]:
            parts.append("abaixo do intervalo de ~90% do modelo")
        parts.append(f"yield líquido estimado ~{r['net_yield_annual_pct']:.1f}% ao ano")
        if r["needs_review"]:
            parts.append("ATENÇÃO: desconto atípico, confira o anúncio (erro de preço, desatualizado ou golpe)")
        return "; ".join(parts) + "."

    def rank(self, df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
        """Melhores oportunidades: apenas anúncios abaixo do valor justo, por score."""
        scored = self.score_all(df)
        if scored.empty:
            return scored
        picked = scored[scored["discount_pct"] >= self.min_discount_pct]
        return picked.sort_values("score", ascending=False).head(top_n).reset_index(drop=True)

    # ------------------------------------------------------------------
    # Resumo (usado pelo pipeline para gerar alertas)
    # ------------------------------------------------------------------
    @staticmethod
    def summarize_by_city(ranked: pd.DataFrame) -> Dict[str, Dict]:
        """Por cidade: nº de oportunidades fortes (abaixo do intervalo, sem alerta
        de verificação) e a melhor delas."""
        summary: Dict[str, Dict] = {}
        if ranked is None or ranked.empty:
            return summary
        strong = ranked[ranked["below_interval"] & ~ranked["needs_review"]]
        for city, grp in strong.groupby("city"):
            best = grp.sort_values("score", ascending=False).iloc[0]
            summary[city] = {"count": int(len(grp)), "best": best.to_dict()}
        return summary


def opportunity_alerts(ranked: pd.DataFrame) -> List[Dict]:
    """Alertas (um por cidade) para oportunidades fortes: abaixo do intervalo
    de ~90% do valor justo e sem sinal de anúncio suspeito."""
    alerts: List[Dict] = []
    for city, info in OpportunityFinder.summarize_by_city(ranked).items():
        best = info["best"]
        alerts.append(
            {
                "severity": "info",
                "category": "opportunity",
                "city": city,
                "neighborhood": best.get("neighborhood"),
                "message": (
                    f"{info['count']} oportunidade(s) abaixo do intervalo de valor justo em {city}. "
                    f"Melhor: {best.get('neighborhood') or 'N/D'}, {best['area']:.0f} m², "
                    f"R$ {best['price']:,.0f} ({best['discount_pct']:.0f}% abaixo do valor justo)."
                ),
                "value": float(info["count"]),
            }
        )
    return alerts
