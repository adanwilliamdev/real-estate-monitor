import pandas as pd

from src.data_ingestion.demo_data import generate_synthetic_listings
from src.data_ingestion.scraper import RealEstateScraper


class TestRealEstateScraper:
    def test_price_cleaning(self):
        scraper = RealEstateScraper()
        assert scraper._clean_price("R$ 500.000") == 500000.0

    def test_price_cleaning_with_cents(self):
        scraper = RealEstateScraper()
        assert scraper._clean_price("R$ 1.234.567,89") == 1234567.89

    def test_area_cleaning(self):
        scraper = RealEstateScraper()
        assert scraper._clean_area("100 m²") == 100.0

    def test_rooms_cleaning(self):
        scraper = RealEstateScraper()
        assert scraper._clean_rooms("3 quartos") == 3

    def test_scrape_zapimoveis_never_raises(self):
        """Scraping ao vivo deve sempre retornar um DataFrame (vazio em falha),
        nunca lançar exceção não tratada — mesmo sem acesso à internet."""
        scraper = RealEstateScraper()
        df = scraper.scrape_zapimoveis("sao-paulo", max_pages=1)
        assert isinstance(df, pd.DataFrame)


class TestDemoDataGenerator:
    def test_generates_requested_amount(self):
        df = generate_synthetic_listings("sao-paulo", n_listings=50, seed=42)
        assert len(df) == 50

    def test_required_columns_present(self):
        df = generate_synthetic_listings("rio-de-janeiro", n_listings=10, seed=1)
        for col in ["price", "area", "rooms", "city", "neighborhood", "latitude", "longitude"]:
            assert col in df.columns

    def test_prices_and_areas_are_positive(self):
        df = generate_synthetic_listings("curitiba", n_listings=100, seed=7)
        assert (df["price"] > 0).all()
        assert (df["area"] > 0).all()

    def test_unknown_city_falls_back_to_default(self):
        df = generate_synthetic_listings("cidade-inexistente-xyz", n_listings=5, seed=1)
        assert len(df) == 5
        assert df["city"].iloc[0] == "São Paulo"
