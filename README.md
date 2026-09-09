<div align="center">

# 🏠 Real Estate Monitor

### Inteligência de mercado imobiliário baseada em dados, Machine Learning e análise de investimentos

<p>
  <strong>Python</strong> ·
  <strong>FastAPI</strong> ·
  <strong>Scikit-learn</strong> ·
  <strong>Streamlit</strong> ·
  <strong>SQLite</strong> ·
  <strong>Docker</strong>
</p>

</div>

---

## 📌 Sobre o projeto

O **Real Estate Monitor** é uma plataforma de inteligência de mercado imobiliário que coleta, processa e analisa dados para gerar insights sobre **preços, tendências, oportunidades de investimento e comportamento do mercado**.

O projeto integra engenharia de dados, análise estatística, Machine Learning, APIs REST e visualização de dados em uma única aplicação.

> **Destaque:** a aplicação pode ser executada localmente sem depender de serviços externos obrigatórios. O projeto utiliza **SQLite** e dados sintéticos realistas por padrão, enquanto a coleta de dados reais funciona em modo *best-effort*, com fallback automático para dados de demonstração.

<p align="center">
  <img src="dashboard.png" alt="Dashboard do Real Estate Monitor" width="100%">
</p>

---

## 📚 Sumário

- [✨ Funcionalidades](#-funcionalidades)
- [🛠️ Stack tecnológica](#️-stack-tecnológica)
- [🤖 Machine Learning](#-machine-learning)
- [💰 Investment Intelligence](#-investment-intelligence)
- [🔔 Alertas e detecção de anomalias](#-alertas-e-detecção-de-anomalias)
- [🧠 Clusterização](#-clusterização)
- [🔌 API](#-api)
- [🚀 Quick Start](#-quick-start)
- [🐳 Docker](#-docker)
- [🧭 CLI](#-cli)
- [📊 Arquitetura](#-arquitetura)
- [📁 Estrutura do projeto](#-estrutura-do-projeto)
- [🔄 Pipeline de dados](#-pipeline-de-dados)
- [🧪 Testes](#-testes)
- [⚠️ Observações](#️-observações)
- [🎯 Objetivos](#-objetivos)

---

## ✨ Funcionalidades

| | Funcionalidade |
|---|---|
| 📊 | Coleta e tratamento de dados imobiliários |
| 🤖 | Previsão de preços com **Random Forest** |
| 📈 | Histórico de preços e análise de tendências |
| 🔔 | Detecção de anomalias e geração de alertas |
| 💰 | Análise de investimento, ROI, yield e payback |
| 🗺️ | Análise por cidade e bairro |
| 🧠 | Clusterização de imóveis com **K-Means** |
| 🔌 | API REST com **FastAPI** |
| 🎨 | Dashboard interativo com **Streamlit** |
| 💾 | Persistência com SQLite e suporte opcional a PostgreSQL |
| 🐳 | Execução com Docker e Docker Compose |
| 🧪 | Testes automatizados com Pytest |

---

## 🛠️ Stack tecnológica

### Backend & API

- **Python 3.11+**
- **FastAPI**
- **Uvicorn**
- **Pydantic**

### Data Science & Machine Learning

- **Pandas**
- **NumPy**
- **Scikit-learn**
  - Random Forest
  - K-Means
  - Z-Score
  - IQR

### Banco de dados & armazenamento

- **SQLite**
- **PostgreSQL** *(opcional)*
- **SQLAlchemy**
- Cache em memória

### Dashboard & visualização

- **Streamlit**
- **Plotly**

### Coleta de dados

- **Requests**
- **BeautifulSoup**
- Scraping em modo *best-effort*
- Gerador de dados sintéticos

### DevOps & testes

- **Docker**
- **Docker Compose**
- **Pytest**
- **PowerShell**
- **Bash**
- **GitHub Actions**

---

## 🤖 Machine Learning

O modelo `RandomForestRegressor` estima preços com base em diferentes características dos imóveis:

- Área
- Quartos
- Banheiros
- Cidade
- Bairro

O módulo também disponibiliza métricas e informações para avaliação do modelo:

- **R²**
- **MAPE**
- Importância das variáveis
- Intervalo de confiança aproximado

### Fluxo de previsão

```text
Dados imobiliários
       │
       ▼
Pré-processamento
       │
       ▼
Feature Engineering
       │
       ▼
Random Forest
       │
       ├──► Preço estimado
       ├──► R²
       ├──► MAPE
       └──► Importância das variáveis
```

---

## 💰 Investment Intelligence

O módulo de inteligência de investimentos calcula indicadores para apoiar a avaliação de oportunidades imobiliárias:

- Aluguel estimado
- Yield bruto
- Yield líquido
- Payback
- ROI
- Custos de transação
- Preço por m²
- Comparação com o mercado local

Também é possível gerar um **ranking das melhores oportunidades de investimento** com base nos indicadores calculados.

### Fluxo de análise

```text
                    ┌─────────────────────┐
                    │   Imóvel analisado  │
                    └──────────┬──────────┘
                               │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
           Preço/m²        Aluguel        Mercado local
               │               │               │
               └───────────────┼───────────────┘
                               ▼
                    ┌─────────────────────┐
                    │ Investment Analysis │
                    └──────────┬──────────┘
                               │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
            Yield           Payback            ROI
```

---

## 🔔 Alertas e detecção de anomalias

O sistema possui mecanismos para identificar comportamentos fora do padrão no mercado imobiliário.

### Técnicas utilizadas

- **Z-Score**
- **IQR (Interquartile Range)**
- Análise histórica
- Comparação de preços por região
- Detecção de oportunidades abaixo do mercado

### Fluxo de detecção

```text
Preço muito abaixo da média
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

O **K-Means** é utilizado para agrupar imóveis com características semelhantes.

Os agrupamentos podem considerar:

- Preço
- Área
- Preço por m²
- Quantidade de quartos
- Localização
- Indicadores de investimento

Essa abordagem permite identificar diferentes **perfis de imóveis e regiões** dentro do mercado analisado.

---

## 🔌 API

A API foi construída com **FastAPI** e possui documentação automática através do Swagger.

Após iniciar a aplicação:

```text
http://localhost:8000/docs
```

### Endpoints

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/health` | Health check da API e do banco |
| `GET` | `/listings` | Lista imóveis |
| `GET` | `/stats` | Estatísticas do mercado |
| `GET` | `/neighborhoods` | Dados por bairro |
| `POST` | `/predict` | Previsão de preço |
| `POST` | `/investment` | Análise de investimento |
| `GET` | `/investment/opportunities` | Ranking de oportunidades |
| `GET` | `/alerts` | Alertas |
| `GET` | `/history/{city}` | Histórico por cidade |
| `POST` | `/pipeline/run` | Executa o pipeline |

### 🔒 Segurança da API

Por padrão, a API roda aberta para facilitar o uso local e demonstrações.

Duas variáveis de ambiente permitem aumentar a segurança em ambientes de produção:

| Variável | Descrição |
|---|---|
| `CORS_ORIGINS` | Lista de origens permitidas, separadas por vírgula |
| `PIPELINE_API_KEY` | Protege `POST /pipeline/run` com o header `X-API-Key` |

Exemplo:

```bash
# .env
CORS_ORIGINS=https://meuapp.com
PIPELINE_API_KEY=uma-chave-secreta
```

Exemplo de chamada:

```bash
curl -X POST http://localhost:8000/pipeline/run   -H "X-API-Key: uma-chave-secreta"   -H "Content-Type: application/json"   -d '{"city": "sao-paulo", "source": "demo", "n_listings": 300}'
```

> O endpoint `/pipeline/run` executa scraping e treinamento de ML de forma síncrona. Por isso, recomenda-se protegê-lo antes de expor a API publicamente.

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

### Instalação manual

Crie o ambiente virtual:

```bash
python -m venv venv
```

#### Windows

```powershell
venv\Scripts\Activate.ps1
```

#### Linux / macOS

```bash
source venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Execute a aplicação:

```bash
python main.py run
```

### Acessos

| Serviço | Endereço |
|---|---|
| 🎨 Dashboard | `http://localhost:8501` |
| 🔌 API | `http://localhost:8000` |
| 📖 Swagger | `http://localhost:8000/docs` |

---

## 🐳 Docker

O projeto também pode ser executado utilizando **Docker Compose**.

```bash
docker compose up --build
```

Após a inicialização:

```text
Dashboard → http://localhost:8501
API       → http://localhost:8000
Swagger   → http://localhost:8000/docs
```

---

## 🧭 CLI

O projeto possui uma CLI para facilitar a execução das principais operações.

### Executar aplicação completa

```bash
python main.py run
```

### Executar utilizando dados reais

```bash
python main.py run --source live
```

### Executar scraping

```bash
python main.py scrape
```

### Iniciar apenas o dashboard

```bash
python main.py dashboard
```

### Iniciar apenas a API

```bash
python main.py api
```

### Cidades disponíveis nos dados de demonstração

- São Paulo
- Rio de Janeiro
- Belo Horizonte
- Curitiba
- Porto Alegre

---

## 📊 Arquitetura

```text
                     ┌─────────────────────┐
                     │       Usuário       │
                     └──────────┬──────────┘
                                │
                     ┌──────────┴──────────┐
                     │                     │
                     ▼                     ▼
            ┌─────────────────┐   ┌─────────────────┐
            │    Streamlit    │   │     FastAPI     │
            │    Dashboard    │   │       API       │
            └────────┬────────┘   └────────┬────────┘
                     │                     │
                     └──────────┬──────────┘
                                ▼
                     ┌──────────────────┐
                     │  Business Logic  │
                     └────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
       ┌────────────┐  ┌────────────┐  ┌──────────────┐
       │ Analytics  │  │ ML Models  │  │ Investment   │
       │            │  │            │  │ Intelligence │
       └─────┬──────┘  └─────┬──────┘  └──────┬───────┘
             │               │                │
             └───────────────┼────────────────┘
                             ▼
                    ┌─────────────────┐
                    │ Storage / Cache │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │ SQLite /        │
                    │ PostgreSQL      │
                    └─────────────────┘
```

---

## 🔄 Pipeline de dados

O processamento é dividido em etapas de ingestão, tratamento, análise, Machine Learning, inteligência de investimentos e disponibilização dos resultados.

```text
┌──────────────────────┐
│  Fonte de dados      │
│  Demo / Scraping     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Data Ingestion     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Data Processing    │
│   Limpeza + Analytics│
└──────────┬───────────┘
           │
      ┌────┴───────────────┐
      ▼                    ▼
┌──────────────────┐ ┌──────────────────┐
│ Machine Learning │ │ Investment       │
│ Price Prediction │ │ Intelligence     │
└────────┬─────────┘ └────────┬─────────┘
         │                    │
         └──────────┬─────────┘
                    ▼
           ┌──────────────────┐
           │ Storage / Cache  │
           └────────┬─────────┘
                    │
             ┌──────┴───────┐
             ▼              ▼
      ┌─────────────┐ ┌─────────────┐
      │   FastAPI   │ │  Streamlit  │
      │     API     │ │  Dashboard  │
      └─────────────┘ └─────────────┘
```

---

## 📁 Estrutura do projeto

```text
real-estate-monitor/
│
├── config/                     # Configurações
│
├── src/
│   ├── data_ingestion/         # Coleta e dados de demonstração
│   ├── data_processing/        # Analytics, ML e investimentos
│   ├── data_storage/           # Banco de dados e cache
│   ├── alerts/                 # Sistema de alertas
│   ├── orchestration/          # Pipeline de processamento
│   ├── api/                    # FastAPI
│   └── visualization/          # Dashboard Streamlit
│
├── tests/                      # Testes automatizados
├── scripts/                    # Scripts de inicialização
├── main.py                     # CLI principal
├── requirements.txt            # Dependências
├── docker-compose.yml          # Orquestração Docker
└── README.md
```

### Responsabilidades dos módulos

| Módulo | Responsabilidade |
|---|---|
| `data_ingestion` | Coleta de dados e geração de dados sintéticos |
| `data_processing` | Tratamento, análise, ML e indicadores |
| `data_storage` | Persistência e cache |
| `alerts` | Detecção de anomalias e geração de alertas |
| `orchestration` | Coordenação do pipeline |
| `api` | Exposição dos dados através de REST |
| `visualization` | Dashboard e visualizações interativas |
| `tests` | Testes automatizados |
| `scripts` | Automação de execução e setup |

---

## 🧪 Testes

O projeto utiliza **Pytest** para testes automatizados.

Execute:

```bash
pytest
```

Para obter informações detalhadas:

```bash
pytest -v
```

Os testes também são executados automaticamente via **GitHub Actions** a cada `push` ou `pull request` na branch `main`, utilizando Python 3.11 e 3.12.

---

## ⚠️ Observações

Os **dados sintéticos, previsões de Machine Learning e estimativas de aluguel/yield** são destinados a **prototipagem, estudos e demonstração técnica**.

A precisão dos resultados depende diretamente da qualidade, quantidade e atualidade dos dados utilizados.

> As análises apresentadas **não substituem avaliação imobiliária, financeira ou profissional especializada**.

---

## 🎯 Objetivos

O **Real Estate Monitor** foi desenvolvido para demonstrar, em um único projeto, a integração entre:

- Engenharia de dados
- APIs REST
- Machine Learning
- Data Science
- Análise estatística
- Inteligência de investimentos
- Detecção de anomalias
- Visualização de dados
- Automação de pipelines
- Persistência de dados
- Desenvolvimento de dashboards
- Containerização com Docker
- Testes automatizados

O projeto combina **engenharia de software + dados + inteligência de negócio** em uma aplicação orientada a um problema real.

---

<div align="center">

## 🏠 Real Estate Monitor

**Inteligência de mercado imobiliário baseada em dados, Machine Learning e análise de investimentos.**

Desenvolvido com 🐍 **Python** · ⚡ **FastAPI** · 🤖 **Scikit-learn** · 📊 **Streamlit**

</div>
