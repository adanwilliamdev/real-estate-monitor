"""
src/data_processing/lifecycle.py

Ciclo de vida dos anúncios entre duas coletas: o que é **novo**, o que
**saiu do ar** (vendido/retirado) e o que **mudou de preço**.

É isso que transforma o projeto de um "retrato do mercado" em um monitor:
sem comparar a coleta atual com a anterior, não existe o conceito de
imóvel novo ou de redução de preço.

Pontos de atenção tratados aqui:

- **Chave estável** do anúncio: `source|source_id`; se faltar, `url`; se
  faltar, `address`.
- **Primeira coleta** não gera eventos: sem coleta anterior, "todos são
  novos" não é informação.
- **Limiar de ruído**: variações menores que `price_change_threshold` (3%)
  são ignoradas, e variações maiores que `max_change` (50%) são tratadas como
  suspeitas (reanúncio, erro de digitação ou efeito do tratamento de
  outliers), não como queda/alta real.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
import pandas as pd

_MISSING_TOKENS = {"", "nan", "none", "null", "<na>"}


def _clean_text(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.strip()
    return s.mask(s.str.lower().isin(_MISSING_TOKENS))


def listing_key(df: pd.DataFrame) -> pd.Series:
    """Chave estável por anúncio (índice alinhado ao de `df`)."""
    idx = df.index
    na = pd.Series(pd.NA, index=idx, dtype="string")
    source = _clean_text(df["source"]) if "source" in df.columns else na
    source_id = _clean_text(df["source_id"]) if "source_id" in df.columns else na
    url = _clean_text(df["url"]) if "url" in df.columns else na
    address = _clean_text(df["address"]) if "address" in df.columns else na

    k1 = (source + "|" + source_id).where(source.notna() & source_id.notna())
    return k1.combine_first(url).combine_first(address)


@dataclass
class LifecycleDiff:
    new: pd.DataFrame = field(default_factory=pd.DataFrame)
    removed: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_drops: pd.DataFrame = field(default_factory=pd.DataFrame)
    price_increases: pd.DataFrame = field(default_factory=pd.DataFrame)
    unchanged: int = 0
    ignored_large_changes: int = 0
    is_first_snapshot: bool = False

    def counts(self) -> Dict[str, int]:
        return {
            "new": len(self.new),
            "removed": len(self.removed),
            "price_drops": len(self.price_drops),
            "price_increases": len(self.price_increases),
            "unchanged": self.unchanged,
            "ignored_large_changes": self.ignored_large_changes,
        }


_CHANGE_COLUMNS = [
    "key", "city", "neighborhood", "address", "url",
    "previous_price", "current_price", "change_pct",
]


def diff_listings(
    previous: pd.DataFrame,
    current: pd.DataFrame,
    price_change_threshold: float = 0.03,
    max_change: float = 0.50,
) -> LifecycleDiff:
    """Compara duas coletas e devolve os eventos de ciclo de vida."""
    if current is None or current.empty:
        return LifecycleDiff()
    if previous is None or previous.empty:
        return LifecycleDiff(is_first_snapshot=True, unchanged=0)

    prev = previous.copy()
    cur = current.copy()
    prev["key"] = listing_key(prev)
    cur["key"] = listing_key(cur)
    prev = prev[prev["key"].notna()].drop_duplicates("key")
    cur = cur[cur["key"].notna()].drop_duplicates("key")

    prev_keys, cur_keys = set(prev["key"]), set(cur["key"])
    new = cur[~cur["key"].isin(prev_keys)].reset_index(drop=True)
    removed = prev[~prev["key"].isin(cur_keys)].reset_index(drop=True)

    both = cur.merge(
        prev[["key", "price"]].rename(columns={"price": "previous_price"}),
        on="key",
        how="inner",
    ).rename(columns={"price": "current_price"})

    both = both[(both["previous_price"] > 0) & both["current_price"].notna()].copy()
    both["change_pct"] = (both["current_price"] - both["previous_price"]) / both["previous_price"] * 100

    thr = price_change_threshold * 100
    cap = max_change * 100
    large = both["change_pct"].abs() > cap
    real = both[~large]
    drops = real[real["change_pct"] <= -thr]
    rises = real[real["change_pct"] >= thr]

    def _shape(frame: pd.DataFrame, ascending: bool) -> pd.DataFrame:
        for col in _CHANGE_COLUMNS:
            if col not in frame.columns:
                frame = frame.assign(**{col: None})
        return frame[_CHANGE_COLUMNS].sort_values("change_pct", ascending=ascending).reset_index(drop=True)

    return LifecycleDiff(
        new=new,
        removed=removed,
        price_drops=_shape(drops, ascending=True),
        price_increases=_shape(rises, ascending=False),
        unchanged=int(len(real) - len(drops) - len(rises)),
        ignored_large_changes=int(large.sum()),
        is_first_snapshot=False,
    )


# --------------------------------------------------------------------------
# Eventos -> alertas (dicts prontos para `DatabaseManager.save_alerts`)
# --------------------------------------------------------------------------
def lifecycle_alerts(diff: LifecycleDiff) -> List[Dict]:
    """Um alerta por tipo de evento e por cidade (evita inundar o painel)."""
    alerts: List[Dict] = []
    if diff is None or diff.is_first_snapshot:
        return alerts

    if not diff.price_drops.empty:
        for city, grp in diff.price_drops.groupby("city", dropna=True):
            biggest = grp.iloc[0]  # já ordenado: maior queda primeiro
            alerts.append(
                {
                    "severity": "info",
                    "category": "listing_price_drop",
                    "city": city,
                    "neighborhood": biggest.get("neighborhood"),
                    "message": (
                        f"{len(grp)} imóvel(is) em {city} reduziram o preço "
                        f"(média {grp['change_pct'].mean():.1f}%). Maior queda: "
                        f"{biggest.get('neighborhood') or 'N/D'} {biggest['change_pct']:.1f}% "
                        f"(R$ {biggest['previous_price']:,.0f} → R$ {biggest['current_price']:,.0f})."
                    ),
                    "value": float(len(grp)),
                }
            )

    if not diff.new.empty and "city" in diff.new.columns:
        for city, grp in diff.new.groupby("city", dropna=True):
            alerts.append(
                {
                    "severity": "info",
                    "category": "new_listings",
                    "city": city,
                    "message": f"{len(grp)} novo(s) imóvel(is) anunciado(s) em {city} desde a última coleta.",
                    "value": float(len(grp)),
                }
            )

    if not diff.removed.empty and "city" in diff.removed.columns:
        for city, grp in diff.removed.groupby("city", dropna=True):
            alerts.append(
                {
                    "severity": "info",
                    "category": "removed_listings",
                    "city": city,
                    "message": (
                        f"{len(grp)} anúncio(s) em {city} saíram do ar desde a última coleta "
                        "(vendidos ou retirados)."
                    ),
                    "value": float(len(grp)),
                }
            )
    return alerts
