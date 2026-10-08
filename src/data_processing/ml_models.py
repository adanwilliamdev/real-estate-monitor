"""
src/data_processing/ml_models.py

Modelo de Machine Learning para previsão de preços de imóveis (v2).

O que mudou em relação à v1:

- **Alvo = log(R$/m²)**: preços são multiplicativos e o tamanho domina o
  preço absoluto. Modelar o preço por m² (e multiplicar pela área na saída)
  deixa o modelo aprender só localização/padrão, como nas avaliações
  hedônicas tradicionais, e estabiliza o erro entre faixas de preço.
- **Validação cruzada (K-Fold) em vez de um único split 80/20**: as métricas
  deixam de depender da sorte de um sorteio e todos os dados são usados.
- **Seleção automática** entre baseline, Random Forest e Gradient Boosting pelo
  menor MAPE em validação cruzada.
- **Baseline como concorrente** (mediana de R$/m² do bairro × área): entra na
  mesma validação cruzada. Se nenhum modelo de ML vencer essa regra de uma
  linha, ela é o modelo escolhido, e as métricas dizem isso
  (`ml_beats_baseline`, `best_ml_mape`, `lift_vs_baseline_pct`).
- **Intervalo de predição calibrado (split-conformal / resíduos
  out-of-fold)**: o intervalo de ~90% vem da distribuição dos erros reais do
  modelo em dados que ele não viu, não do desvio entre árvores.
- As previsões *out-of-fold* ficam disponíveis (``oof_fair_value_``) para estimar
  o "valor justo" de cada anúncio sem vazamento (usado em ``opportunities.py``).

A interface pública (`PricePredictionModel.train/predict/save/load`,
`train_and_save_model`, `load_model`) foi mantida.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import KFold
from sklearn.preprocessing import OrdinalEncoder

from config.settings import settings
from src.logging_setup import logger

# Colunas que o chamador precisa fornecer
FEATURE_COLUMNS = ["area", "rooms", "bathrooms", "city", "neighborhood"]
CATEGORICAL_COLUMNS = ["city", "neighborhood"]
TARGET_COLUMN = "price"
# Colunas efetivamente vistas pelo modelo (inclui features derivadas)
MODEL_FEATURES = FEATURE_COLUMNS + ["area_per_room", "bath_per_room"]

MODEL_PATH = settings.CACHE_DIR / "price_model.joblib"
MIN_TRAINING_ROWS = 30
SCHEMA_VERSION = 2  # incrementar quando o formato de features/bundle mudar
INTERVAL_COVERAGE = 0.90
RANDOM_STATE = 42


@dataclass
class TrainingResult:
    trained: bool
    n_samples: int = 0
    mae: float = 0.0
    mape: float = 0.0
    r2: float = 0.0
    feature_importance: Dict[str, float] = field(default_factory=dict)
    message: str = ""
    # --- novos campos (todos com default: compatível com quem já usa a v1) ---
    model_name: str = ""
    baseline_mape: float = 0.0
    lift_vs_baseline_pct: float = 0.0  # redução de MAPE do modelo escolhido vs baseline (0 = baseline venceu)
    best_ml_mape: float = 0.0  # melhor MAPE entre os modelos de ML (mesmo que o baseline tenha vencido)
    ml_beats_baseline: bool = False
    cv_folds: int = 0
    interval_coverage: float = 0.0


# --------------------------------------------------------------------------
# Baseline: mediana de R$/m² por bairro (também concorre na seleção)
# --------------------------------------------------------------------------
class NeighborhoodMedianEstimator:
    """Regra simples: log(R$/m²) = mediana do bairro (fallback: cidade → global).

    Opera sobre a mesma matriz de features dos modelos de ML (cidade/bairro já
    codificados), então entra na validação cruzada em pé de igualdade. É a
    régua do sistema: o ML só é escolhido se vencer esta regra de uma linha.
    """

    def fit(self, X: pd.DataFrame, y) -> "NeighborhoodMedianEstimator":
        d = pd.DataFrame(
            {"c": X["city"].to_numpy(), "h": X["neighborhood"].to_numpy(), "y": np.asarray(y)}
        )
        self.global_ = float(d["y"].median())
        self.city_ = d.groupby("c")["y"].median().to_dict()
        self.hood_ = d.groupby(["c", "h"])["y"].median().to_dict()
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.array(
            [
                self.hood_.get((c, h), self.city_.get(c, self.global_))
                for c, h in zip(X["city"].to_numpy(), X["neighborhood"].to_numpy())
            ],
            dtype=float,
        )


BASELINE_NAME = "neighborhood_median"


# --------------------------------------------------------------------------
# Helpers de features / modelos
# --------------------------------------------------------------------------
def _add_engineered_features(X: pd.DataFrame) -> pd.DataFrame:
    X = X.copy()
    rooms = X["rooms"].clip(lower=1)  # studios (0 quartos) contam como 1
    X["area_per_room"] = X["area"] / rooms
    X["bath_per_room"] = X["bathrooms"] / rooms
    return X


def _candidate_models() -> Dict[str, Callable[[], object]]:
    return {
        BASELINE_NAME: NeighborhoodMedianEstimator,
        "random_forest": lambda: RandomForestRegressor(
            n_estimators=200, max_depth=12, min_samples_leaf=3,
            random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "gradient_boosting": lambda: GradientBoostingRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=3,
            subsample=0.8, random_state=RANDOM_STATE,
        ),
    }


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "mape": float(mean_absolute_percentage_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def _conformal_quantile(abs_residuals: np.ndarray, coverage: float) -> float:
    """Quantil conformal (com correção de amostra finita) dos resíduos absolutos."""
    n = len(abs_residuals)
    level = min(1.0, math.ceil((n + 1) * coverage) / n)
    return float(np.quantile(abs_residuals, level, method="higher"))


class PricePredictionModel:
    """Prevê o preço de um imóvel a partir de suas características."""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or MODEL_PATH
        self.model = None
        self.encoder: Optional[OrdinalEncoder] = None
        self.metadata: Dict = {}
        # Preços "justos" out-of-fold, alinhados ao índice do DataFrame de treino.
        self.oof_fair_value_: Optional[pd.Series] = None

    # -------------------- Treinamento --------------------
    def _matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df[FEATURE_COLUMNS].copy()
        X[CATEGORICAL_COLUMNS] = self.encoder.transform(X[CATEGORICAL_COLUMNS])
        return _add_engineered_features(X)[MODEL_FEATURES]

    def train(self, df: pd.DataFrame) -> TrainingResult:
        """Treina a partir de um DataFrame já limpo (ver `DataCleaner`)."""
        cols_needed = FEATURE_COLUMNS + [TARGET_COLUMN]
        missing = [c for c in cols_needed if c not in df.columns]
        if missing:
            return TrainingResult(trained=False, message=f"Colunas ausentes: {missing}")

        data = df[cols_needed].dropna()
        data = data[(data[TARGET_COLUMN] > 0) & (data["area"] > 0)]
        if len(data) < MIN_TRAINING_ROWS:
            return TrainingResult(
                trained=False,
                n_samples=len(data),
                message=(
                    f"Dados insuficientes para treinar ({len(data)} linhas; "
                    f"mínimo recomendado: {MIN_TRAINING_ROWS})."
                ),
            )

        self.encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
        self.encoder.fit(data[CATEGORICAL_COLUMNS])
        X = self._matrix(data)
        y = data[TARGET_COLUMN].to_numpy(dtype=float)
        area = data["area"].to_numpy(dtype=float)
        # Alvo: log(R$/m²). Remove o efeito dominante do tamanho e deixa o modelo
        # aprender só localização/padrão; o preço volta como exp(pred) × área.
        y_log = np.log(y / area)

        n_splits = max(3, min(5, len(data) // 10))
        kf = KFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
        folds = list(kf.split(X))

        # --- candidatos (baseline incluso): previsões out-of-fold em log(R$/m²) ---
        # Todo ajuste acontece dentro do fold de treino, sem vazamento.
        scores: Dict[str, Dict[str, float]] = {}
        oof_by_name: Dict[str, np.ndarray] = {}
        for name, factory in _candidate_models().items():
            oof_log = np.zeros(len(data))
            for tr, te in folds:
                est = factory()
                est.fit(X.iloc[tr], y_log[tr])
                oof_log[te] = est.predict(X.iloc[te])
            scores[name] = _metrics(y, np.exp(oof_log) * area)
            oof_by_name[name] = oof_log
            logger.info(f"CV[{name}]: MAPE={scores[name]['mape']:.1%} R²={scores[name]['r2']:.3f}")

        best_name = min(scores, key=lambda n: scores[n]["mape"])
        best_m, best_oof_log = scores[best_name], oof_by_name[best_name]
        baseline_m = scores[BASELINE_NAME]
        ml_scores = {n: m for n, m in scores.items() if n != BASELINE_NAME}
        best_ml_mape = min(m["mape"] for m in ml_scores.values())

        # --- modelo final com todos os dados ---
        self.model = _candidate_models()[best_name]()
        self.model.fit(X, y_log)

        # --- intervalo calibrado a partir dos resíduos out-of-fold ---
        conformal_q = _conformal_quantile(np.abs(y_log - best_oof_log), INTERVAL_COVERAGE)
        self.oof_fair_value_ = pd.Series(np.exp(best_oof_log) * area, index=data.index)

        importance = (
            dict(zip(MODEL_FEATURES, map(float, self.model.feature_importances_)))
            if hasattr(self.model, "feature_importances_")
            else {}
        )
        lift = (
            (baseline_m["mape"] - best_m["mape"]) / baseline_m["mape"] * 100
            if baseline_m["mape"] > 0
            else 0.0
        )

        self.metadata = {
            "schema_version": SCHEMA_VERSION,
            "model_name": best_name,
            "n_samples": len(data),
            "cv_folds": n_splits,
            **best_m,
            "baseline_mape": baseline_m["mape"],
            "baseline_r2": baseline_m["r2"],
            "best_ml_mape": best_ml_mape,
            "ml_beats_baseline": best_name != BASELINE_NAME,
            "lift_vs_baseline_pct": lift,
            "feature_importance": importance,
            "conformal_log_q": conformal_q,
            "interval_coverage": INTERVAL_COVERAGE,
            "trained_at": pd.Timestamp.now(tz="UTC").isoformat(),
        }

        logger.info(
            f"Modelo de preço treinado ({best_name}, {n_splits}-fold): {len(data)} amostras | "
            f"MAPE={best_m['mape']:.1%} (baseline {baseline_m['mape']:.1%}) | R²={best_m['r2']:.3f}"
        )

        return TrainingResult(
            trained=True,
            n_samples=len(data),
            mae=best_m["mae"],
            mape=best_m["mape"],
            r2=best_m["r2"],
            feature_importance=importance,
            message="Modelo treinado com sucesso.",
            model_name=best_name,
            baseline_mape=baseline_m["mape"],
            lift_vs_baseline_pct=lift,
            best_ml_mape=best_ml_mape,
            ml_beats_baseline=best_name != BASELINE_NAME,
            cv_folds=n_splits,
            interval_coverage=INTERVAL_COVERAGE,
        )

    # -------------------- Persistência --------------------
    def save(self) -> bool:
        if self.model is None or self.encoder is None:
            return False
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "schema_version": SCHEMA_VERSION,
                "model": self.model,
                "encoder": self.encoder,
                "metadata": self.metadata,
            },
            self.model_path,
        )
        logger.info(f"Modelo salvo em {self.model_path}")
        return True

    def load(self) -> bool:
        if not self.model_path.exists():
            return False
        try:
            bundle = joblib.load(self.model_path)
            if bundle.get("schema_version") != SCHEMA_VERSION:
                logger.warning(
                    "Modelo salvo é de uma versão anterior (features diferentes); "
                    "rode o pipeline para re-treinar."
                )
                return False
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
        """Prevê o preço com intervalo de ~90% calibrado (conformal, multiplicativo)."""
        if not self.is_ready:
            raise RuntimeError("Modelo ainda não foi treinado/carregado.")

        row = pd.DataFrame(
            [{"area": area, "rooms": rooms, "bathrooms": bathrooms, "city": city,
              "neighborhood": neighborhood}]
        )
        # log(R$/m²) previsto + log(área) = log(preço)
        log_pred = float(self.model.predict(self._matrix(row))[0]) + math.log(area)
        q = float(self.metadata.get("conformal_log_q", 0.0))

        point = math.exp(log_pred)
        known_city, known_hood = (
            set(cats) for cats in self.encoder.categories_
        )
        known_location = city in known_city and neighborhood in known_hood

        result = {
            "predicted_price": round(point, 2),
            "price_per_m2": round(point / area, 2) if area else None,
            "confidence_interval_low": round(math.exp(log_pred - q), 2),
            "confidence_interval_high": round(math.exp(log_pred + q), 2),
            "interval_coverage": self.metadata.get("interval_coverage", INTERVAL_COVERAGE),
            "model_name": self.metadata.get("model_name"),
            "model_r2": self.metadata.get("r2"),
            "model_mape": self.metadata.get("mape"),
            "baseline_mape": self.metadata.get("baseline_mape"),
            "trained_at": self.metadata.get("trained_at"),
            "known_location": known_location,
        }
        if not known_location:
            result["warning"] = (
                "Cidade/bairro não visto no treino: a estimativa é menos confiável."
            )
        return result


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
