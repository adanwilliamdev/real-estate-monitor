"""
src/data_processing/analytics.py
Análises avançadas: segmentação (clustering), tendências e detecção de anomalias.
"""
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from src.logging_setup import logger


class RealEstateAnalytics:
    """Análises avançadas para dados imobiliários."""

    def __init__(self):
        self.scaler = StandardScaler()

    def perform_segmentation(self, df: pd.DataFrame, n_clusters: int = 4) -> pd.DataFrame:
        """Segmenta imóveis por similaridade (preço, área, quartos) via K-Means."""
        df = df.copy()
        features = ["price", "area", "rooms"]

        df_seg = df[features].dropna()
        n_clusters = max(1, min(n_clusters, len(df_seg)))

        if len(df_seg) < 2:
            df["segment"] = np.nan
            return df

        X_scaled = self.scaler.fit_transform(df_seg)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df_seg = df_seg.assign(segment=kmeans.fit_predict(X_scaled))

        df["segment"] = np.nan
        df.loc[df_seg.index, "segment"] = df_seg["segment"]

        logger.info(f"Criados {n_clusters} segmentos de imóveis")
        return df

    @staticmethod
    def calculate_growth_rate(df: pd.DataFrame) -> pd.DataFrame:
        """Calcula variação de preço ao longo do tempo, por cidade."""
        if df.empty or "scraped_at" not in df.columns:
            return df

        df = df.sort_values(["city", "scraped_at"]).copy()
        df["price_change"] = df.groupby("city")["price"].pct_change()
        df["price_change_abs"] = df.groupby("city")["price"].diff()
        return df

    @staticmethod
    def detect_anomalies(df: pd.DataFrame, threshold: float = 2.5) -> pd.DataFrame:
        """Marca imóveis com preço/área estatisticamente anômalos (z-score)."""
        df = df.copy()
        if df.empty:
            df["anomaly_score"] = pd.Series(dtype=float)
            df["is_anomaly"] = pd.Series(dtype=bool)
            return df

        price_filled = df["price"].fillna(df["price"].median())
        area_filled = df["area"].fillna(df["area"].median())

        price_std = price_filled.std()
        area_std = area_filled.std()

        df["price_zscore"] = (
            np.abs(stats.zscore(price_filled)) if price_std and price_std > 0 else 0.0
        )
        df["area_zscore"] = (
            np.abs(stats.zscore(area_filled)) if area_std and area_std > 0 else 0.0
        )

        df["anomaly_score"] = (df["price_zscore"] + df["area_zscore"]) / 2
        df["is_anomaly"] = df["anomaly_score"] > threshold

        logger.info(f"Detectadas {int(df['is_anomaly'].sum())} anomalias")
        return df
