import pandas as pd

from src.data_processing.analytics import RealEstateAnalytics
from src.data_processing.cleaner import DataCleaner


def _sample_df():
    return pd.DataFrame(
        {
            "price": [100000, 150000, 200000, 1000000000, 120000],
            "area": [50, 60, 70, 80, 55],
            "rooms": [1, 2, 2, 3, 1],
            "source": ["test"] * 5,
            "source_id": ["1", "2", "3", "4", "5"],
            "address": ["Rua A, Bairro X, Cidade Y"] * 5,
            "city": ["Cidade Y"] * 5,
        }
    )


class TestDataCleaner:
    def test_outlier_removal(self):
        cleaner = DataCleaner()
        df = _sample_df()
        cleaned_df = cleaner._remove_outliers(df)
        assert len(cleaned_df) == 4  # remove o outlier extremo

    def test_clean_listings_end_to_end(self):
        cleaner = DataCleaner()
        df = _sample_df()
        cleaned = cleaner.clean_listings(df)
        assert "price_per_m2" in cleaned.columns
        assert "property_size_category" in cleaned.columns
        assert not cleaned.empty

    def test_clean_listings_handles_empty_df(self):
        cleaner = DataCleaner()
        result = cleaner.clean_listings(pd.DataFrame())
        assert result.empty

    def test_market_metrics(self):
        cleaner = DataCleaner()
        df = cleaner.clean_listings(_sample_df())
        metrics = cleaner.calculate_market_metrics(df)
        assert metrics["total_listings"] == len(df)
        assert metrics["average_price"] > 0


class TestRealEstateAnalytics:
    def test_detect_anomalies_adds_columns(self):
        analytics = RealEstateAnalytics()
        df = _sample_df()
        df["price_per_m2"] = df["price"] / df["area"]
        result = analytics.detect_anomalies(df, threshold=1.0)
        assert "is_anomaly" in result.columns
        assert "anomaly_score" in result.columns
        # o registro com preço extremamente fora da curva deve ter o maior score
        assert result["anomaly_score"].idxmax() == df["price"].idxmax()
        assert result["is_anomaly"].sum() >= 1  # com threshold baixo, é sinalizado

    def test_segmentation_assigns_segments(self):
        analytics = RealEstateAnalytics()
        df = pd.DataFrame(
            {
                "price": [100000 + i * 5000 for i in range(20)],
                "area": [40 + i for i in range(20)],
                "rooms": [1 + (i % 4) for i in range(20)],
            }
        )
        result = analytics.perform_segmentation(df, n_clusters=3)
        assert "segment" in result.columns
        assert result["segment"].notna().all()
