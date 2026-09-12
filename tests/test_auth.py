import pandas as pd
import pytest

from config.settings import settings
from src.alerts.alert_engine import AlertEngine
from src.auth.security import create_access_token, decode_access_token, hash_password, verify_password
from src.data_storage.database import DatabaseManager


# -------------------- security.py --------------------
class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("minhaSenha123")
        assert hashed != "minhaSenha123"
        assert hashed.startswith("pbkdf2_sha256$")

    def test_verify_correct_password(self):
        hashed = hash_password("minhaSenha123")
        assert verify_password("minhaSenha123", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("minhaSenha123")
        assert verify_password("outraSenha", hashed) is False

    def test_two_hashes_of_same_password_differ(self):
        # salts aleatórios -> hashes diferentes mesmo para a mesma senha
        assert hash_password("abc12345") != hash_password("abc12345")


class TestTokens:
    def test_create_and_decode_token(self):
        token = create_access_token(subject="42")
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"

    def test_decode_invalid_token_returns_none(self):
        assert decode_access_token("token.invalido.aqui") is None

    def test_decode_token_signed_with_wrong_key(self):
        import jwt

        token = jwt.encode({"sub": "1"}, "outra-chave", algorithm=settings.JWT_ALGORITHM)
        assert decode_access_token(token) is None


# -------------------- DatabaseManager: usuários --------------------
@pytest.fixture
def db(tmp_path):
    return DatabaseManager(db_url=f"sqlite:///{tmp_path / 'auth_test.db'}")


class TestUserManagement:
    def test_create_and_authenticate_user(self, db):
        db.create_user(email="Ana@Example.com", password="senhaSegura1")
        # e-mail é normalizado para minúsculas na autenticação
        user = db.authenticate_user(email="ana@example.com", password="senhaSegura1")
        assert user is not None
        assert user["email"] == "ana@example.com"

    def test_duplicate_email_raises(self, db):
        db.create_user(email="dup@example.com", password="senhaSegura1")
        with pytest.raises(ValueError):
            db.create_user(email="dup@example.com", password="outraSenha1")

    def test_authenticate_wrong_password_returns_none(self, db):
        db.create_user(email="bob@example.com", password="senhaSegura1")
        assert db.authenticate_user(email="bob@example.com", password="errada") is None

    def test_get_user_by_id(self, db):
        created = db.create_user(email="carol@example.com", password="senhaSegura1")
        fetched = db.get_user_by_id(created["id"])
        assert fetched["email"] == "carol@example.com"


class TestFavorites:
    def test_add_and_list_favorite(self, db):
        user = db.create_user(email="fav@example.com", password="senhaSegura1")
        listing = {
            "url": "https://example.com/imovel/1",
            "price": 500000,
            "area": 80,
            "city": "São Paulo",
            "neighborhood": "Pinheiros",
        }
        result = db.add_favorite(user_id=user["id"], listing=listing)
        assert result["already_existed"] is False

        favorites = db.get_favorites(user_id=user["id"])
        assert len(favorites) == 1
        assert favorites.iloc[0]["neighborhood"] == "Pinheiros"

    def test_adding_same_url_twice_is_idempotent(self, db):
        user = db.create_user(email="fav2@example.com", password="senhaSegura1")
        listing = {"url": "https://example.com/imovel/2", "price": 300000}
        db.add_favorite(user_id=user["id"], listing=listing)
        result = db.add_favorite(user_id=user["id"], listing=listing)
        assert result["already_existed"] is True
        assert len(db.get_favorites(user_id=user["id"])) == 1

    def test_remove_favorite(self, db):
        user = db.create_user(email="fav3@example.com", password="senhaSegura1")
        added = db.add_favorite(user_id=user["id"], listing={"url": "https://example.com/3"})
        assert db.remove_favorite(user_id=user["id"], favorite_id=added["id"]) is True
        assert db.get_favorites(user_id=user["id"]).empty


class TestSavedSearches:
    def test_add_and_list_saved_search(self, db):
        user = db.create_user(email="search@example.com", password="senhaSegura1")
        db.add_saved_search(
            user_id=user["id"], name="Apto em Pinheiros", city="São Paulo",
            neighborhood="Pinheiros", max_price=600000,
        )
        searches = db.get_saved_searches(user_id=user["id"])
        assert len(searches) == 1
        assert searches.iloc[0]["name"] == "Apto em Pinheiros"

    def test_delete_saved_search(self, db):
        user = db.create_user(email="search2@example.com", password="senhaSegura1")
        created = db.add_saved_search(user_id=user["id"], name="Qualquer imóvel")
        assert db.delete_saved_search(user_id=user["id"], search_id=created["id"]) is True
        assert db.get_saved_searches(user_id=user["id"]).empty


class TestPersonalAlerts:
    def test_saved_search_generates_personal_alert_on_match(self, db):
        user = db.create_user(email="alerts@example.com", password="senhaSegura1")
        db.add_saved_search(
            user_id=user["id"], name="Barato em Pinheiros", city="São Paulo",
            neighborhood="Pinheiros", max_price=400000,
        )
        df = pd.DataFrame(
            {
                "city": ["São Paulo", "São Paulo", "Rio de Janeiro"],
                "neighborhood": ["Pinheiros", "Moema", "Copacabana"],
                "price": [350000, 900000, 500000],
                "area": [60, 100, 70],
            }
        )
        engine = AlertEngine()
        alerts = engine.evaluate_saved_searches(df, db)

        assert len(alerts) == 1
        assert alerts[0]["user_id"] == user["id"]
        assert alerts[0]["category"] == "saved_search_match"

        personal = db.get_alerts(user_id=user["id"])
        assert len(personal) == 1

        # sem autenticação, alerta pessoal não deve aparecer
        public = db.get_alerts(user_id=None)
        assert public.empty

    def test_no_duplicate_alert_when_match_count_unchanged(self, db):
        user = db.create_user(email="alerts2@example.com", password="senhaSegura1")
        db.add_saved_search(user_id=user["id"], name="Qualquer coisa em SP", city="São Paulo")
        df = pd.DataFrame({"city": ["São Paulo"], "neighborhood": ["Centro"], "price": [200000], "area": [50]})

        engine = AlertEngine()
        first_run = engine.evaluate_saved_searches(df, db)
        second_run = engine.evaluate_saved_searches(df, db)

        assert len(first_run) == 1
        assert len(second_run) == 0  # mesma contagem de matches -> não repete
