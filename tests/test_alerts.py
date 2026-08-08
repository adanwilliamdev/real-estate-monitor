import pandas as pd
import pytest

from src.alerts.alert_engine import AlertEngine
from src.data_storage.database import DatabaseManager


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "alerts_test.db"
    return DatabaseManager(db_url=f"sqlite:///{db_path}")


def _df(city="São Paulo", price_per_m2=8000, n=20, anomaly_ratio=0.0):
    n_anomalies = int(n * anomaly_ratio)
    return pd.DataFrame(
        {
            "city": [city] * n,
            "neighborhood": ["Centro"] * n,
            "price": [price_per_m2 * 70] * n,
            "area": [70] * n,
            "price_per_m2": [price_per_m2] * n,
            "is_anomaly": [True] * n_anomalies + [False] * (n - n_anomalies),
        }
    )


class TestDatabaseSnapshotsAndAlerts:
    def test_save_and_get_snapshot(self, temp_db):
        df = _df()
        saved = temp_db.save_snapshot(df)
        assert saved > 0
        snapshots = temp_db.get_snapshots(city="São Paulo")
        assert not snapshots.empty

    def test_save_and_get_alerts(self, temp_db):
        alerts = [{"severity": "warning", "category": "price_spike", "city": "São Paulo",
                    "message": "teste", "value": 10.0}]
        saved = temp_db.save_alerts(alerts)
        assert saved == 1
        df = temp_db.get_alerts()
        assert len(df) == 1
        assert df.iloc[0]["category"] == "price_spike"

    def test_mark_alerts_read(self, temp_db):
        temp_db.save_alerts([{"severity": "info", "category": "x", "message": "m"}])
        updated = temp_db.mark_alerts_read()
        assert updated == 1
        unread = temp_db.get_alerts(unread_only=True)
        assert unread.empty


class TestAlertEngine:
    def test_no_alerts_without_history(self, temp_db):
        engine = AlertEngine()
        alerts = engine.evaluate(_df(), temp_db)
        # sem snapshot anterior, não há comparação de preço possível
        assert all(a["category"] != "price_spike" for a in alerts)

    def test_price_spike_detected_after_history(self, temp_db):
        engine = AlertEngine(price_change_threshold=0.05)
        # primeira coleta estabelece histórico
        first = _df(price_per_m2=8000)
        temp_db.save_snapshot(first)

        # segunda coleta com alta relevante de preço
        second = _df(price_per_m2=9500)
        alerts = engine.evaluate(second, temp_db)
        assert any(a["category"] == "price_spike" for a in alerts)

    def test_anomaly_spike_detected(self, temp_db):
        engine = AlertEngine(anomaly_ratio_threshold=0.1)
        df = _df(anomaly_ratio=0.5)
        alerts = engine.evaluate(df, temp_db)
        assert any(a["category"] == "anomaly_spike" for a in alerts)
