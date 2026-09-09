<div align="center">

# Real Estate Monitor

**Inteligência imobiliária orientada por dados**

</div>

---

## Sobre

O **Real Estate Monitor** é uma plataforma de inteligência de mercado imobiliário para análise de preços, tendências e oportunidades de investimento.

O projeto combina **Data Science, Machine Learning e engenharia de software** em uma aplicação modular com API REST, dashboard interativo e pipeline de dados.

> **Demo:** utiliza SQLite e dados sintéticos realistas. A coleta de dados reais possui fallback automático para dados de demonstração.

## Funcionalidades

- Análise de preços e tendências
- Previsão de preços com Random Forest
- Análise de investimento: ROI, yield e payback
- Detecção de anomalias e oportunidades
- Clusterização de imóveis com K-Means
- Análises por cidade e bairro
- API REST com FastAPI
- Dashboard com Streamlit

## Stack

`Python` · `FastAPI` · `Pandas` · `NumPy` · `Scikit-learn` · `SQLite` · `PostgreSQL` · `Streamlit` · `Plotly` · `Docker`

## Machine Learning

O modelo `RandomForestRegressor` utiliza características como:

**Área · Quartos · Banheiros · Cidade · Bairro**

Métricas disponíveis:

- R²
- MAPE
- Importância das variáveis
- Intervalo de confiança aproximado

## API

| Método | Endpoint | Descrição |
|:--:|:--|:--|
| `GET` | `/health` | Health check |
| `GET` | `/listings` | Lista imóveis |
| `GET` | `/stats` | Estatísticas |
| `GET` | `/neighborhoods` | Dados por bairro |
| `POST` | `/predict` | Previsão de preço |
| `POST` | `/investment` | Análise de investimento |
| `GET` | `/investment/opportunities` | Oportunidades |
| `GET` | `/alerts` | Alertas |
| `GET` | `/history/{city}` | Histórico |
| `POST` | `/pipeline/run` | Executa o pipeline |

Documentação: `http://localhost:8000/docs`

## Execução

### Quick Start

**Windows**

```powershell
.\scripts\quick_start.ps1
```

**Linux / macOS**

```bash
./scripts/quick_start.sh
```

### Manual

```bash
python -m venv venv
pip install -r requirements.txt
python main.py run
```

### Docker

```bash
docker compose up --build
```

### Serviços

| Serviço | URL |
|:--|:--|
| Dashboard | `http://localhost:8501` |
| API | `http://localhost:8000` |
| Swagger | `http://localhost:8000/docs` |

## CLI

```bash
python main.py run
python main.py run --source live
python main.py scrape
python main.py dashboard
python main.py api
```

## Estrutura

```text
real-estate-monitor/
├── config/
├── src/
│   ├── data_ingestion/
│   ├── data_processing/
│   ├── data_storage/
│   ├── alerts/
│   ├── orchestration/
│   ├── api/
│   └── visualization/
├── tests/
├── scripts/
├── main.py
├── requirements.txt
├── docker-compose.yml
└── README.md
```

## Testes

```bash
pytest
```

Ou, para saída detalhada:

```bash
pytest -v
```

O projeto possui GitHub Actions para execução automática dos testes em `push` e `pull request` na branch `main`.

## Configuração

Para restringir origens e proteger o pipeline:

```env
CORS_ORIGINS=https://meuapp.com
PIPELINE_API_KEY=uma-chave-secreta
```

Quando configurada, a chave é enviada no header:

```http
X-API-Key: uma-chave-secreta
```

## Disclaimer

Os dados sintéticos, previsões de Machine Learning e estimativas de aluguel/yield são destinados a **prototipagem, estudos e demonstração técnica**.

Os resultados dependem da qualidade, quantidade e atualidade dos dados utilizados e não substituem avaliação imobiliária, financeira ou profissional especializada.

---

<div align="center">

**Real Estate Monitor**

Python · FastAPI · Scikit-learn · Streamlit · Docker

</div>
