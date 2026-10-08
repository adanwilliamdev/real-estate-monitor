"""
src/data_processing/serialization.py

Conversão segura de DataFrames para estruturas JSON-serializáveis.
`DataFrame.to_dict()` mantém `NaN`/`NaT`, que o JSON padrão (e o FastAPI)
não aceitam; aqui eles viram `None`.
"""
from typing import Dict, List

import numpy as np
import pandas as pd


def df_to_records(df: pd.DataFrame) -> List[Dict]:
    """Lista de dicts com NaN/NaT/inf -> None e tipos numpy -> tipos nativos."""
    if df is None or df.empty:
        return []
    out: List[Dict] = []
    for rec in df.to_dict(orient="records"):
        clean: Dict = {}
        for key, value in rec.items():
            if isinstance(value, (np.floating, float)):
                value = None if (np.isnan(value) or np.isinf(value)) else float(value)
            elif isinstance(value, np.integer):
                value = int(value)
            elif isinstance(value, np.bool_):
                value = bool(value)
            elif isinstance(value, pd.Timestamp):
                value = None if pd.isna(value) else value.isoformat()
            elif value is pd.NaT:
                value = None
            clean[key] = value
        out.append(clean)
    return out
