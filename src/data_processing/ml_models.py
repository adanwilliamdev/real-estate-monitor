"""
src/data_processing/ml_models.py

Modelo de Machine Learning para previsão de preços de imóveis.

Usa um RandomForestRegressor (robusto a features não-lineares e a pouca
quantidade de dados, sem exigir tuning pesado) treinado sobre
área, quartos, banheiros e localização (cidade/bairro codificados).
O modelo é serializado com `joblib` em `data/cache/` para reuso entre
execuções, evitando re-treinar a cada requisição.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder

from config.settings import settings
from src.logging_setup import logger

FEATURE_COLUMNS = ["area", "rooms", "bathrooms", "city", "neighborhood"]
CATEGORICAL_COLUMNS = ["city", "neighborhood"]
TARGET_COLUMN = "price"

MODEL_PATH = settings.CACHE_DIR / "price_model.joblib"
MIN_TRAINING_ROWS = 30


@dataclass
class TrainingResult:
    trained: bool
    n_samples: int = 0
    mae: float = 0.0
    mape: float = 0.0
    r2: float = 0.0
    feature_importance: Dict[str, float] = field(default_factory=dict)
    message: str = ""


class PricePredictionModel:
    """Prevê o preço de um imóvel a partir de suas características."""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or MODEL_PATH
        self.model: Optional[RandomForestRegressor] = None
        self.encoder: Optional[OrdinalEncoder] = None
        self.metadata: Dict = {}

    # -------------------- Treinamento --------------------
    def train(self, df: pd.DataFrame, test_size: float = 0.2) -> TrainingResult:
        """Treina o modelo a partir de um DataFrame já limpo (ver DataCleaner)."""
        cols_needed = FEATURE_COLUMNS + [TARGET_COLUMN]
        missing = [c for c in cols_needed if c not in df.columns]
        if missing:
            return TrainingResult(trained=False, message=f"Colunas ausentes: {missing}")

        data = df[cols_needed].dropna()
        if len(data) < MIN_TRAINING_ROWS:
            return TrainingResult(
                trained=False,
                n_samples=len(data),
                message=(
                    f"Dados insuficientes para treinar ({len(data)} linhas; "
                    f"mínimo recomendado: {MIN_TRAINING_ROWS})."
                ),
            )

        X = data[FEATURE_COLUMNS].copy()
        y = data[TARGET_COLUMN].copy()

        self.encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
        X[CATEGORICAL_COLUMNS] = self.encoder.fit_transform(X[CATEGORICAL_COLUMNS])

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        self.model = RandomForestRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_train, y_train)

        y_pred = self.model.predict(X_test)
        mae = float(mean_absolute_error(y_test, y_pred))
        mape = float(mean_absolute_percentage_error(y_test, y_pred))
        r2 = float(r2_score(y_test, y_pred))

        importance = dict(zip(FEATURE_COLUMNS, self.model.feature_importances_.tolist()))

        self.metadata = {
            "n_samples": len(data),
            "mae": mae,
            "mape": mape,
            "r2": r2,
            "feature_importance": importance,
            "trained_at": pd.Timestamp.utcnow().isoformat(),
        }

        logger.info(
            f"Modelo de preço treinado: {len(data)} amostras | "
            f"MAE=R${mae:,.0f} | MAPE={mape:.1%} | R²={r2:.3f}"
        )

        return TrainingResult(
            trained=True,
            n_samples=len(data),
            mae=mae,
            mape=mape,
            r2=r2,
            feature_importance=importance,
            message="Modelo treinado com sucesso.",
        )

    # -------------------- Persistência --------------------
    def save(self) -> bool:
        if self.model is None or self.encoder is None:
            return False
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {"model": self.model, "encoder": self.encoder, "metadata": self.metadata},
            self.model_path,
        )
        logger.info(f"Modelo salvo em {self.model_path}")
        return True

    def load(self) -> bool:
        if not self.model_path.exists():
            return False
        try:
            bundle = joblib.load(self.model_path)
            self.model = bundle["model"]
            self.encoder = bundle["encoder"]
            self.metadata = bundle.get("metadata", {})
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Falha ao carregar modelo salvo: {exc}")
            return False

    @property
    def is_ready(self) -> bool:
        return self.model is not None and self.encoder is not None

    # -------------------- Predição --------------------
    def predict(
        self,
        area: float,
        rooms: int,
        bathrooms: int,
        city: str,
        neighborhood: str,
    ) -> Dict:
        """Prevê o preço e devolve um intervalo de confiança aproximado.

        O intervalo é estimado a partir da dispersão das previsões das
        árvores individuais do Random Forest (não é um intervalo estatístico
        formal, mas dá uma noção honesta de incerteza).
        """
        if not self.is_ready:
            raise RuntimeError("Modelo ainda não foi treinado/carregado.")

        row = pd.DataFrame(
            [{"area": area, "rooms": rooms, "bathrooms": bathrooms, "city": city,
              "neighborhood": neighborhood}]
        )
        row[CATEGORICAL_COLUMNS] = self.encoder.transform(row[CATEGORICAL_COLUMNS])
        row = row[FEATURE_COLUMNS]

        tree_preds = np.array([tree.predict(row.values)[0] for tree in self.model.estimators_])
        point_estimate = float(tree_preds.mean())
        std = float(tree_preds.std())

        return {
            "predicted_price": round(point_estimate, 2),
            "price_per_m2": round(point_estimate / area, 2) if area else None,
            "confidence_interval_low": round(max(0.0, point_estimate - 1.64 * std), 2),
            "confidence_interval_high": round(point_estimate + 1.64 * std, 2),
            "model_r2": self.metadata.get("r2"),
            "model_mape": self.metadata.get("mape"),
            "trained_at": self.metadata.get("trained_at"),
        }


def train_and_save_model(df: pd.DataFrame) -> TrainingResult:
    """Atalho: treina o modelo com o DataFrame informado e salva em disco."""
    model = PricePredictionModel()
    result = model.train(df)
    if result.trained:
        model.save()
    return result


def load_model() -> PricePredictionModel:
    model = PricePredictionModel()
    model.load()
    return model
