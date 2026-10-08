"""Integração: escopo por cidade, eventos de ciclo de vida e buscas salvas no pipeline."""
import pandas as pd

from src.alerts.alert_engine import AlertEngine
from src.data_storage.database import DatabaseManager
from src.orchestration.pipeline import collect_properties, run_pipeline


def _isolated_pipeline(tmp_path, monkeypatch):
    """Banco e arquivo de modelo temporários; devolve o DatabaseManager do teste."""
    import src.data_processing.ml_models as ml_module
    import src.orchestration.pipeline as pipeline_module

    db_url = f"sqlite:///{tmp_path / 'lifecycle.db'}"
    monkeypatch.setattr(pipeline_module, "DatabaseManager", lambda: DatabaseManager(db_url=db_url))
    monkeypatch.setattr(ml_module, "MODEL_PATH", tmp_path / "model.joblib")
    return DatabaseManager(db_url=db_url)


class TestScopedClear:
    def test_clear_listings_by_city_keeps_the_others(self, tmp_path):
        db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'scoped.db'}")
        db.save_listings(collect_properties("sao-paulo", n_listings=10))
        db.save_listings(collect_properties("curitiba", n_listings=10))

        deleted = db.clear_listings(cities=["São Paulo"])
        assert deleted == 10
        assert set(db.get_listings()["city"]) == {"Curitiba"}

    def test_empty_city_list_deletes_nothing_and_none_deletes_everything(self, tmp_path):
        db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'scoped2.db'}")
        db.save_listings(collect_properties("sao-paulo", n_listings=10))
        assert db.clear_listings(cities=[]) == 0
        assert len(db.get_listings()) == 10
        assert db.clear_listings() == 10  # comportamento legado preservado
        assert db.get_listings().empty


class TestPipelineKeepsMarketHistory:
    def test_running_another_city_does_not_wipe_the_first(self, tmp_path, monkeypatch):
        db = _isolated_pipeline(tmp_path, monkeypatch)
        run_pipeline(city="sao-paulo", source="demo", n_listings=60)
        run_pipeline(city="rio-de-janeiro", source="demo", n_listings=60)
        counts = db.get_listings()["city"].value_counts().to_dict()
        assert set(counts) == {"São Paulo", "Rio de Janeiro"}

    def test_first_run_has_no_events_second_run_does(self, tmp_path, monkeypatch):
        db = _isolated_pipeline(tmp_path, monkeypatch)
        first = run_pipeline(city="sao-paulo", source="demo", n_listings=120)
        assert first["listing_events"]["is_first_snapshot"] is True

        second = run_pipeline(city="sao-paulo", source="demo", n_listings=120)
        ev = second["listing_events"]
        assert ev["is_first_snapshot"] is False
        assert ev["new"] > 0 and ev["removed"] > 0 and ev["price_drops"] > 0
        categories = {a["category"] for a in second["alerts"]}
        assert {"new_listings", "removed_listings", "listing_price_drop"} <= categories
        # o mercado continua com o tamanho pedido (nada acumulou nem sumiu)
        assert len(db.get_listings(city="São Paulo")) == second["saved_count"]

    def test_pipeline_returns_scored_opportunities_and_model_comparison(self, tmp_path, monkeypatch):
        _isolated_pipeline(tmp_path, monkeypatch)
        result = run_pipeline(city="curitiba", source="demo", n_listings=150)
        assert result["opportunities"], "esperava ao menos uma oportunidade"
        top = result["opportunities"][0]
        assert top["discount_pct"] > 0 and 0 <= top["score"] <= 100 and top["reason"]
        assert result["model"]["trained"] is True
        assert result["model"]["baseline_mape"] > 0
        assert "Melhores oportunidades" in result["report"]

    def test_tiny_batch_does_not_break_pipeline(self, tmp_path, monkeypatch):
        _isolated_pipeline(tmp_path, monkeypatch)
        result = run_pipeline(city="belo-horizonte", source="demo", n_listings=12)
        assert result["scraped_count"] == 12
        assert result["model"]["trained"] is False  # < 30 linhas: sem modelo, sem erro


class TestSavedSearchesOnNewListings:
    def test_alerts_on_new_matching_listing_even_when_count_is_unchanged(self, tmp_path):
        db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'ss.db'}")
        user = db.create_user(email="lifecycle@example.com", password="senhaSegura1")
        db.add_saved_search(user_id=user["id"], name="SP", city="São Paulo")
        engine = AlertEngine()

        def frame(prices):
            return pd.DataFrame(
                {"city": "São Paulo", "neighborhood": "Centro", "price": prices, "area": 50}
            )

        base = frame([200000, 210000])
        assert len(engine.evaluate_saved_searches(base, db, new_listings=base)) == 1  # busca nova

        # nada novo: não repete
        assert engine.evaluate_saved_searches(base, db, new_listings=base.iloc[0:0]) == []

        # 1 vendido + 1 novo compatível: a contagem não muda, mas há novidade
        swapped = frame([200000, 190000])
        alerts = engine.evaluate_saved_searches(swapped, db, new_listings=swapped.iloc[[1]])
        assert len(alerts) == 1
        assert "novo" in alerts[0]["message"]

    def test_legacy_mode_without_diff_is_unchanged(self, tmp_path):
        db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'ss2.db'}")
        user = db.create_user(email="legacy@example.com", password="senhaSegura1")
        db.add_saved_search(user_id=user["id"], name="SP", city="São Paulo")
        df = pd.DataFrame({"city": ["São Paulo"], "neighborhood": ["Centro"], "price": [200000], "area": [50]})
        engine = AlertEngine()
        assert len(engine.evaluate_saved_searches(df, db)) == 1
        assert len(engine.evaluate_saved_searches(df, db)) == 0
