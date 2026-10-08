"""Testes do motor de oportunidades (valor justo, desconto, score, verificação)."""
import numpy as np
import pandas as pd

from src.data_ingestion.demo_data import generate_synthetic_listings
from src.data_processing.cleaner import DataCleaner
from src.data_processing.investment import InvestmentAnalyzer
from src.data_processing.opportunities import OpportunityFinder, opportunity_alerts


def _market(seed_a=11, seed_b=12, n=150):
    raw = pd.concat(
        [generate_synthetic_listings("sao-paulo", n, seed=seed_a),
         generate_synthetic_listings("curitiba", n, seed=seed_b)],
        ignore_index=True,
    )
    return DataCleaner().clean_listings(raw)


def _auc(positives_scores, negatives_scores):
    """AUC por comparação de pares (sem depender de sklearn)."""
    pos = np.asarray(positives_scores)[:, None]
    neg = np.asarray(negatives_scores)[None, :]
    return float(((pos > neg) + 0.5 * (pos == neg)).mean())


class TestDiscoveryOfPlantedBargains:
    def test_planted_discounts_score_far_above_normal_listings(self):
        df = _market()
        rng = np.random.default_rng(0)
        planted = rng.choice(len(df), 15, replace=False)
        df.loc[planted, "price"] *= 0.75  # −25% real
        df["price_per_m2"] = df["price"] / df["area"]

        scored = OpportunityFinder().score_all(df).set_index("source_id")
        planted_ids = set(df.loc[planted, "source_id"])
        pos = scored.loc[scored.index.isin(planted_ids), "score"]
        neg = scored.loc[~scored.index.isin(planted_ids), "score"]
        assert _auc(pos, neg) > 0.85

    def test_rank_only_returns_listings_below_fair_value(self):
        ranked = OpportunityFinder(min_discount_pct=5).rank(_market(), top_n=30)
        assert not ranked.empty
        assert (ranked["discount_pct"] >= 5).all()
        assert list(ranked["score"]) == sorted(ranked["score"], reverse=True)
        assert ranked["reason"].str.contains("valor justo").all()

    def test_extreme_discount_is_flagged_for_review_not_celebrated(self):
        df = _market()
        df.loc[0, "price"] = df.loc[0, "price"] * 0.35  # −65%: típico de erro/golpe
        df["price_per_m2"] = df["price"] / df["area"]
        scored = OpportunityFinder().score_all(df)
        row = scored[scored["source_id"] == df.loc[0, "source_id"]].iloc[0]
        assert bool(row["needs_review"]) is True
        assert "ATENÇÃO" in row["reason"]
        # e não vira alerta de "oportunidade forte"
        assert all(a["category"] == "opportunity" for a in opportunity_alerts(scored))
        flagged_ids = set(scored.loc[scored["needs_review"], "source_id"])
        strong = scored[scored["below_interval"] & ~scored["needs_review"]]
        assert flagged_ids.isdisjoint(set(strong["source_id"]))


class TestFallbackAndEdgeCases:
    def test_small_dataset_uses_median_fallback_without_crashing(self):
        df = _market(n=8)  # < 30 linhas: não treina
        finder = OpportunityFinder()
        scored = finder.score_all(df)
        assert finder.training_result_.trained is False
        if not scored.empty:
            assert (scored["valuation_method"] == "median_fallback").all()
            assert not scored["below_interval"].any()  # sem intervalo calibrado

    def test_empty_and_invalid_inputs(self):
        finder = OpportunityFinder()
        assert finder.rank(pd.DataFrame()).empty
        assert finder.rank(pd.DataFrame({"x": [1]})).empty

    def test_weights_must_sum_to_one(self):
        try:
            OpportunityFinder(weights=(0.5, 0.5, 0.5))
        except ValueError:
            return
        raise AssertionError("deveria rejeitar pesos que não somam 1")


class TestInvestmentUsesFairValue:
    def test_yield_is_identical_for_same_city_without_fair_value(self):
        df = _market().query("city == 'São Paulo'")
        ranked = InvestmentAnalyzer().rank_best_opportunities(df, top_n=500)
        assert ranked["net_yield_annual_pct"].nunique() == 1  # limitação legada documentada

    def test_yield_differs_when_fair_value_is_provided(self):
        df = _market().query("city == 'São Paulo'").copy()
        df["fair_value"] = df["price"] * np.linspace(0.8, 1.3, len(df))
        ranked = InvestmentAnalyzer().rank_best_opportunities(df, top_n=500)
        assert ranked["net_yield_annual_pct"].nunique() > 10

    def test_cheaper_than_fair_value_yields_more(self):
        a = InvestmentAnalyzer()
        fair = a.analyze(price=800_000, city="São Paulo", fair_value=1_000_000)
        same = a.analyze(price=800_000, city="São Paulo")
        assert fair.net_yield_annual > same.net_yield_annual
        assert "valor justo" in fair.notes
