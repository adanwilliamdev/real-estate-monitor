# 🏠 Real Estate Monitor

> Plataforma de inteligência de mercado imobiliário com **Machine Learning, análise de investimentos, histórico de preços e alertas automáticos**.

O **Real Estate Monitor** coleta, processa e analisa dados imobiliários para gerar insights sobre preços, oportunidades de investimento e tendências de mercado.

A aplicação funciona **sem serviços externos obrigatórios**, utilizando SQLite e dados sintéticos realistas por padrão. O scraping de dados reais está disponível em modo *best-effort*, com fallback automático para dados de demonstração.

---

## 🛠️ Stack

### Backend & API

* **Python 3.11+**
* **FastAPI**
* **Uvicorn**
* **Pydantic**

### Data Science & Machine Learning

* **Pandas**
* **NumPy**
* **Scikit-learn**

  * Random Forest
  * K-Means
  * Z-Score
  * IQR

### Database & Storage

* **SQLite**
* **PostgreSQL** *(opcional)*
* **SQLAlchemy**
* Cache em memória

### Dashboard

* **Streamlit**
* **Plotly**

### Data Collection

* **Requests**
* **BeautifulSoup**
* Scraping *best-effort*
* Gerador de dados sintéticos

### DevOps & Testing

* **Docker**
* **Docker Compose**
* **Pytest**
* **PowerShell**
* **Bash**

---

## ✨ Funcionalidades

* 📊 Coleta e tratamento de dados imobiliários
* 🤖 Previsão de preços com **Random Forest**
* 📈 Histórico de preços e tendências
* 🔔 Detecção de anomalias e alertas
* 💰 Análise de investimento, ROI, yield e payback
* 🗺️ Análise por cidade e bairro
* 🧠 Clusterização com K-Means
* 🔌 API REST com FastAPI
* 🎨 Dashboard interativo com Streamlit
* 💾 SQLite + PostgreSQL
* 🐳 Docker
* 🧪 Testes automatizados

---

## 🤖 Machine Learning

O modelo `RandomForestRegressor` estima preços utilizando:

* Área
* Quartos
* Banheiros
* Cidade
* Bairro

Também são disponibilizados **R², MAPE, importância das variáveis e intervalo de confiança aproximado**.

---

## 💰 Investment Intelligence

O módulo de investimentos calcula:

* Aluguel estimado
* Yield bruto e líquido
* Payback
* Custos de transação
* Preço/m²
* Comparação com o mercado local

Também gera um **ranking das melhores oportunidades de investimento**.

---

## 🔌 API

Construída com **FastAPI** e documentação automática em `/docs`.

| Método | Endpoint                    | Função                   |
| ------ | --------------------------- | ------------------------ |
| GET    | `/listings`                 | Lista imóveis            |
| GET    | `/stats`                    | Estatísticas do mercado  |
| GET    | `/neighborhoods`            | Dados por bairro         |
| POST   | `/predict`                  | Previsão de preço        |
| POST   | `/investment`               | Análise de investimento  |
| GET    | `/investment/opportunities` | Ranking de oportunidades |
| GET    | `/alerts`                   | Alertas                  |
| GET    | `/history/{city}`           | Histórico                |
| POST   | `/pipeline/run`             | Executa pipeline         |

---

## 🚀 Quick Start

### Windows

```powershell
.\scripts\quick_start.ps1
```

### Linux / macOS

```bash
./scripts/quick_start.sh
```

### Manual

```bash
python -m venv venv

# Windows
venv\Scripts\Activate.ps1

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
python main.py run
```

Dashboard:

```text
http://localhost:8501
```

API:

```text
http://localhost:8000/docs
```

---

## 🐳 Docker

```bash
docker compose up --build
```

---

## 🧭 CLI

```bash
python main.py run
python main.py run --source live
python main.py scrape
python main.py dashboard
python main.py api
```

Cidades disponíveis nos dados demo:

**São Paulo · Rio de Janeiro · Belo Horizonte · Curitiba · Porto Alegre**

---

## 📁 Estrutura

```text
├── config/              # Configurações
├── src/
│   ├── data_ingestion/  # Coleta e dados demo
│   ├── data_processing/ # Analytics, ML e investimentos
│   ├── data_storage/    # Banco e cache
│   ├── alerts/          # Sistema de alertas
│   ├── orchestration/   # Pipeline
│   ├── api/             # FastAPI
│   └── visualization/   # Streamlit
├── tests/               # Testes
├── scripts/             # Scripts de inicialização
└── main.py              # CLI
```

---

## ⚠️ Observação

Os dados sintéticos, previsões de ML e estimativas de aluguel/yield são destinados a **prototipagem e demonstração**.

A precisão depende da qualidade dos dados utilizados e os resultados não substituem avaliação imobiliária ou financeira profissional.
