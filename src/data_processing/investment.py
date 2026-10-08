"""
src/data_processing/investment.py

Análise de viabilidade de investimento imobiliário: estimativa de aluguel,
yield bruto/líquido, payback e comparação com a média do mercado local.

O "rent-to-price ratio" (razão aluguel/preço) varia por cidade e padrão de
imóvel no Brasil, tipicamente entre 0.35% e 0.60% ao mês. Como o projeto
não tem uma fonte de aluguéis reais, usamos essa razão calibrada por
cidade como uma estimativa heurística e deixamos isso explícito para quem
usar os números — não é garantia de rentabilidade real.
"""
from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd


# Razão aluguel mensal / preço de venda, por cidade (estimativa heurística
# baseada em faixas tipicamente observadas no mercado brasileiro).
RENT_TO_PRICE_RATIO: Dict[str, float] = {
    "São Paulo": 0.0050,
    "Rio de Janeiro": 0.0045,
    "Belo Horizonte": 0.0055,
    "Curitiba": 0.0055,
    "Porto Alegre": 0.0052,
}
DEFAULT_RENT_RATIO = 0.0050

# Custos recorrentes estimados como % do aluguel bruto (condomínio médio
# embutido no cálculo do proprietário, IPTU, manutenção, vacância).
DEFAULT_EXPENSE_RATIO = 0.25

# Custos de transação estimados (ITBI + escritura + corretagem), como % do
# valor do imóvel — usados no cálculo de payback "todo incluso".
DEFAULT_TRANSACTION_COST_RATIO = 0.06


@dataclass
class InvestmentAnalysis:
    price: float
    estimated_monthly_rent: float
    gross_yield_annual: float
    net_yield_annual: float
    payback_years: float
    payback_years_with_costs: float
    rent_to_price_ratio_used: float
    vs_market_price_per_m2_pct: Optional[float]
    verdict: str
    notes: str


class InvestmentAnalyzer:
    """Calcula métricas de viabilidade de investimento para um imóvel."""

    def __init__(
        self,
        expense_ratio: float = DEFAULT_EXPENSE_RATIO,
        transaction_cost_ratio: float = DEFAULT_TRANSACTION_COST_RATIO,
    ):
        self.expense_ratio = expense_ratio
        self.transaction_cost_ratio = transaction_cost_ratio

    def _rent_ratio(self, city: str) -> float:
        return RENT_TO_PRICE_RATIO.get(city, DEFAULT_RENT_RATIO)

    def analyze(
        self,
        price: float,
        city: str,
        area: Optional[float] = None,
        market_price_per_m2: Optional[float] = None,
        fair_value: Optional[float] = None,
    ) -> InvestmentAnalysis:
        """Analisa a viabilidade de comprar um imóvel pelo `price` pedido.

        `fair_value` (opcional): valor de mercado estimado do imóvel (ver
        `opportunities.py`). O aluguel de um imóvel depende do que ele *vale*,
        não do que o vendedor pede; por isso, quando informado, o aluguel é
        estimado sobre o valor justo e o yield é medido sobre o preço pago.
        Sem ele, o aluguel é proporcional ao próprio preço e o yield fica
        idêntico para todos os imóveis da mesma cidade (comportamento legado).
        """
        if price <= 0:
            raise ValueError("Preço deve ser positivo")

        rent_ratio = self._rent_ratio(city)
        rent_basis = fair_value if fair_value is not None and fair_value > 0 else price
        monthly_rent = rent_basis * rent_ratio
        gross_yield_annual = (monthly_rent * 12) / price
        net_annual_rent = monthly_rent * 12 * (1 - self.expense_ratio)
        net_yield_annual = net_annual_rent / price

        payback_years = price / (monthly_rent * 12) if monthly_rent > 0 else float("inf")
        total_cost = price * (1 + self.transaction_cost_ratio)
        payback_years_with_costs = (
            total_cost / net_annual_rent if net_annual_rent > 0 else float("inf")
        )

        vs_market_pct = None
        if area and market_price_per_m2 and area > 0:
            actual_per_m2 = price / area
            vs_market_pct = (actual_per_m2 / market_price_per_m2 - 1) * 100

        verdict, notes = self._verdict(net_yield_annual, vs_market_pct)
        if rent_basis != price:
            notes += (
                f" Aluguel estimado sobre o valor justo (R$ {rent_basis:,.0f}), "
                "não sobre o preço pedido."
            )

        return InvestmentAnalysis(
            price=round(price, 2),
            estimated_monthly_rent=round(monthly_rent, 2),
            gross_yield_annual=round(gross_yield_annual * 100, 2),
            net_yield_annual=round(net_yield_annual * 100, 2),
            payback_years=round(payback_years, 1),
            payback_years_with_costs=round(payback_years_with_costs, 1),
            rent_to_price_ratio_used=rent_ratio,
            vs_market_price_per_m2_pct=round(vs_market_pct, 1) if vs_market_pct is not None else None,
            verdict=verdict,
            notes=notes,
        )

    @staticmethod
    def _verdict(net_yield_annual: float, vs_market_pct: Optional[float]) -> tuple:
        if net_yield_annual >= 0.07:
            verdict = "🟢 Yield atrativo"
        elif net_yield_annual >= 0.045:
            verdict = "🟡 Yield na média do mercado"
        else:
            verdict = "🔴 Yield abaixo da média"

        notes = (
            "Estimativa baseada na razão aluguel/preço típica da cidade "
            "e em custos recorrentes médios (condomínio, IPTU, vacância, "
            "manutenção). Não substitui uma avaliação de aluguel real do imóvel."
        )
        if vs_market_pct is not None:
            if vs_market_pct <= -10:
                notes += f" Preço {abs(vs_market_pct):.0f}% ABAIXO da média do m² local — pode indicar oportunidade."
            elif vs_market_pct >= 10:
                notes += f" Preço {vs_market_pct:.0f}% ACIMA da média do m² local — avalie com cautela."

        return verdict, notes

    def rank_best_opportunities(
        self, df: pd.DataFrame, top_n: int = 10
    ) -> pd.DataFrame:
        """Rankeia imóveis do DataFrame por yield líquido estimado.

        Se o DataFrame tiver a coluna `fair_value`, o aluguel é estimado sobre
        ela e o ranking passa a diferenciar imóveis da mesma cidade (quem está
        abaixo do valor justo rende mais). Sem ela, todos os imóveis de uma
        cidade empatam no mesmo yield — para um ranking útil, use
        `OpportunityFinder` (opportunities.py).
        """
        if df is None or df.empty:
            return pd.DataFrame()

        required = {"price", "city"}
        if not required.issubset(df.columns):
            return pd.DataFrame()

        rows = []
        market_avg = df.groupby("city")["price_per_m2"].mean().to_dict() if "price_per_m2" in df else {}

        for _, r in df.iterrows():
            try:
                analysis = self.analyze(
                    price=float(r["price"]),
                    city=r["city"],
                    area=float(r["area"]) if "area" in r and pd.notnull(r["area"]) else None,
                    market_price_per_m2=market_avg.get(r["city"]),
                    fair_value=(
                        float(r["fair_value"])
                        if "fair_value" in r and pd.notnull(r["fair_value"])
                        else None
                    ),
                )
            except (ValueError, TypeError):
                continue
            rows.append(
                {
                    "city": r.get("city"),
                    "neighborhood": r.get("neighborhood"),
                    "price": analysis.price,
                    "area": r.get("area"),
                    "estimated_monthly_rent": analysis.estimated_monthly_rent,
                    "net_yield_annual_pct": analysis.net_yield_annual,
                    "payback_years": analysis.payback_years,
                    "vs_market_pct": analysis.vs_market_price_per_m2_pct,
                    "verdict": analysis.verdict,
                }
            )

        result = pd.DataFrame(rows)
        if result.empty:
            return result
        return result.sort_values("net_yield_annual_pct", ascending=False).head(top_n)
