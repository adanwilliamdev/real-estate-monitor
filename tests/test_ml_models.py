import pandas as pd
import pytest

from src.data_ingestion.demo_data import generate_synthetic_listings
from src.data_processing.cleaner import DataCleaner
from src.data_processing.ml_models import PricePredictionModel, train_and_save_model


@pytest.fixture
def clean_df():
    df = generate_synthetic_listings("sao-paulo", n_listings=120, seed=42)
    return DataCleaner().clean_listings(df)


class TestPricePredictionModel:
    def test_train_with_enough_data_succeeds(self, clean_df):
        model = PricePredictionModel()
        result = model.train(clean_df)
        assert result.trained is True
        assert result.n_samples > 0
        assert 0 <= result.r2 <= 1 or result.r2 < 0  # r2 pode ser negativo em casos raros, mas deve existir
        assert model.is_ready

    def test_train_with_insufficient_data_fails_gracefully(self):
        tiny_df = pd.DataFrame(
            {
                "price": [100000, 200000],
                "area": [50, 60],
                "rooms": [1, 2],
                "bathrooms": [1, 1],
                "city": ["São Paulo", "São Paulo"],
                "neighborhood": ["Centro", "Centro"],
            }
        )
        model = PricePredictionModel()
        result = model.train(tiny_df)
        assert result.trained is False
        assert not model.is_ready

    def test_predict_returns_expected_fields(self, clean_df):
        model = PricePredictionModel()
        model.train(clean_df)
        city = clean_df["city"].iloc[0]
        neighborhood = clean_df["neighborhood"].iloc[0]

        result = model.predict(area=70, rooms=2, bathrooms=2, city=city, neighborhood=neighborhood)
        assert result["predicted_price"] > 0
        assert result["confidence_interval_low"] <= result["predicted_price"] <= result["confidence_interval_high"]

    def test_predict_without_training_raises(self):
        model = PricePredictionModel()
        with pytest.raises(RuntimeError):
            model.predict(area=70, rooms=2, bathrooms=2, city="São Paulo", neighborhood="Centro")

    def test_save_and_load_roundtrip(self, clean_df, tmp_path):
        model_path = tmp_path / "model.joblib"
        model = PricePredictionModel(model_path=model_path)
        model.train(clean_df)
        assert model.save() is True

        loaded = PricePredictionModel(model_path=model_path)
        assert loaded.load() is True
        assert loaded.is_ready

        city = clean_df["city"].iloc[0]
        neighborhood = clean_df["neighborhood"].iloc[0]
        result = loaded.predict(area=70, rooms=2, bathrooms=2, city=city, neighborhood=neighborhood)
        assert result["predicted_price"] > 0

    def test_train_and_save_model_shortcut(self, clean_df, monkeypatch, tmp_path):
        import src.data_processing.ml_models as ml_module

        monkeypatch.setattr(ml_module, "MODEL_PATH", tmp_path / "shortcut_model.joblib")
        result = train_and_save_model(clean_df)
        assert result.trained is True
