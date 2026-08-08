import pandas as pd
import pytest

from src.data_processing.investment import InvestmentAnalyzer


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "price": [500000, 700000, 900000, 1200000],
            "area": [50, 70, 90, 120],
            "city": ["São Paulo"] * 4,
            "neighborhood": ["Pinheiros", "Moema", "Jardins", "Itaim Bibi"],
            "price_per_m2": [10000, 10000, 10000, 10000],
        }
    )


class TestInvestmentAnalyzer:
    def test_analyze_returns_positive_metrics(self):
        analyzer = InvestmentAnalyzer()
        result = analyzer.analyze(price=700000, city="São Paulo", area=70)
        assert result.estimated_monthly_rent > 0
        assert result.gross_yield_annual > result.net_yield_annual  # bruto sempre >= líquido
        assert result.payback_years_with_costs > result.payback_years
        assert result.verdict

    def test_analyze_rejects_non_positive_price(self):
        analyzer = InvestmentAnalyzer()
        with pytest.raises(ValueError):
            analyzer.analyze(price=0, city="São Paulo")

    def test_analyze_unknown_city_uses_default_ratio(self):
        analyzer = InvestmentAnalyzer()
        result = analyzer.analyze(price=500000, city="Cidade Desconhecida")
        assert result.rent_to_price_ratio_used > 0

    def test_analyze_flags_above_market_price(self):
        analyzer = InvestmentAnalyzer()
        result = analyzer.analyze(price=1_000_000, city="São Paulo", area=50, market_price_per_m2=8000)
        # 1_000_000 / 50 = 20_000/m², muito acima de 8_000
        assert result.vs_market_price_per_m2_pct > 50

    def test_rank_best_opportunities_returns_sorted_dataframe(self, sample_df):
        analyzer = InvestmentAnalyzer()
        ranked = analyzer.rank_best_opportunities(sample_df, top_n=3)
        assert len(ranked) <= 3
        assert list(ranked["net_yield_annual_pct"]) == sorted(
            ranked["net_yield_annual_pct"], reverse=True
        )

    def test_rank_best_opportunities_handles_empty_df(self):
        analyzer = InvestmentAnalyzer()
        result = analyzer.rank_best_opportunities(pd.DataFrame())
        assert result.empty
