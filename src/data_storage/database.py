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
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import settings
from src.auth.security import hash_password, verify_password
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
    # Nulo = alerta global de mercado (visível para todos). Preenchido =
    # alerta pessoal, gerado a partir de uma `SavedSearch` do usuário.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    saved_search_id = Column(Integer, ForeignKey("saved_searches.id"), nullable=True)


class User(Base):
    """Conta de usuário do dashboard/API (favoritos e alertas pessoais)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Favorite(Base):
    """Imóvel salvo por um usuário.

    Guarda uma "fotografia" dos dados do anúncio no momento em que foi
    favoritado (preço, área, bairro, url, etc.), em vez de só uma
    referência ao id em `property_listings` — essa tabela é substituída a
    cada execução do pipeline (`clear_listings`), então uma referência por
    id se perderia na coleta seguinte.
    """

    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "url", name="uq_favorite_user_url"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source = Column(String(50), nullable=True)
    source_id = Column(String(100), nullable=True)
    price = Column(Float, nullable=True)
    area = Column(Float, nullable=True)
    rooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    neighborhood = Column(String(100), nullable=True)
    url = Column(String(500), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SavedSearch(Base):
    """Critério de busca salvo por um usuário ("alerta pessoal").

    A cada execução do pipeline, o `AlertEngine` compara os anúncios
    coletados contra os critérios ativos e gera um `Alert` pessoal
    (`user_id` preenchido) quando encontra imóveis compatíveis novos.
    """

    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    city = Column(String(100), nullable=True)
    neighborhood = Column(String(100), nullable=True)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    min_area = Column(Float, nullable=True)
    max_area = Column(Float, nullable=True)
    min_rooms = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    last_match_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


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
                        user_id=a.get("user_id"),
                        saved_search_id=a.get("saved_search_id"),
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

    def get_alerts(
        self,
        unread_only: bool = False,
        limit: int = 100,
        user_id: Optional[int] = None,
        include_global: bool = True,
    ) -> pd.DataFrame:
        """Recupera alertas.

        - `user_id=None`: apenas alertas globais de mercado (comportamento
          original, usado por quem não está autenticado).
        - `user_id=<id>`: alertas pessoais desse usuário; se
          `include_global=True` (padrão), também inclui os globais.
        """
        with self.Session() as session:
            query = session.query(Alert)
            if user_id is None:
                query = query.filter(Alert.user_id.is_(None))
            elif include_global:
                query = query.filter(
                    (Alert.user_id == user_id) | (Alert.user_id.is_(None))
                )
            else:
                query = query.filter(Alert.user_id == user_id)

            if unread_only:
                query = query.filter(Alert.is_read.is_(False))
            query = query.order_by(Alert.created_at.desc()).limit(limit)
            df = pd.read_sql(query.statement, self.engine)
        return df

    def mark_alerts_read(self, user_id: Optional[int] = None) -> int:
        """Marca alertas como lidos. Se `user_id` for passado, restringe aos
        alertas pessoais desse usuário; caso contrário, marca os globais."""
        with self.Session() as session:
            query = session.query(Alert).filter(Alert.is_read.is_(False))
            query = query.filter(Alert.user_id == user_id) if user_id is not None else query.filter(
                Alert.user_id.is_(None)
            )
            updated = query.update({"is_read": True})
            session.commit()
        return updated

    # -------------------- Usuários (autenticação) --------------------
    def create_user(self, email: str, password: str, full_name: Optional[str] = None) -> Dict:
        """Cria um novo usuário. Lança `ValueError` se o e-mail já existir."""
        session = self.Session()
        try:
            user = User(
                email=email.strip().lower(),
                hashed_password=hash_password(password),
                full_name=full_name,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return {
                "id": user.id, "email": user.email, "full_name": user.full_name,
                "created_at": user.created_at,
            }
        except IntegrityError:
            session.rollback()
            raise ValueError(f"E-mail '{email}' já está cadastrado.")
        finally:
            session.close()

    def authenticate_user(self, email: str, password: str) -> Optional[Dict]:
        """Confere e-mail/senha. Retorna os dados do usuário ou `None` se inválido."""
        with self.Session() as session:
            user = session.query(User).filter(User.email == email.strip().lower()).first()
            if not user or not user.is_active:
                return None
            if not verify_password(password, user.hashed_password):
                return None
            return {"id": user.id, "email": user.email, "full_name": user.full_name}

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        with self.Session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            return {
                "id": user.id, "email": user.email, "full_name": user.full_name,
                "is_active": user.is_active, "created_at": user.created_at,
            }

    # -------------------- Favoritos --------------------
    def add_favorite(self, user_id: int, listing: Dict, note: Optional[str] = None) -> Dict:
        """Salva um imóvel como favorito de um usuário (idempotente por URL)."""
        session = self.Session()
        try:
            existing = None
            url = listing.get("url")
            if url:
                existing = (
                    session.query(Favorite)
                    .filter(Favorite.user_id == user_id, Favorite.url == url)
                    .first()
                )
            if existing:
                return {"id": existing.id, "already_existed": True}

            fav = Favorite(
                user_id=user_id,
                source=listing.get("source"),
                source_id=str(listing.get("source_id", "")) or None,
                price=_safe_float(listing.get("price")),
                area=_safe_float(listing.get("area")),
                rooms=_safe_int(listing.get("rooms")),
                bathrooms=_safe_int(listing.get("bathrooms")),
                address=listing.get("address"),
                city=listing.get("city"),
                neighborhood=listing.get("neighborhood"),
                url=url,
                note=note,
            )
            session.add(fav)
            session.commit()
            session.refresh(fav)
            return {"id": fav.id, "already_existed": False}
        except IntegrityError:
            session.rollback()
            existing = (
                session.query(Favorite)
                .filter(Favorite.user_id == user_id, Favorite.url == listing.get("url"))
                .first()
            )
            return {"id": existing.id if existing else None, "already_existed": True}
        finally:
            session.close()

    def get_favorites(self, user_id: int) -> pd.DataFrame:
        with self.Session() as session:
            query = (
                session.query(Favorite)
                .filter(Favorite.user_id == user_id)
                .order_by(Favorite.created_at.desc())
            )
            df = pd.read_sql(query.statement, self.engine)
        return df

    def remove_favorite(self, user_id: int, favorite_id: int) -> bool:
        with self.Session() as session:
            deleted = (
                session.query(Favorite)
                .filter(Favorite.id == favorite_id, Favorite.user_id == user_id)
                .delete()
            )
            session.commit()
        return bool(deleted)

    # -------------------- Buscas salvas (alertas pessoais) --------------------
    def add_saved_search(self, user_id: int, **criteria) -> Dict:
        session = self.Session()
        try:
            search = SavedSearch(user_id=user_id, **criteria)
            session.add(search)
            session.commit()
            session.refresh(search)
            return {"id": search.id}
        finally:
            session.close()

    def get_saved_searches(self, user_id: int, active_only: bool = False) -> pd.DataFrame:
        with self.Session() as session:
            query = session.query(SavedSearch).filter(SavedSearch.user_id == user_id)
            if active_only:
                query = query.filter(SavedSearch.is_active.is_(True))
            query = query.order_by(SavedSearch.created_at.desc())
            df = pd.read_sql(query.statement, self.engine)
        return df

    def get_all_active_saved_searches(self) -> pd.DataFrame:
        """Todas as buscas salvas ativas de todos os usuários — usado pelo
        `AlertEngine` a cada execução do pipeline para gerar alertas pessoais."""
        with self.Session() as session:
            query = session.query(SavedSearch).filter(SavedSearch.is_active.is_(True))
            df = pd.read_sql(query.statement, self.engine)
        return df

    def update_saved_search_match_count(self, search_id: int, count: int) -> None:
        with self.Session() as session:
            session.query(SavedSearch).filter(SavedSearch.id == search_id).update(
                {"last_match_count": count}
            )
            session.commit()

    def delete_saved_search(self, user_id: int, search_id: int) -> bool:
        with self.Session() as session:
            deleted = (
                session.query(SavedSearch)
                .filter(SavedSearch.id == search_id, SavedSearch.user_id == user_id)
                .delete()
            )
            session.commit()
        return bool(deleted)

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
