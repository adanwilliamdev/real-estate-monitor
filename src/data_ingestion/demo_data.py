"""
src/data_ingestion/demo_data.py

Gerador de dados sintéticos de anúncios imobiliários.

Sites de imóveis (Zap, VivaReal, etc.) mudam o layout com frequência e
bloqueiam scraping automatizado, então confiar apenas em scraping ao vivo
deixaria o projeto quebrado na maior parte do tempo. Este módulo gera dados
realistas (mas sintéticos) com distribuições plausíveis de preço, área e
localização por cidade/bairro brasileiros, permitindo que todo o pipeline
(limpeza, análise, storage, dashboard) funcione de ponta a ponta sempre.
"""
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd

from src.logging_setup import logger

# Coordenadas aproximadas (lat, lon) do centro de cada cidade suportada
CITY_COORDS: Dict[str, Dict] = {
    "sao-paulo": {
        "display_name": "São Paulo",
        "state": "SP",
        "lat": -23.5505,
        "lon": -46.6333,
        "neighborhoods": [
            "Pinheiros", "Vila Mariana", "Moema", "Itaim Bibi", "Jardins",
            "Tatuapé", "Vila Madalena", "Perdizes", "Santana", "Brooklin",
        ],
        "price_base": 8500,  # R$/m² base
    },
    "rio-de-janeiro": {
        "display_name": "Rio de Janeiro",
        "state": "RJ",
        "lat": -22.9068,
        "lon": -43.1729,
        "neighborhoods": [
            "Copacabana", "Ipanema", "Leblon", "Botafogo", "Barra da Tijuca",
            "Tijuca", "Recreio", "Flamengo", "Laranjeiras", "Jacarepaguá",
        ],
        "price_base": 9200,
    },
    "belo-horizonte": {
        "display_name": "Belo Horizonte",
        "state": "MG",
        "lat": -19.9167,
        "lon": -43.9345,
        "neighborhoods": [
            "Savassi", "Lourdes", "Belvedere", "Buritis", "Santo Antônio",
            "Sion", "Castelo", "Cidade Nova", "Pampulha", "Serra",
        ],
        "price_base": 6200,
    },
    "curitiba": {
        "display_name": "Curitiba",
        "state": "PR",
        "lat": -25.4284,
        "lon": -49.2733,
        "neighborhoods": [
            "Batel", "Água Verde", "Centro Cívico", "Bigorrilho", "Cabral",
            "Champagnat", "Juvevê", "Cristo Rei", "Portão", "Ecoville",
        ],
        "price_base": 6800,
    },
    "porto-alegre": {
        "display_name": "Porto Alegre",
        "state": "RS",
        "lat": -30.0346,
        "lon": -51.2177,
        "neighborhoods": [
            "Moinhos de Vento", "Bela Vista", "Petrópolis", "Menino Deus",
            "Cidade Baixa", "Bom Fim", "Auxiliadora", "Tristeza",
            "Higienópolis", "Boa Vista",
        ],
        "price_base": 6500,
    },
}

VALID_CITIES = list(CITY_COORDS.keys())


def _pick_city_key(city: str) -> str:
    """Normaliza o nome da cidade recebido para uma chave conhecida."""
    key = city.strip().lower().replace(" ", "-").replace("_", "-")
    if key in CITY_COORDS:
        return key
    # tenta casar por aproximação (ex: "sao paulo" -> "sao-paulo")
    for candidate in CITY_COORDS:
        if candidate.replace("-", "") == key.replace("-", ""):
            return candidate
    logger.warning(f"Cidade '{city}' não reconhecida, usando 'sao-paulo' como padrão")
    return "sao-paulo"


def generate_synthetic_listings(
    city: str = "sao-paulo",
    n_listings: int = 300,
    seed: int = None,
) -> pd.DataFrame:
    """Gera um DataFrame de anúncios imobiliários sintéticos e realistas.

    Args:
        city: cidade alvo (ex: 'sao-paulo', 'rio-de-janeiro')
        n_listings: quantidade de anúncios a gerar
        seed: seed para reprodutibilidade (opcional)

    Returns:
        DataFrame com colunas compatíveis com o restante do pipeline.
    """
    rng = np.random.default_rng(seed)
    city_key = _pick_city_key(city)
    city_info = CITY_COORDS[city_key]

    rooms_choices = [1, 2, 2, 3, 3, 3, 4, 4, 5]
    listings: List[Dict] = []

    for i in range(n_listings):
        neighborhood = rng.choice(city_info["neighborhoods"])
        rooms = int(rng.choice(rooms_choices))

        # Área correlacionada com número de quartos + ruído
        base_area = 25 + rooms * 22
        area = max(20.0, float(rng.normal(base_area, base_area * 0.22)))

        # Preço por m² varia por bairro (efeito fixo por índice do bairro)
        neighborhood_idx = city_info["neighborhoods"].index(neighborhood)
        neighborhood_multiplier = 0.75 + (neighborhood_idx * 0.06)
        price_per_m2 = max(
            1500.0,
            float(rng.normal(city_info["price_base"] * neighborhood_multiplier, 900)),
        )
        price = round(price_per_m2 * area, -2)  # arredonda pra centena

        bathrooms = max(1, rooms - rng.integers(0, 2))
        scraped_at = datetime.utcnow() - timedelta(days=int(rng.integers(0, 30)))

        # pequena dispersão geográfica ao redor do centro da cidade
        lat = city_info["lat"] + rng.normal(0, 0.03)
        lon = city_info["lon"] + rng.normal(0, 0.03)

        listings.append(
            {
                "source": "demo_generator",
                "source_id": f"{city_key}-{i:05d}",
                "price": round(price, 2),
                "area": round(area, 1),
                "rooms": rooms,
                "bedrooms": rooms,
                "bathrooms": int(bathrooms),
                "address": f"Rua {rng.integers(1, 999)}, {neighborhood}, "
                f"{city_info['display_name']} - {city_info['state']}",
                "city": city_info["display_name"],
                "state": city_info["state"],
                "neighborhood": neighborhood,
                "latitude": lat,
                "longitude": lon,
                "url": f"https://example.com/imovel/{city_key}-{i:05d}",
                "scraped_at": scraped_at,
            }
        )

    df = pd.DataFrame(listings)
    logger.info(f"Gerados {len(df)} anúncios sintéticos para {city_info['display_name']}")
    return df


if __name__ == "__main__":
    sample = generate_synthetic_listings("sao-paulo", 10)
    print(sample.head(10))
