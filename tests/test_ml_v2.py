"""Testes do modelo de preço v2: baseline, validação cruzada, intervalo calibrado."""
import joblib
import numpy as np
import pandas as pd

from src.data_ingestion.demo_data import generate_synthetic_listings
from src.data_processing.cleaner import DataCleaner
from src.data_processing.ml_models import (
    BASELINE_NAME,
    NeighborhoodMedianEstimator,
    PricePredictionModel,
)


def _clean(city="sao-paulo", n=300, seed=1):
    return DataCleaner().clean_listings(generate_synthetic_listings(city, n_listings=n, seed=seed))


def _structured_market(n=500, seed=0):
    """Mercado em que o R$/m² depende de bairro E de tamanho/banheiros, algo que
    a mediana do bairro não captura (logo, o ML deve vencer o baseline)."""
    rng = np.random.default_rng(seed)
    hoods = [f"Bairro {i}" for i in range(8)]
    base = dict(zip(hoods, np.linspace(6000, 14000, 8)))
    rooms = rng.integers(1, 5, n)
    area = 30 + 25 * rooms + rng.normal(0, 6, n)
    baths = np.array([rng.integers(1, r + 1) for r in rooms])
    hood = rng.choice(hoods, n)
    ppm2 = (
        np.array([base[h] for h in hood])
        * np.exp(-0.006 * (area - 80))
        * (1 + 0.2 * baths / rooms)
        * rng.lognormal(0, 0.04, n)
    )
    return pd.DataFrame(
        {"price": ppm2 * area, "area": area, "rooms": rooms, "bathrooms": baths,
         "city": "Cidade", "neighborhood": hood}
    )


class TestBaselineAndSelection:
    def test_result_reports_baseline_and_cv(self):
        res = PricePredictionModel().train(_clean())
        assert res.trained
        assert res.model_name in {BASELINE_NAME, "random_forest", "gradient_boosting"}
        assert res.baseline_mape > 0
        assert res.cv_folds >= 3
        # o modelo escolhido nunca é pior que o baseline
        assert res.mape <= res.baseline_mape + 1e-12

    def test_never_ships_worse_than_baseline(self):
        res = PricePredictionModel().train(_clean(seed=2))
        assert res.mape <= res.baseline_mape + 1e-12
        assert res.best_ml_mape > 0

    def test_ml_wins_when_structure_goes_beyond_neighborhood(self):
        model = PricePredictionModel()
        res = model.train(_structured_market())
        assert res.ml_beats_baseline is True
        assert res.model_name != BASELINE_NAME
        assert res.lift_vs_baseline_pct > 5
        assert model.metadata["feature_importance"]  # ML expõe importâncias

    def test_baseline_estimator_falls_back_for_unseen_groups(self):
        X = pd.DataFrame({"city": [0.0, 0.0, 1.0], "neighborhood": [0.0, 1.0, 0.0]})
        est = NeighborhoodMedianEstimator().fit(X, [1.0, 2.0, 3.0])
        pred = est.predict(pd.DataFrame({"city": [0.0, 0.0, -1.0], "neighborhood": [0.0, 9.0, 0.0]}))
        assert list(pred) == [1.0, 1.5, 2.0]  # bairro; cidade; global


class TestCalibratedInterval:
    def test_interval_covers_about_90pct_on_unseen_data(self):
        big = _clean(n=1200, seed=7).sample(frac=1, random_state=0).reset_index(drop=True)
        train, test = big.iloc[:600], big.iloc[600:]
        model = PricePredictionModel()
        model.train(train)
        hits = []
        for _, x in test.iterrows():
            p = model.predict(x.area, int(x.rooms), int(x.bathrooms), x.city, x.neighborhood)
            hits.append(p["confidence_interval_low"] <= x.price <= p["confidence_interval_high"])
        assert 0.82 <= float(np.mean(hits)) <= 0.97

    def test_interval_brackets_point_estimate(self):
        df = _clean()
        model = PricePredictionModel()
        model.train(df)
        p = model.predict(70, 2, 2, df.city.iloc[0], df.neighborhood.iloc[0])
        assert 0 < p["confidence_interval_low"] <= p["predicted_price"] <= p["confidence_interval_high"]
        assert p["interval_coverage"] == 0.9


class TestPredictionSafety:
    def test_unknown_location_is_flagged(self):
        model = PricePredictionModel()
        model.train(_clean())
        p = model.predict(70, 2, 2, "Cidade Inexistente", "Bairro Inexistente")
        assert p["known_location"] is False
        assert "warning" in p

    def test_known_location_has_no_warning(self):
        df = _clean()
        model = PricePredictionModel()
        model.train(df)
        p = model.predict(70, 2, 2, df.city.iloc[0], df.neighborhood.iloc[0])
        assert p["known_location"] is True
        assert "warning" not in p

    def test_load_rejects_bundle_from_old_schema(self, tmp_path):
        old = tmp_path / "old.joblib"
        joblib.dump({"model": object(), "encoder": object(), "metadata": {}}, old)  # sem schema_version
        model = PricePredictionModel(model_path=old)
        assert model.load() is False
        assert not model.is_ready

    def test_oof_fair_values_are_aligned_and_positive(self):
        df = _clean()
        model = PricePredictionModel()
        model.train(df)
        oof = model.oof_fair_value_
        assert oof is not None and len(oof) == len(df)
        assert (oof > 0).all() and oof.notna().all()
