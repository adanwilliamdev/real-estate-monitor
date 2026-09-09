<div align="center">

# 🏠 Real Estate Monitor

### Inteligência imobiliária orientada por dados

**Transforme dados de mercado em insights sobre preços, tendências e oportunidades de investimento.**

<br>

<p>
  <img src="https://skillicons.dev/icons?i=python,fastapi,pandas,numpy,sklearn,sqlite,postgres,streamlit,plotly,docker,githubactions,git&perline=12" />
</p>

<br>

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Scikit-learn](https://img.shields.io/badge/Scikit--learn-Machine%20Learning-F7931E?style=flat-square&logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/Docker-Container-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)

</div>

---

## 📌 Sobre

O **Real Estate Monitor** é uma plataforma de inteligência de mercado imobiliário que coleta, processa e analisa dados para gerar insights sobre:

- **Preços e tendências** do mercado
- **Previsão de valores** com Machine Learning
- **Oportunidades de investimento**
- **Anomalias e imóveis abaixo do mercado**
- **Comportamento por cidade e bairro**

O projeto reúne **engenharia de software, Data Science e inteligência de negócio** em uma aplicação modular, com API REST, dashboard interativo, pipeline de dados e modelos de Machine Learning.

> **Modo demonstração:** funciona localmente com SQLite e dados sintéticos realistas. A coleta de dados reais possui execução *best-effort* e fallback automático para dados de demonstração.

---

## 🖥️ Dashboard

<p align="center">
  <img src="dashboard.png" alt="Dashboard do Real Estate Monitor" width="95%">
</p>

---

## ✨ O que o projeto faz

| Módulo | O que entrega |
|:--|:--|
| 📊 **Market Analytics** | Estatísticas, histórico e tendências de preços |
| 🤖 **Price Prediction** | Estimativa de preços com Random Forest |
| 💰 **Investment Intelligence** | ROI, yield, payback e comparação com o mercado |
| 🔔 **Alerts** | Identificação de anomalias e oportunidades |
| 🧠 **Clustering** | Agrupamento de imóveis com K-Means |
| 🗺️ **Geographic Analysis** | Análises por cidade e bairro |
| 🔌 **REST API** | Dados e análises expostos via FastAPI |
| 📈 **Dashboard** | Visualização interativa com Streamlit |

---

## 🤖 Machine Learning

A previsão de preços utiliza `RandomForestRegressor` considerando características como:

**Área · Quartos · Banheiros · Cidade · Bairro**

### Métricas

- **R²**
- **MAPE**
- Importância das variáveis
- Intervalo de confiança aproximado

```text
                  ┌─────────────────┐
                  │  Dados imóveis  │
                  └────────┬────────┘
                           ↓
                  ┌─────────────────┐
                  │ Pré-processamento│
                  └────────┬────────┘
                           ↓
                  ┌─────────────────┐
                  │ Feature          │
                  │ Engineering     │
                  └────────┬────────┘
                           ↓
                  ┌─────────────────┐
                  │ Random Forest   │
                  └────────┬────────┘
                           ↓
             ┌─────────────┼─────────────┐
             ↓             ↓             ↓
        Preço estimado     R²           MAPE
```

---

## 💰 Investment Intelligence

O módulo transforma dados do imóvel em indicadores para análise de investimento:

| Indicador | Objetivo |
|:--|:--|
| **Preço/m²** | Comparar valores entre imóveis e regiões |
| **Aluguel estimado** | Projetar potencial de renda |
| **Yield bruto/líquido** | Avaliar retorno sobre o imóvel |
| **ROI** | Avaliar retorno do investimento |
| **Payback** | Estimar tempo de recuperação |
| **Mercado local** | Comparar o imóvel com a região |

O sistema também permite gerar um **ranking de oportunidades** com base nos indicadores calculados.

---

## 🔔 Detecção de anomalias

A aplicação combina técnicas estatísticas e análise histórica para encontrar comportamentos fora do padrão.

**Z-Score · IQR · Histórico · Comparação regional**

```text
Preço fora do padrão
        ↓
Detecção de anomalia
        ↓
Análise do imóvel
        ↓
Possível oportunidade
        ↓
Alerta
```

---

## 🧠 Clusterização

O **K-Means** agrupa imóveis com características semelhantes considerando variáveis como:

**Preço · Área · Preço/m² · Quartos · Localização · Indicadores de investimento**

Isso permite identificar diferentes perfis de imóveis e segmentos dentro do mercado analisado.

---

## 🏗️ Arquitetura

```text
                         ┌──────────────┐
                         │    Usuário   │
                         └──────┬───────┘
                                │
                  ┌─────────────┴─────────────┐
                  ↓                           ↓
           ┌─────────────┐             ┌─────────────┐
           │  Streamlit  │             │   FastAPI   │
           │  Dashboard  │             │     API     │
           └──────┬──────┘             └──────┬──────┘
                  │                           │
                  └─────────────┬─────────────┘
                                ↓
                     ┌────────────────────┐
                     │   Business Logic   │
                     └─────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ↓                ↓                ↓
        ┌───────────┐    ┌───────────┐   ┌────────────┐
        │ Analytics │    │ ML Models │   │ Investment │
        └─────┬─────┘    └─────┬─────┘   └──────┬─────┘
              │                │                │
              └────────────────┼────────────────┘
                               ↓
                     ┌────────────────────┐
                     │   Storage / Cache  │
                     └─────────┬──────────┘
                               ↓
                     ┌────────────────────┐
                     │ SQLite / PostgreSQL│
                     └────────────────────┘
```

---

## 🔄 Pipeline

```text
Demo / Scraping
      ↓
Data Ingestion
      ↓
Data Processing
      ↓
 ┌────┴──────────────┐
 ↓                   ↓
Machine Learning   Investment
 ↓                   ↓
 └────────┬──────────┘
          ↓
   Storage / Cache
          ↓
 ┌────────┴────────┐
 ↓                 ↓
FastAPI         Streamlit
```

---

## 🔌 API

A API REST é construída com **FastAPI** e possui documentação automática via Swagger.

### Endpoints

| Método | Endpoint | Descrição |
|:--:|:--|:--|
| `GET` | `/health` | Health check |
| `GET` | `/listings` | Lista imóveis |
| `GET` | `/stats` | Estatísticas do mercado |
| `GET` | `/neighborhoods` | Dados por bairro |
| `POST` | `/predict` | Previsão de preço |
| `POST` | `/investment` | Análise de investimento |
| `GET` | `/investment/opportunities` | Ranking de oportunidades |
| `GET` | `/alerts` | Alertas |
| `GET` | `/history/{city}` | Histórico |
| `POST` | `/pipeline/run` | Executa o pipeline |

### 🔒 Configuração

Para restringir origens e proteger a execução do pipeline:

```env
CORS_ORIGINS=https://meuapp.com
PIPELINE_API_KEY=uma-chave-secreta
```

Com `PIPELINE_API_KEY` configurada, `POST /pipeline/run` exige o header:

```http
X-API-Key: uma-chave-secreta
```

---

## 🚀 Como executar

### ⚡ Quick Start

**Windows**

```powershell
.\scripts\quick_start.ps1
```

**Linux / macOS**

```bash
./scripts/quick_start.sh
```

### 🔧 Instalação manual

```bash
python -m venv venv
```

**Windows**

```powershell
venv\Scripts\Activate.ps1
```

**Linux / macOS**

```bash
source venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Execute:

```bash
python main.py run
```

### 🌐 Serviços

| Serviço | Endereço |
|:--|:--|
| 🎨 Dashboard | `http://localhost:8501` |
| 🔌 API | `http://localhost:8000` |
| 📖 Swagger | `http://localhost:8000/docs` |

---

## 🐳 Docker

Execute a aplicação com:

```bash
docker compose up --build
```

Depois:

```text
Dashboard → http://localhost:8501
API       → http://localhost:8000
Swagger   → http://localhost:8000/docs
```

---

## 🧭 CLI

```bash
# Aplicação completa
python main.py run

# Utilizando dados reais
python main.py run --source live

# Scraping
python main.py scrape

# Apenas dashboard
python main.py dashboard

# Apenas API
python main.py api
```

**Dados de demonstração:** São Paulo · Rio de Janeiro · Belo Horizonte · Curitiba · Porto Alegre

---

## 📁 Estrutura

```text
real-estate-monitor/
│
├── config/
├── src/
│   ├── data_ingestion/
│   ├── data_processing/
│   ├── data_storage/
│   ├── alerts/
│   ├── orchestration/
│   ├── api/
│   └── visualization/
│
├── tests/
├── scripts/
├── main.py
├── requirements.txt
├── docker-compose.yml
└── README.md
```

| Diretório | Responsabilidade |
|:--|:--|
| `data_ingestion` | Coleta e geração de dados |
| `data_processing` | Analytics, ML e indicadores |
| `data_storage` | Persistência e cache |
| `alerts` | Anomalias e alertas |
| `orchestration` | Coordenação do pipeline |
| `api` | API REST |
| `visualization` | Dashboard |
| `tests` | Testes automatizados |

---

## 🧪 Testes

Execute:

```bash
pytest
```

Modo detalhado:

```bash
pytest -v
```

O projeto possui **GitHub Actions** para execução automática dos testes em `push` e `pull request` na branch `main`, utilizando Python 3.11 e 3.12.

---

## ⚠️ Disclaimer

Os dados sintéticos, previsões de Machine Learning e estimativas de aluguel/yield são destinados a **prototipagem, estudos e demonstração técnica**.

A precisão dos resultados depende da qualidade, quantidade e atualidade dos dados utilizados.

> As análises apresentadas não substituem avaliação imobiliária, financeira ou profissional especializada.

---

<div align="center">

### 🏠 Real Estate Monitor

**Data-driven real estate intelligence.**

<br>

🐍 Python · ⚡ FastAPI · 🤖 Scikit-learn · 📊 Streamlit · 🐳 Docker

</div>
