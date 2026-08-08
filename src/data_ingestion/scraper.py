"""
src/data_ingestion/scraper.py

Scraper "best-effort" de anúncios imobiliários. Sites de imóveis mudam o
HTML com frequência e costumam bloquear requisições automatizadas, então
este módulo é escrito para falhar de forma segura: qualquer erro de rede,
parsing ou ausência de resultados é logado e resulta em um DataFrame vazio
(nunca uma exceção não tratada), permitindo que quem chama decida cair
para dados sintéticos (ver `demo_data.py`).

Selenium é uma dependência pesada (exige Chrome/driver instalado) e por
isso é totalmente opcional aqui: só é importado se `use_selenium=True` for
passado explicitamente e o pacote estiver disponível.
"""
import random
import re
import time
from typing import Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config.settings import settings
from src.logging_setup import logger


class RealEstateScraper:
    """Raspa anúncios de imóveis. Uso ao vivo é best-effort por natureza."""

    def __init__(self, use_selenium: bool = False):
        self.headers = {"User-Agent": settings.USER_AGENT}
        self.use_selenium = use_selenium
        self.driver = None

        if use_selenium:
            try:
                from selenium import webdriver  # import tardio e opcional
                from selenium.webdriver.chrome.options import Options

                options = Options()
                options.add_argument("--headless=new")
                self.driver = webdriver.Chrome(options=options)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Selenium indisponível ({exc}); continuando sem navegador headless"
                )
                self.use_selenium = False

    def scrape_zapimoveis(self, city: str, max_pages: int = 5) -> pd.DataFrame:
        """Tenta raspar listagens do Zap Imóveis. Retorna DataFrame vazio em falha."""
        listings: List[Dict] = []

        for page in range(1, max_pages + 1):
            try:
                url = f"https://www.zapimoveis.com.br/venda/apartamentos/{city}/?pagina={page}"
                response = requests.get(
                    url, headers=self.headers, timeout=settings.SCRAPE_TIMEOUT
                )
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")

                cards = soup.find_all("div", class_="card")
                if not cards:
                    logger.warning(
                        f"Nenhum card encontrado na página {page} (layout do site "
                        "pode ter mudado ou a requisição foi bloqueada)"
                    )
                    break

                for card in cards:
                    listing = self._extract_listing_info(card)
                    if listing:
                        listings.append(listing)

                logger.info(f"Página {page}: {len(cards)} cards encontrados")
                time.sleep(random.uniform(1, 3))

            except requests.RequestException as exc:
                logger.error(f"Erro de rede ao raspar página {page}: {exc}")
                break
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Erro inesperado ao raspar página {page}: {exc}")
                continue

        df = pd.DataFrame(listings)
        if not df.empty:
            df["scraped_at"] = pd.Timestamp.utcnow()
            df["source"] = "zapimoveis"
        else:
            logger.warning(
                "Scraping ao vivo não retornou nenhum resultado. "
                "Use fonte 'demo' para dados sintéticos."
            )
        return df

    def _extract_listing_info(self, card) -> Optional[Dict]:
        try:
            price_elem = card.find("span", class_="price")
            area_elem = card.find("span", class_="area")
            rooms_elem = card.find("span", class_="rooms")
            address_elem = card.find("span", class_="address")

            if not price_elem:
                return None

            link = card.find("a")
            return {
                "price": self._clean_price(price_elem.text),
                "area": self._clean_area(area_elem.text) if area_elem else None,
                "rooms": self._clean_rooms(rooms_elem.text) if rooms_elem else None,
                "address": address_elem.text.strip() if address_elem else None,
                "url": link["href"] if link and link.has_attr("href") else None,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Erro ao extrair listagem: {exc}")
            return None

    @staticmethod
    def _clean_price(price_text: str) -> float:
        """Converte string de preço em BRL (ex: 'R$ 500.000') para float."""
        numbers = re.sub(r"[^\d,]", "", price_text)
        numbers = numbers.replace(".", "").replace(",", ".")
        try:
            return float(numbers) if numbers else 0.0
        except ValueError:
            return 0.0

    @staticmethod
    def _clean_area(area_text: str) -> float:
        numbers = re.findall(r"\d+", area_text)
        return float(numbers[0]) if numbers else 0.0

    @staticmethod
    def _clean_rooms(rooms_text: str) -> int:
        numbers = re.findall(r"\d+", rooms_text)
        return int(numbers[0]) if numbers else 0

    def close(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except Exception:  # noqa: BLE001
                pass

    def __del__(self):
        self.close()


class APIIngestor:
    """Ingestão opcional de dados complementares via APIs externas."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GOOGLE_PLACES_API_KEY
        self.session = requests.Session()

    def get_from_google_places(self, query: str, location: str) -> pd.DataFrame:
        """Busca pontos de interesse próximos via Google Places API (requer chave)."""
        if not self.api_key:
            logger.warning("Nenhuma API key do Google Places configurada")
            return pd.DataFrame()

        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {"query": f"{query} in {location}", "key": self.api_key}

        try:
            response = self.session.get(url, params=params, timeout=settings.SCRAPE_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK":
                logger.error(f"Google Places API retornou status: {data.get('status')}")
                return pd.DataFrame()

            places = [
                {
                    "name": place.get("name"),
                    "address": place.get("formatted_address"),
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("user_ratings_total"),
                    "lat": place["geometry"]["location"]["lat"],
                    "lng": place["geometry"]["location"]["lng"],
                }
                for place in data.get("results", [])[:20]
            ]
            return pd.DataFrame(places)

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Erro ao consultar Google Places: {exc}")
            return pd.DataFrame()

    def get_from_ibge(self, city: str) -> pd.DataFrame:
        """Busca dados demográficos básicos do IBGE para uma cidade."""
        url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"

        try:
            response = self.session.get(url, timeout=settings.SCRAPE_TIMEOUT)
            response.raise_for_status()
            cities_data = response.json()

            data = [
                {
                    "city": city_info["nome"],
                    "state": city_info["microrregiao"]["mesorregiao"]["UF"]["sigla"],
                }
                for city_info in cities_data
                if city.lower() in city_info["nome"].lower()
            ]
            return pd.DataFrame(data)

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Erro ao consultar IBGE: {exc}")
            return pd.DataFrame()
