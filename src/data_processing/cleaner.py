"""
src/data_processing/cleaner.py
Limpeza, normalização e cálculo de métricas de mercado para os anúncios.
"""
from typing import Dict

import numpy as np
import pandas as pd

from src.logging_setup import logger

REQUIRED_COLUMNS = ["price", "area", "rooms", "source", "address", "city"]


class DataCleaner:
    """Limpa e enriquece dados de anúncios imobiliários."""

    def __init__(self, outlier_threshold: float = 3.0):
        self.outlier_threshold = outlier_threshold

    def clean_listings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pipeline principal de limpeza."""
        if df is None or df.empty:
            logger.warning("clean_listings recebeu DataFrame vazio")
            return pd.DataFrame(columns=REQUIRED_COLUMNS)

        df = df.copy()

        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                df[col] = np.nan

        dedup_cols = [c for c in ["source", "source_id", "address"] if c in df.columns]
        if dedup_cols:
            df = df.drop_duplicates(subset=dedup_cols)

        df["price"] = self._clean_numeric(df["price"])
        df["area"] = self._clean_numeric(df["area"])
        df["rooms"] = pd.to_numeric(df["rooms"], errors="coerce").fillna(0).astype(int)

        df["price_per_m2"] = df["price"] / df["area"].replace(0, np.nan)
        df["price_per_m2"] = df["price_per_m2"].replace([np.inf, -np.inf], np.nan)

        df = self._remove_outliers(df)

        if df.empty:
            logger.warning("Todos os registros foram removidos na limpeza")
            return df

        df["property_size_category"] = self._categorize_size(df["area"])
        df["price_category"] = self._categorize_price(df["price"])

        if "city" not in df.columns or df["city"].isnull().all():
            df["city"] = df["address"].apply(self._extract_city)

        logger.info(f"Limpeza concluída: {len(df)} imóveis")
        return df.reset_index(drop=True)

    @staticmethod
    def _clean_numeric(series: pd.Series) -> pd.Series:
        series = pd.to_numeric(series, errors="coerce")
        series = series.replace([np.inf, -np.inf], np.nan)
        median = series.median()
        series = series.fillna(median if pd.notnull(median) else 0)
        if series.notnull().any() and series.nunique() > 1:
            series = series.clip(
                lower=series.quantile(0.01),
                upper=series.quantile(0.99),
            )
        return series

    def _remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove outliers usando o método IQR nas colunas numéricas relevantes."""
        numeric_cols = ["price", "area", "price_per_m2"]
        df_clean = df.copy()

        for col in numeric_cols:
            if col not in df_clean.columns or df_clean[col].dropna().empty:
                continue
            q1 = df_clean[col].quantile(0.25)
            q3 = df_clean[col].quantile(0.75)
            iqr = q3 - q1
            if iqr == 0 or pd.isna(iqr):
                continue
            lower_bound = q1 - self.outlier_threshold * iqr
            upper_bound = q3 + self.outlier_threshold * iqr
            df_clean = df_clean[
                df_clean[col].isna()
                | ((df_clean[col] >= lower_bound) & (df_clean[col] <= upper_bound))
            ]

        removed = len(df) - len(df_clean)
        if removed > 0:
            logger.info(f"Removidos {removed} outliers")
        return df_clean

    @staticmethod
    def _categorize_size(area: pd.Series) -> pd.Series:
        return pd.cut(
            area,
            bins=[0, 50, 100, 200, float("inf")],
            labels=["Pequeno", "Médio", "Grande", "Mansão"],
        )

    @staticmethod
    def _categorize_price(price: pd.Series) -> pd.Series:
        return pd.cut(
            price,
            bins=[0, 500_000, 1_000_000, 2_000_000, float("inf")],
            labels=["Econômico", "Médio", "Premium", "Luxo"],
        )

    @staticmethod
    def _extract_city(address) -> str:
        if not isinstance(address, str) or not address:
            return "Desconhecido"
        parts = address.split(",")
        if len(parts) >= 2:
            return parts[-2].strip()
        return address.split()[-1]

    @staticmethod
    def calculate_market_metrics(df: pd.DataFrame) -> Dict:
        if df is None or df.empty:
            return {
                "average_price": 0, "median_price": 0, "price_std": 0,
                "average_area": 0, "median_area": 0,
                "average_price_per_m2": 0, "median_price_per_m2": 0,
                "total_listings": 0, "unique_cities": 0,
                "price_range": (0, 0),
            }
        return {
            "average_price": float(df["price"].mean()),
            "median_price": float(df["price"].median()),
            "price_std": float(df["price"].std() or 0),
            "average_area": float(df["area"].mean()),
            "median_area": float(df["area"].median()),
            "average_price_per_m2": float(df["price_per_m2"].mean()),
            "median_price_per_m2": float(df["price_per_m2"].median()),
            "total_listings": int(len(df)),
            "unique_cities": int(df["city"].nunique()),
            "price_range": (float(df["price"].min()), float(df["price"].max())),
        }

    @staticmethod
    def calculate_neighborhood_stats(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or "neighborhood" not in df.columns:
            return pd.DataFrame()

        group_cols = [c for c in ["city", "neighborhood"] if c in df.columns]
        if not group_cols:
            return pd.DataFrame()

        stats = df.groupby(group_cols).agg(
            price_mean=("price", "mean"),
            price_median=("price", "median"),
            price_std=("price", "std"),
            price_min=("price", "min"),
            price_max=("price", "max"),
            area_mean=("area", "mean"),
            area_median=("area", "median"),
            price_per_m2_mean=("price_per_m2", "mean"),
            price_per_m2_median=("price_per_m2", "median"),
            listing_count=("source", "count"),
        ).round(2)

        return stats.sort_values("price_mean", ascending=False)
