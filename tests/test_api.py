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


class TestAuthFlow:
    """Registro, login e acesso a rotas protegidas (favoritos/buscas salvas)."""

    def _register_and_login(self, client, email="user@example.com", password="senhaSegura1"):
        resp = client.post("/auth/register", json={"email": email, "password": password})
        assert resp.status_code == 201
        return resp.json()["access_token"]

    def _auth_header(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_register_and_login(self, client):
        token = self._register_and_login(client, email="alice@example.com")
        assert token

        resp = client.post(
            "/auth/login", json={"email": "alice@example.com", "password": "senhaSegura1"}
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_with_wrong_password_fails(self, client):
        self._register_and_login(client, email="bob@example.com")
        resp = client.post("/auth/login", json={"email": "bob@example.com", "password": "errada"})
        assert resp.status_code == 401

    def test_duplicate_registration_fails(self, client):
        self._register_and_login(client, email="carol@example.com")
        resp = client.post(
            "/auth/register", json={"email": "carol@example.com", "password": "outraSenha1"}
        )
        assert resp.status_code == 409

    def test_me_requires_token(self, client):
        assert client.get("/auth/me").status_code == 401

    def test_me_returns_current_user(self, client):
        token = self._register_and_login(client, email="dave@example.com")
        resp = client.get("/auth/me", headers=self._auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "dave@example.com"

    def test_favorites_require_auth(self, client):
        assert client.get("/favorites").status_code == 401
        assert client.post("/favorites", json={"url": "https://x.com/1"}).status_code == 401

    def test_favorites_crud(self, client):
        token = self._register_and_login(client, email="erin@example.com")
        headers = self._auth_header(token)

        resp = client.post(
            "/favorites",
            json={"url": "https://x.com/imovel/1", "price": 500000, "city": "São Paulo"},
            headers=headers,
        )
        assert resp.status_code == 201
        favorite_id = resp.json()["id"]

        resp = client.get("/favorites", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = client.delete(f"/favorites/{favorite_id}", headers=headers)
        assert resp.status_code == 200
        assert client.get("/favorites", headers=headers).json() == []

    def test_saved_searches_crud(self, client):
        token = self._register_and_login(client, email="frank@example.com")
        headers = self._auth_header(token)

        resp = client.post(
            "/saved-searches",
            json={"name": "Apto em Pinheiros", "city": "São Paulo", "max_price": 700000},
            headers=headers,
        )
        assert resp.status_code == 201
        search_id = resp.json()["id"]

        resp = client.get("/saved-searches", headers=headers)
        assert resp.status_code == 200
        assert resp.json()[0]["name"] == "Apto em Pinheiros"

        resp = client.delete(f"/saved-searches/{search_id}", headers=headers)
        assert resp.status_code == 200

    def test_alerts_endpoint_works_with_and_without_auth(self, client):
        token = self._register_and_login(client, email="grace@example.com")
        assert client.get("/alerts").status_code == 200
        assert client.get("/alerts", headers=self._auth_header(token)).status_code == 200
