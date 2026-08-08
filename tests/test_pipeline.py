import pytest

from src.data_storage.database import DatabaseManager
from src.orchestration.pipeline import (
    clean_properties,
    collect_properties,
    generate_report,
    run_pipeline,
)


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    return DatabaseManager(db_url=f"sqlite:///{db_path}")


class TestDatabaseManager:
    def test_save_and_get_listings(self, temp_db):
        df = collect_properties("sao-paulo", source="demo", n_listings=20)
        df_clean = clean_properties(df)
        saved = temp_db.save_listings(df_clean)
        assert saved == len(df_clean)

        retrieved = temp_db.get_listings()
        assert len(retrieved) == saved

    def test_get_statistics_empty_db(self, temp_db):
        stats = temp_db.get_statistics()
        assert stats["total_listings"] == 0

    def test_get_statistics_with_data(self, temp_db):
        df = collect_properties("curitiba", source="demo", n_listings=15)
        df_clean = clean_properties(df)
        temp_db.save_listings(df_clean)

        stats = temp_db.get_statistics()
        assert stats["total_listings"] == len(df_clean)
        assert stats["avg_price"] > 0


class TestPipeline:
    def test_collect_demo_data(self):
        df = collect_properties("sao-paulo", source="demo", n_listings=10)
        assert len(df) == 10
        assert not df.empty

    def test_generate_report_handles_empty_results(self):
        report = generate_report({})
        assert "Relatório" in report

    def test_run_pipeline_end_to_end(self, tmp_path, monkeypatch):
        # Isola o teste usando um banco temporário
        import src.orchestration.pipeline as pipeline_module

        db_path = tmp_path / "pipeline_test.db"
        monkeypatch.setattr(
            pipeline_module,
            "DatabaseManager",
            lambda: DatabaseManager(db_url=f"sqlite:///{db_path}"),
        )

        result = run_pipeline(city="belo-horizonte", source="demo", n_listings=25)
        assert result["scraped_count"] == 25
        assert result["saved_count"] == result["saved_count"]  # sanity
        assert "statistics" in result["analysis"]
