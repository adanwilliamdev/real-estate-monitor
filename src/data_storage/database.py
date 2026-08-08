"""
src/data_storage/database.py

Camada de persistência via SQLAlchemy. Usa SQLite por padrão (zero
configuração, funciona em qualquer ambiente) e suporta Postgres apenas
trocando DATABASE_URL no .env. Estatísticas agregadas são calculadas com
SQL puro sobre o mesmo engine (sem depender de DuckDB).

Além da tabela principal de anúncios, mantém:
- `market_snapshots`: um resumo agregado (cidade/bairro) a cada execução
  do pipeline, permitindo reconstruir séries temporais de preço mesmo
  quando `property_listings` é substituída a cada coleta.
- `alerts`: eventos gerados pelo `AlertEngine` (queda/alta de preço,
  picos de anomalias, etc.), consultáveis pelo dashboard e pela API.
"""
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import settings
from src.logging_setup import logger

Base = declarative_base()


class PropertyListing(Base):
    __tablename__ = "property_listings"

    id = Column(Integer, primary_key=True)
    source = Column(String(50))
    source_id = Column(String(100))
    price = Column(Float)
    area = Column(Float)
    rooms = Column(Integer)
    bedrooms = Column(Integer)
    bathrooms = Column(Integer)
    address = Column(String(500))
    city = Column(String(100))
    state = Column(String(2))
    neighborhood = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    url = Column(String(500))
    scraped_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MarketSnapshot(Base):
    """Resumo agregado (cidade + bairro) capturado a cada execução do pipeline.

    Serve de base para os gráficos de tendência histórica no dashboard,
    já que a tabela de anúncios é substituída a cada nova coleta.
    """

    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True)
    city = Column(String(100), index=True)
    neighborhood = Column(String(100), nullable=True)
    avg_price = Column(Float)
    median_price = Column(Float)
    avg_price_per_m2 = Column(Float)
    avg_area = Column(Float)
    listing_count = Column(Integer)
    captured_at = Column(DateTime, default=datetime.utcnow, index=True)


class Alert(Base):
    """Evento gerado pelo AlertEngine (variações de preço, anomalias, etc.)."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    severity = Column(String(20))  # info | warning | critical
    category = Column(String(50))  # price_drop | price_spike | anomaly_spike | ...
    city = Column(String(100), nullable=True)
    neighborhood = Column(String(100), nullable=True)
    message = Column(Text)
    value = Column(Float, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class DatabaseManager:
    """Gerencia todas as operações de banco de dados do monitor imobiliário."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or settings.DATABASE_URL
        connect_args = {"check_same_thread": False} if self.db_url.startswith("sqlite") else {}
        self.engine = create_engine(self.db_url, connect_args=connect_args)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save_listings(self, df: pd.DataFrame) -> int:
        """Salva um DataFrame de anúncios no banco. Retorna quantos foram salvos."""
        if df is None or df.empty:
            logger.warning("save_listings recebeu DataFrame vazio, nada a salvar")
            return 0

        session = self.Session()
        count = 0
        try:
            for _, row in df.iterrows():
                listing = PropertyListing(
                    source=row.get("source", ""),
                    source_id=str(row.get("source_id", "")),
                    price=_safe_float(row.get("price")),
                    area=_safe_float(row.get("area")),
                    rooms=_safe_int(row.get("rooms")),
                    bedrooms=_safe_int(row.get("bedrooms")),
                    bathrooms=_safe_int(row.get("bathrooms")),
                    address=row.get("address"),
                    city=row.get("city"),
                    state=row.get("state"),
                    neighborhood=row.get("neighborhood"),
                    latitude=_safe_float(row.get("latitude")),
                    longitude=_safe_float(row.get("longitude")),
                    url=row.get("url"),
                    scraped_at=row.get("scraped_at") or datetime.utcnow(),
                )
                session.add(listing)
                count += 1
                if count % 200 == 0:
                    session.commit()

            session.commit()
            logger.info(f"Salvos {count} imóveis no banco de dados")
            return count

        except Exception as exc:  # noqa: BLE001
            session.rollback()
            logger.error(f"Erro ao salvar imóveis: {exc}")
            raise
        finally:
            session.close()

    def get_listings(
        self,
        city: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> pd.DataFrame:
        """Recupera imóveis do banco, com filtros opcionais."""
        with self.Session() as session:
            query = session.query(PropertyListing)
            if city:
                query = query.filter(PropertyListing.city.ilike(f"%{city}%"))
            if min_price is not None:
                query = query.filter(PropertyListing.price >= min_price)
            if max_price is not None:
                query = query.filter(PropertyListing.price <= max_price)

            df = pd.read_sql(query.statement, self.engine)
        return df

    def clear_listings(self) -> int:
        """Remove todos os registros da tabela (útil para re-popular com demo data)."""
        with self.Session() as session:
            deleted = session.query(PropertyListing).delete()
            session.commit()
        logger.info(f"Removidos {deleted} registros existentes")
        return deleted

    # -------------------- Market snapshots (histórico) --------------------
    def save_snapshot(self, df: pd.DataFrame) -> int:
        """Grava um resumo agregado (cidade+bairro) do estado atual do mercado.

        Chamado a cada execução do pipeline para construir uma série
        temporal, mesmo que `property_listings` seja substituída.
        """
        if df is None or df.empty:
            return 0

        session = self.Session()
        count = 0
        try:
            now = datetime.utcnow()
            group_cols = [c for c in ["city", "neighborhood"] if c in df.columns]
            if not group_cols:
                return 0

            grouped = df.groupby(group_cols).agg(
                avg_price=("price", "mean"),
                median_price=("price", "median"),
                avg_price_per_m2=("price_per_m2", "mean"),
                avg_area=("area", "mean"),
                listing_count=("price", "count"),
            ).reset_index()

            for _, row in grouped.iterrows():
                snap = MarketSnapshot(
                    city=row.get("city"),
                    neighborhood=row.get("neighborhood") if "neighborhood" in grouped.columns else None,
                    avg_price=_safe_float(row.get("avg_price")),
                    median_price=_safe_float(row.get("median_price")),
                    avg_price_per_m2=_safe_float(row.get("avg_price_per_m2")),
                    avg_area=_safe_float(row.get("avg_area")),
                    listing_count=_safe_int(row.get("listing_count")),
                    captured_at=now,
                )
                session.add(snap)
                count += 1

            # snapshot agregado por cidade (sem quebra por bairro), útil p/ gráficos gerais
            city_grouped = df.groupby("city").agg(
                avg_price=("price", "mean"),
                median_price=("price", "median"),
                avg_price_per_m2=("price_per_m2", "mean"),
                avg_area=("area", "mean"),
                listing_count=("price", "count"),
            ).reset_index()
            for _, row in city_grouped.iterrows():
                snap = MarketSnapshot(
                    city=row.get("city"),
                    neighborhood=None,
                    avg_price=_safe_float(row.get("avg_price")),
                    median_price=_safe_float(row.get("median_price")),
                    avg_price_per_m2=_safe_float(row.get("avg_price_per_m2")),
                    avg_area=_safe_float(row.get("avg_area")),
                    listing_count=_safe_int(row.get("listing_count")),
                    captured_at=now,
                )
                session.add(snap)
                count += 1

            session.commit()
            logger.info(f"Snapshot de mercado salvo ({count} linhas)")
            return count
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            logger.error(f"Erro ao salvar snapshot: {exc}")
            return 0
        finally:
            session.close()

    def get_snapshots(
        self, city: Optional[str] = None, neighborhood_level: bool = False
    ) -> pd.DataFrame:
        """Recupera a série histórica de snapshots (para gráficos de tendência)."""
        with self.Session() as session:
            query = session.query(MarketSnapshot)
            if city:
                query = query.filter(MarketSnapshot.city.ilike(f"%{city}%"))
            if neighborhood_level:
                query = query.filter(MarketSnapshot.neighborhood.isnot(None))
            else:
                query = query.filter(MarketSnapshot.neighborhood.is_(None))
            query = query.order_by(MarketSnapshot.captured_at.asc())
            df = pd.read_sql(query.statement, self.engine)
        return df

    # -------------------- Alertas --------------------
    def save_alerts(self, alerts: List[Dict]) -> int:
        if not alerts:
            return 0
        session = self.Session()
        try:
            for a in alerts:
                session.add(
                    Alert(
                        severity=a.get("severity", "info"),
                        category=a.get("category", "general"),
                        city=a.get("city"),
                        neighborhood=a.get("neighborhood"),
                        message=a.get("message", ""),
                        value=_safe_float(a.get("value")),
                        created_at=datetime.utcnow(),
                    )
                )
            session.commit()
            logger.info(f"Salvos {len(alerts)} alertas")
            return len(alerts)
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            logger.error(f"Erro ao salvar alertas: {exc}")
            return 0
        finally:
            session.close()

    def get_alerts(self, unread_only: bool = False, limit: int = 100) -> pd.DataFrame:
        with self.Session() as session:
            query = session.query(Alert)
            if unread_only:
                query = query.filter(Alert.is_read.is_(False))
            query = query.order_by(Alert.created_at.desc()).limit(limit)
            df = pd.read_sql(query.statement, self.engine)
        return df

    def mark_alerts_read(self) -> int:
        with self.Session() as session:
            updated = session.query(Alert).filter(Alert.is_read.is_(False)).update(
                {"is_read": True}
            )
            session.commit()
        return updated

    def get_statistics(self) -> Dict:
        """Estatísticas agregadas via SQL, direto no engine configurado."""
        with self.engine.connect() as conn:
            row = conn.execute(
                select(
                    func.count(PropertyListing.id).label("total_listings"),
                    func.avg(PropertyListing.price).label("avg_price"),
                    func.avg(PropertyListing.area).label("avg_area"),
                    func.min(PropertyListing.price).label("min_price"),
                    func.max(PropertyListing.price).label("max_price"),
                    func.count(func.distinct(PropertyListing.city)).label("total_cities"),
                )
            ).fetchone()

        if row is None or row.total_listings == 0:
            return {
                "total_listings": 0, "avg_price": 0, "avg_area": 0,
                "avg_price_per_m2": 0, "min_price": 0, "max_price": 0,
                "total_cities": 0,
            }

        avg_price_per_m2 = (row.avg_price / row.avg_area) if row.avg_area else 0
        return {
            "total_listings": row.total_listings,
            "avg_price": row.avg_price or 0,
            "avg_area": row.avg_area or 0,
            "avg_price_per_m2": avg_price_per_m2,
            "min_price": row.min_price or 0,
            "max_price": row.max_price or 0,
            "total_cities": row.total_cities or 0,
        }


def _safe_float(value) -> Optional[float]:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> Optional[int]:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
