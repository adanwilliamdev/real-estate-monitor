import pytest
from fastapi.testclient import TestClient

from config.settings import settings
from src.orchestration.pipeline import run_pipeline


@pytest.fixture(scope="module", autouse=True)
def seeded_db(tmp_path_factory):
    """Popula um banco SQLite temporário com dados demo antes dos testes de API.

    A API usa `DatabaseManager()` sem argumentos (banco padrão do settings),
    então apontamos `settings.DATABASE_URL` para um arquivo temporário e
    rodamos o pipeline uma vez, garantindo isolamento do banco real do
    projeto e dados/modelo disponíveis durante a suíte.
    """
    db_path = tmp_path_factory.mktemp("api_db") / "test.db"
    original_url = settings.DATABASE_URL
    settings.DATABASE_URL = f"sqlite:///{db_path}"
    try:
        run_pipeline(city="sao-paulo", source="demo", n_listings=60, train_model=True)
        yield
    finally:
        settings.DATABASE_URL = original_url


@pytest.fixture
def client():
    from src.api.main import app

    return TestClient(app)


class TestAPI:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "endpoints" in resp.json()

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"

    def test_cities(self, client):
        resp = client.get("/cities")
        assert resp.status_code == 200
        assert "sao-paulo" in resp.json()["cities"]

    def test_listings(self, client):
        resp = client.get("/listings?limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] > 0

    def test_stats(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200
        assert resp.json()["total_listings"] > 0

    def test_predict(self, client):
        resp = client.post(
            "/predict",
            json={"area": 70, "rooms": 2, "bathrooms": 2, "city": "São Paulo", "neighborhood": "Pinheiros"},
        )
        assert resp.status_code == 200
        assert resp.json()["predicted_price"] > 0

    def test_investment(self, client):
        resp = client.post("/investment", json={"price": 700000, "city": "São Paulo", "area": 70})
        assert resp.status_code == 200
        assert resp.json()["estimated_monthly_rent"] > 0

    def test_investment_opportunities(self, client):
        resp = client.get("/investment/opportunities?top_n=5")
        assert resp.status_code == 200

    def test_history(self, client):
        resp = client.get("/history/São Paulo")
        assert resp.status_code == 200
        assert len(resp.json()) > 0

    def test_alerts(self, client):
        resp = client.get("/alerts")
        assert resp.status_code == 200


class TestPipelineApiKey:
    """POST /pipeline/run deve ficar aberto por padrão e só exigir
    X-API-Key quando PIPELINE_API_KEY estiver configurada no ambiente."""

    def test_open_by_default(self, client, monkeypatch):
        monkeypatch.setattr(settings, "PIPELINE_API_KEY", "")
        resp = client.post(
            "/pipeline/run", json={"city": "sao-paulo", "source": "demo", "n_listings": 40}
        )
        assert resp.status_code == 200

    def test_rejects_missing_key_when_configured(self, client, monkeypatch):
        monkeypatch.setattr(settings, "PIPELINE_API_KEY", "secret123")
        resp = client.post(
            "/pipeline/run", json={"city": "sao-paulo", "source": "demo", "n_listings": 40}
        )
        assert resp.status_code == 401

    def test_accepts_correct_key_when_configured(self, client, monkeypatch):
        monkeypatch.setattr(settings, "PIPELINE_API_KEY", "secret123")
        resp = client.post(
            "/pipeline/run",
            json={"city": "sao-paulo", "source": "demo", "n_listings": 40},
            headers={"X-API-Key": "secret123"},
        )
        assert resp.status_code == 200
