<div align="center">

# 🏠 Real Estate Monitor

### Inteligência imobiliária orientada por dados

Análise de preços · Machine Learning · Oportunidades · Investimentos · Monitoramento

<br>

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Scikit-learn](https://img.shields.io/badge/Scikit--learn-ML-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Container-2496ED?style=for-the-badge&logo=docker&logoColor=white)

</div>

---

## 📌 Sobre o projeto

O **Real Estate Monitor** é uma plataforma de inteligência de mercado imobiliário desenvolvida para analisar **preços, tendências, oportunidades e indicadores de investimento**.

O projeto combina **Data Science, Machine Learning e Engenharia de Software** em uma arquitetura modular composta por:

- API REST
- Dashboard interativo
- Pipeline de dados
- Modelos de Machine Learning
- Motor de oportunidades
- Monitoramento de alterações no mercado
- Sistema de autenticação e alertas personalizados

> **Demo:** o projeto utiliza SQLite e dados sintéticos realistas. A coleta de dados reais possui fallback automático para dados de demonstração.

---

## 🚀 Funcionalidades

### 📊 Análise de mercado

- Análise de preços e tendências
- Estatísticas por cidade e bairro
- Histórico de preços
- Detecção de anomalias
- Clusterização de imóveis com K-Means

### 🤖 Machine Learning

- Previsão de preços
- Validação cruzada K-Fold
- Comparação entre modelos e baseline
- Métricas de avaliação
- Intervalo de previsão calibrado
- Detecção de cidades e bairros não observados no treinamento

### 💰 Oportunidades de investimento

- Estimativa de valor justo
- Cálculo de desconto sobre o valor justo
- Score de oportunidade de `0–100`
- Identificação automática do motivo da oportunidade
- Análise de ROI
- Yield líquido
- Payback
- Ranking de oportunidades

### 🔎 Monitoramento

- Identificação de novos anúncios
- Identificação de anúncios retirados
- Detecção de reduções de preço
- Histórico entre coletas
- Alertas automáticos
- Buscas salvas com alertas personalizados

### 👤 Usuários

- Cadastro e autenticação
- Login com JWT
- Favoritos
- Buscas salvas
- Alertas personalizados
- Área de conta no dashboard

---

## 🧠 Machine Learning

O modelo tem como alvo:

```text
log(R$/m²)
```

### Features utilizadas

- Área
- Quartos
- Banheiros
- Cidade
- Bairro
- Área por quarto
- Banheiros por quarto

Durante o treinamento, três candidatos competem utilizando **validação cruzada K-Fold**:

| Modelo | Descrição |
|---|---|
| Baseline | Mediana de R$/m² do bairro |
| Random Forest | Modelo de ensemble baseado em árvores |
| Gradient Boosting | Modelo de boosting baseado em árvores |

O modelo vencedor é definido pelo **menor MAPE**, garantindo que o Machine Learning não seja utilizado automaticamente quando uma regra simples apresenta desempenho superior.

### Métricas

O pipeline disponibiliza:

- `R²`
- `MAPE`
- `MAE`
- `baseline_mape`
- `best_ml_mape`
- `ml_beats_baseline`

Também é calculado um intervalo de aproximadamente **90%**, calibrado a partir dos erros reais fora da amostra utilizando uma abordagem conformal.

> **Nota:** nos dados sintéticos, o baseline costuma vencer porque o gerador define o R$/m² principalmente pelo bairro. Com dados reais, novas variáveis como andar, idade, vagas, conservação e localização podem permitir que os modelos de Machine Learning apresentem desempenho superior.

---

## 🎯 Motor de oportunidades

O `OpportunityFinder` estima o **valor justo** de cada anúncio utilizando previsões out-of-fold.

Isso evita que o modelo utilize o próprio anúncio para avaliar sua oportunidade.

O sistema calcula:

```text
Valor justo
      ↓
Preço anunciado
      ↓
Desconto
      ↓
Yield líquido
      ↓
Score 0–100
      ↓
Motivo da oportunidade
```

Descontos iguais ou superiores a **40%** recebem a marcação:

```text
needs_review
```

Isso ocorre porque descontos extremos podem representar erros de cadastro, dados inconsistentes ou anúncios suspeitos, e não necessariamente uma oportunidade real.

---

## 📡 Monitoramento do mercado

O pipeline compara a coleta atual com a coleta anterior para identificar alterações.

São monitorados:

- 🆕 Novos anúncios
- ❌ Anúncios retirados
- 📉 Reduções de preço
- 🔔 Alertas por cidade
- 🔎 Novos imóveis compatíveis com buscas salvas

No modo `demo`, o mercado **evolui entre as execuções**, simulando alterações reais como:

- novos imóveis
- imóveis vendidos
- redução de preços
- anúncios removidos

Isso evita que cada execução simplesmente recrie o mesmo conjunto de dados.

---

## 🔐 Autenticação

O sistema possui autenticação baseada em **JWT**.

As senhas são armazenadas utilizando:

```text
PBKDF2-HMAC-SHA256
```

com salt aleatório por usuário.

Os tokens JWT são assinados utilizando uma `SECRET_KEY`.

> ⚠️ Para produção, configure uma `SECRET_KEY` própria e forte no arquivo `.env`.

### Criar uma conta

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "voce@example.com", "password": "senhaSegura1"}'
```

### Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "voce@example.com", "password": "senhaSegura1"}'
```

### Acessar favoritos

```bash
curl http://localhost:8000/favorites \
  -H "Authorization: Bearer <access_token>"
```

### Criar uma busca salva

```bash
curl -X POST http://localhost:8000/saved-searches \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Apto em Pinheiros", "city": "São Paulo", "neighborhood": "Pinheiros", "max_price": 700000}'
```

---

## 🔌 API REST

A API é construída com **FastAPI** e possui documentação automática através do Swagger.

### Principais endpoints

| Método | Endpoint | Descrição |
|:---:|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/listings` | Lista imóveis |
| `GET` | `/stats` | Estatísticas |
| `GET` | `/neighborhoods` | Dados por bairro |
| `POST` | `/predict` | Previsão de preço |
| `POST` | `/investment` | Análise de investimento |
| `GET` | `/investment/opportunities` | Ranking por yield |
| `GET` | `/opportunities` | Imóveis abaixo do valor justo |
| `GET` | `/alerts` | Alertas |
| `GET` | `/history/{city}` | Histórico por cidade |
| `POST` | `/pipeline/run` | Executa o pipeline |
| `POST` | `/auth/register` | Cria uma conta |
| `POST` | `/auth/login` | Login |
| `GET` | `/auth/me` | Usuário autenticado |
| `GET/POST/DELETE` | `/favorites` | Gerenciamento de favoritos |
| `GET/POST/DELETE` | `/saved-searches` | Buscas salvas |

### Swagger

Após iniciar a API:

```text
http://localhost:8000/docs
```

---

## 🛠️ Stack

| Tecnologia | Utilização |
|---|---|
| **Python** | Linguagem principal |
| **FastAPI** | API REST |
| **Pandas** | Manipulação de dados |
| **NumPy** | Computação numérica |
| **Scikit-learn** | Machine Learning |
| **SQLite** | Banco para demonstração |
| **PostgreSQL** | Banco para produção |
| **Streamlit** | Dashboard |
| **Plotly** | Visualizações |
| **Docker** | Containerização |
| **Pytest** | Testes automatizados |
| **GitHub Actions** | CI/CD |

---

## 📁 Estrutura do projeto

```text
real-estate-monitor/
│
├── config/
│
├── src/
│   ├── alerts/
│   ├── api/
│   ├── auth/
│   ├── data_ingestion/
│   ├── data_processing/
│   ├── data_storage/
│   ├── orchestration/
│   └── visualization/
│
├── tests/
│
├── scripts/
│
├── main.py
├── requirements.txt
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## ⚡ Como executar

### Windows

```powershell
.\scripts\quick_start.ps1
```

### Linux / macOS

```bash
./scripts/quick_start.sh
```

### Execução manual

```bash
python -m venv venv
```

Ative o ambiente virtual e instale as dependências:

```bash
pip install -r requirements.txt
```

Execute o projeto:

```bash
python main.py run
```

---

## 🐳 Docker

Para executar todos os serviços utilizando Docker:

```bash
docker compose up --build
```

### Serviços

| Serviço | URL |
|---|---|
| 🖥️ Dashboard | `http://localhost:8501` |
| ⚙️ API | `http://localhost:8000` |
| 📚 Swagger | `http://localhost:8000/docs` |

---

## 💻 CLI

O projeto possui uma CLI para facilitar a execução dos principais componentes.

### Pipeline completo

```bash
python main.py run
```

### Pipeline com dados reais

```bash
python main.py run --source live
```

### Scraping

```bash
python main.py scrape
```

### Dashboard

```bash
python main.py dashboard
```

### API

```bash
python main.py api
```

---

## 🧪 Testes

Execute os testes com:

```bash
pytest
```

Para visualizar detalhes:

```bash
pytest -v
```

O projeto também possui **GitHub Actions** para execução automática dos testes em:

- `push`
- `pull request`
- branch `main`

---

## ⚙️ Configuração

Crie seu arquivo `.env` baseado no `.env.example`.

### CORS

```env
CORS_ORIGINS=https://meuapp.com
```

### Proteção do pipeline

```env
PIPELINE_API_KEY=uma-chave-secreta
```

Quando configurada, a chave deve ser enviada no header:

```http
X-API-Key: uma-chave-secreta
```

### JWT

```env
SECRET_KEY=troque-por-uma-chave-aleatoria-forte
```

> ⚠️ Nunca publique chaves, tokens ou credenciais reais no repositório.

---

## 📊 Pipeline

O fluxo principal do sistema pode ser representado da seguinte forma:

```text
                 ┌─────────────────┐
                 │  Data Sources   │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Data Ingestion  │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Data Processing │
                 └────────┬────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       ┌─────────────┐         ┌─────────────┐
       │  Database   │         │ ML Pipeline │
       └──────┬──────┘         └──────┬──────┘
              │                       │
              └───────────┬───────────┘
                          ▼
                 ┌─────────────────┐
                 │ Opportunity &   │
                 │ Alert Engine    │
                 └────────┬────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       ┌─────────────┐         ┌─────────────┐
       │  FastAPI    │         │  Streamlit  │
       └─────────────┘         └─────────────┘
```

---

## 📌 Disclaimer

Os dados sintéticos, previsões de Machine Learning e estimativas de aluguel e yield são destinados a **prototipagem, estudos e demonstração técnica**.

Os resultados dependem da qualidade, quantidade e atualidade dos dados utilizados e **não substituem avaliação imobiliária, financeira ou profissional especializada**.

---

<div align="center">

### 🏠 Real Estate Monitor

**Python · FastAPI · Scikit-learn · Streamlit · Docker**

</div>
