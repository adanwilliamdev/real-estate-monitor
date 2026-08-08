"""
src/api/main.py

API REST do Real Estate Monitor, construída com FastAPI. Expõe os mesmos
dados e análises do dashboard Streamlit para consumo programático
(integrações, apps externos, automações).

Rodar com:
    python main.py api
    # ou diretamente:
    uvicorn src.api.main:app --reload --port 8000

Docs interativas automáticas em /docs (Swagger) e /redoc.
"""
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.data_ingestion.demo_data import VALID_CITIES
from src.data_processing.analytics import RealEstateAnalytics
from src.data_processing.cleaner import DataCleaner
from src.data_processing.investment import InvestmentAnalyzer
from src.data_processing.ml_models import PricePredictionModel
from src.data_storage.database import DatabaseManager
from src.logging_setup import logger
from src.orchestration.pipeline import run_pipeline

app = FastAPI(
    title="Real Estate Monitor API",
    description="API para consulta de anúncios, estatísticas, previsão de preços "
    "e análise de investimento imobiliário.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_cleaner = DataCleaner()
_analytics = RealEstateAnalytics()
_investment = InvestmentAnalyzer()


def _get_clean_df(city: Optional[str] = None) -> pd.DataFrame:
    db = DatabaseManager()
    df = db.get_listings(city=city)
    if df.empty:
        return df
    return _cleaner.clean_listings(df)


# -------------------- Schemas --------------------
class PredictionRequest(BaseModel):
    area: float = Field(..., gt=0, description="Área em m²")
    rooms: int = Field(..., ge=0, description="Número de quartos")
    bathrooms: int = Field(1, ge=0, description="Número de banheiros")
    city: str = Field(..., description="Cidade (nome de exibição, ex: 'São Paulo')")
    neighborhood: str = Field(..., description="Bairro")


class InvestmentRequest(BaseModel):
    price: float = Field(..., gt=0)
    city: str
    area: Optional[float] = Field(None, gt=0)


class PipelineRunRequest(BaseModel):
    city: str = "sao-paulo"
    source: str = "demo"
    n_listings: int = Field(300, gt=0, le=5000)


# -------------------- Endpoints --------------------
@app.get("/", tags=["meta"])
def root():
    return {
        "name": "Real Estate Monitor API",
        "docs": "/docs",
        "endpoints": [
            "/listings", "/stats", "/cities", "/predict", "/investment",
            "/investment/opportunities", "/alerts", "/history/{city}", "/pipeline/run",
        ],
    }


@app.get("/cities", tags=["meta"])
def cities():
    return {"cities": VALID_CITIES}


@app.get("/listings", tags=["dados"])
def get_listings(
    city: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = Query(100, le=2000),
):
    df = _get_clean_df(city=city)
    if df.empty:
        return {"count": 0, "listings": []}

    if min_price is not None:
        df = df[df["price"] >= min_price]
    if max_price is not None:
        df = df[df["price"] <= max_price]

    df = df.head(limit)
    return {"count": len(df), "listings": df.to_dict(orient="records")}


@app.get("/stats", tags=["dados"])
def get_stats(city: Optional[str] = None):
    df = _get_clean_df(city=city)
    if df.empty:
        raise HTTPException(status_code=404, detail="Sem dados. Rode o pipeline primeiro.")
    return _cleaner.calculate_market_metrics(df)


@app.get("/neighborhoods", tags=["dados"])
def get_neighborhood_stats(city: Optional[str] = None):
    df = _get_clean_df(city=city)
    if df.empty:
        raise HTTPException(status_code=404, detail="Sem dados. Rode o pipeline primeiro.")
    stats = _cleaner.calculate_neighborhood_stats(df)
    return stats.reset_index().to_dict(orient="records")


@app.post("/predict", tags=["ml"])
def predict_price(req: PredictionRequest):
    model = PricePredictionModel()
    if not model.load():
        raise HTTPException(
            status_code=503,
            detail="Modelo de previsão ainda não foi treinado. Rode o pipeline primeiro "
            "(python main.py scrape) ou POST /pipeline/run.",
        )
    try:
        return model.predict(
            area=req.area,
            rooms=req.rooms,
            bathrooms=req.bathrooms,
            city=req.city,
            neighborhood=req.neighborhood,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/investment", tags=["investimento"])
def investment_analysis(req: InvestmentRequest):
    df = _get_clean_df(city=req.city)
    market_price_per_m2 = float(df["price_per_m2"].mean()) if not df.empty else None
    try:
        result = _investment.analyze(
            price=req.price, city=req.city, area=req.area,
            market_price_per_m2=market_price_per_m2,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.__dict__


@app.get("/investment/opportunities", tags=["investimento"])
def investment_opportunities(city: Optional[str] = None, top_n: int = Query(10, le=50)):
    df = _get_clean_df(city=city)
    if df.empty:
        raise HTTPException(status_code=404, detail="Sem dados. Rode o pipeline primeiro.")
    ranked = _investment.rank_best_opportunities(df, top_n=top_n)
    return ranked.to_dict(orient="records")


@app.get("/alerts", tags=["alertas"])
def get_alerts(unread_only: bool = False, limit: int = Query(50, le=500)):
    db = DatabaseManager()
    df = db.get_alerts(unread_only=unread_only, limit=limit)
    return df.to_dict(orient="records")


@app.get("/history/{city}", tags=["historico"])
def get_history(city: str):
    db = DatabaseManager()
    df = db.get_snapshots(city=city)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Sem histórico para '{city}' ainda.")
    return df.to_dict(orient="records")


@app.post("/pipeline/run", tags=["pipeline"])
def trigger_pipeline(req: PipelineRunRequest):
    """Dispara uma execução síncrona do pipeline (coleta + limpeza + ML + alertas)."""
    try:
        result = run_pipeline(city=req.city, source=req.source, n_listings=req.n_listings)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Erro ao rodar pipeline via API: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "scraped_count": result.get("scraped_count", 0),
        "saved_count": result.get("saved_count", 0),
        "alerts_generated": len(result.get("alerts", [])),
        "model": result.get("model", {}),
    }
