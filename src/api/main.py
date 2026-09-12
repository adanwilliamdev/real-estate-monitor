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
from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from config.settings import settings
from src.auth.security import create_access_token, decode_access_token
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
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_pipeline_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """Protege endpoints que disparam trabalho pesado (scraping/ML síncronos).

    Só exige o header `X-API-Key` se `PIPELINE_API_KEY` estiver configurada
    no ambiente; caso contrário mantém o endpoint aberto (comportamento
    padrão, adequado para demo/estudo local).
    """
    if settings.PIPELINE_API_KEY and x_api_key != settings.PIPELINE_API_KEY:
        raise HTTPException(status_code=401, detail="X-API-Key inválida ou ausente.")

_cleaner = DataCleaner()
_analytics = RealEstateAnalytics()
_investment = InvestmentAnalyzer()

# -------------------- Autenticação --------------------
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """Exige um JWT válido (`Authorization: Bearer <token>`) e retorna o usuário."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")

    db = DatabaseManager()
    user = db.get_user_by_id(int(payload["sub"]))
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Usuário inválido ou inativo.")
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[dict]:
    """Como `get_current_user`, mas retorna `None` em vez de erro se não autenticado.

    Usado em endpoints que funcionam tanto para visitantes quanto para
    usuários logados (ex: `/alerts`, que mistura alertas globais e pessoais).
    """
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        return None
    db = DatabaseManager()
    return db.get_user_by_id(int(payload["sub"]))


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


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Mínimo de 8 caracteres")
    full_name: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class FavoriteRequest(BaseModel):
    source: Optional[str] = None
    source_id: Optional[str] = None
    price: Optional[float] = None
    area: Optional[float] = None
    rooms: Optional[int] = None
    bathrooms: Optional[int] = None
    address: Optional[str] = None
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    url: str
    note: Optional[str] = None


class SavedSearchRequest(BaseModel):
    name: str
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    min_area: Optional[float] = Field(None, ge=0)
    max_area: Optional[float] = Field(None, ge=0)
    min_rooms: Optional[int] = Field(None, ge=0)


# -------------------- Endpoints --------------------
@app.get("/", tags=["meta"])
def root():
    return {
        "name": "Real Estate Monitor API",
        "docs": "/docs",
        "endpoints": [
            "/health", "/listings", "/stats", "/cities", "/predict", "/investment",
            "/investment/opportunities", "/alerts", "/history/{city}", "/pipeline/run",
            "/auth/register", "/auth/login", "/auth/me",
            "/favorites", "/saved-searches",
        ],
    }


@app.get("/health", tags=["meta"])
def health():
    """Health check simples: confirma que a API sobe e consegue falar com o banco."""
    try:
        DatabaseManager()
        db_ok = True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Health check: falha ao conectar ao banco: {exc}")
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "unreachable",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/cities", tags=["meta"])
def cities():
    return {"cities": VALID_CITIES}


# -------------------- Autenticação --------------------
@app.post("/auth/register", tags=["auth"], response_model=TokenResponse, status_code=201)
def register(req: UserRegisterRequest):
    db = DatabaseManager()
    try:
        user = db.create_user(email=req.email, password=req.password, full_name=req.full_name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    token = create_access_token(subject=str(user["id"]))
    return TokenResponse(access_token=token)


@app.post("/auth/login", tags=["auth"], response_model=TokenResponse)
def login(req: UserLoginRequest):
    db = DatabaseManager()
    user = db.authenticate_user(email=req.email, password=req.password)
    if not user:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    token = create_access_token(subject=str(user["id"]))
    return TokenResponse(access_token=token)


@app.get("/auth/me", tags=["auth"])
def me(current_user: dict = Depends(get_current_user)):
    return current_user


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
def get_alerts(
    unread_only: bool = False,
    limit: int = Query(50, le=500),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """Alertas de mercado. Sem autenticação, retorna só os alertas globais;
    autenticado, inclui também os alertas pessoais gerados pelas suas
    buscas salvas (veja `/saved-searches`)."""
    db = DatabaseManager()
    user_id = current_user["id"] if current_user else None
    df = db.get_alerts(unread_only=unread_only, limit=limit, user_id=user_id)
    return df.to_dict(orient="records")


@app.get("/history/{city}", tags=["historico"])
def get_history(city: str):
    db = DatabaseManager()
    df = db.get_snapshots(city=city)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Sem histórico para '{city}' ainda.")
    return df.to_dict(orient="records")


@app.post("/pipeline/run", tags=["pipeline"], dependencies=[Depends(require_pipeline_api_key)])
def trigger_pipeline(req: PipelineRunRequest):
    """Dispara uma execução síncrona do pipeline (coleta + limpeza + ML + alertas).

    Protegido por `X-API-Key` quando `PIPELINE_API_KEY` está definida no
    ambiente, já que roda scraping e treino de ML de forma síncrona e pode
    ser custoso/abusável se exposto publicamente sem controle.
    """
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


# -------------------- Favoritos --------------------
@app.get("/favorites", tags=["favoritos"])
def list_favorites(current_user: dict = Depends(get_current_user)):
    db = DatabaseManager()
    df = db.get_favorites(user_id=current_user["id"])
    return df.to_dict(orient="records")


@app.post("/favorites", tags=["favoritos"], status_code=201)
def add_favorite(req: FavoriteRequest, current_user: dict = Depends(get_current_user)):
    db = DatabaseManager()
    result = db.add_favorite(user_id=current_user["id"], listing=req.model_dump(), note=req.note)
    return result


@app.delete("/favorites/{favorite_id}", tags=["favoritos"])
def remove_favorite(favorite_id: int, current_user: dict = Depends(get_current_user)):
    db = DatabaseManager()
    removed = db.remove_favorite(user_id=current_user["id"], favorite_id=favorite_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Favorito não encontrado.")
    return {"removed": True}


# -------------------- Buscas salvas (alertas pessoais) --------------------
@app.get("/saved-searches", tags=["buscas salvas"])
def list_saved_searches(current_user: dict = Depends(get_current_user)):
    db = DatabaseManager()
    df = db.get_saved_searches(user_id=current_user["id"])
    return df.to_dict(orient="records")


@app.post("/saved-searches", tags=["buscas salvas"], status_code=201)
def add_saved_search(req: SavedSearchRequest, current_user: dict = Depends(get_current_user)):
    db = DatabaseManager()
    result = db.add_saved_search(user_id=current_user["id"], **req.model_dump(exclude={"name"}), name=req.name)
    return result


@app.delete("/saved-searches/{search_id}", tags=["buscas salvas"])
def remove_saved_search(search_id: int, current_user: dict = Depends(get_current_user)):
    db = DatabaseManager()
    removed = db.delete_saved_search(user_id=current_user["id"], search_id=search_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Busca salva não encontrada.")
    return {"removed": True}
