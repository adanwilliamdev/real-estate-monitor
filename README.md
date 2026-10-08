<div align="center">

# 🏠 Real Estate Monitor

### Inteligência imobiliária orientada por dados

**Análise de mercado · Machine Learning · Oportunidades · Investimentos · Monitoramento**

<br>

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Scikit-learn](https://img.shields.io/badge/Scikit--learn-ML-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Container-2496ED?style=for-the-badge&logo=docker&logoColor=white)

</div>

---

## 📌 Sobre

O **Real Estate Monitor** é uma plataforma de inteligência de mercado imobiliário para análise de **preços, tendências e oportunidades de investimento**.

O projeto combina **Data Science, Machine Learning e Engenharia de Software** em uma aplicação modular com:

- API REST
- Dashboard interativo
- Pipeline de dados
- Modelos de Machine Learning
- Motor de oportunidades
- Monitoramento do mercado
- Sistema de autenticação
- Alertas personalizados

> **Demo:** utiliza SQLite e dados sintéticos realistas. A coleta de dados reais possui fallback automático para dados de demonstração.

---

## 🚀 Funcionalidades

### 📊 Análise de mercado

- Análise de preços e tendências
- Análises por cidade e bairro
- Histórico de preços
- Detecção de anomalias
- Clusterização de imóveis com K-Means

### 🤖 Machine Learning

- Previsão de preços
- Validação cruzada K-Fold
- Comparação com baseline
- Random Forest
- Gradient Boosting
- Intervalo de previsão calibrado
- Métricas out-of-fold
- Detecção de cidades e bairros não vistos no treinamento

### 💰 Oportunidades

- Estimativa de valor justo
- Desconto sobre o valor justo
- Score de oportunidade `0–100`
- Identificação do motivo da oportunidade
- ROI
- Yield líquido
- Payback
- Ranking de oportunidades

### 📡 Monitoramento

- Novos anúncios
- Anúncios retirados
- Reduções de preço
- Histórico entre coletas
- Alertas automáticos
- Alertas para buscas salvas

### 👤 Usuários

- Cadastro
- Login
- Autenticação JWT
- Favoritos
- Buscas salvas
- Alertas personalizados

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
| **PostgreSQL** | Banco de dados |
| **Streamlit** | Dashboard |
| **Plotly** | Visualizações |
| **Docker** | Containerização |
| **Pytest** | Testes |
| **GitHub Actions** | CI |

---

## 🧠 Machine Learning

O alvo utilizado pelo modelo é:

```text
log(R$/m²)
```

### Features

- Área
- Quartos
- Banheiros
- Cidade
- Bairro
- Área por quarto
- Banheiros por quarto

Três candidatos competem utilizando **validação cruzada K-Fold**:

| Modelo | Estratégia |
|---|---|
| **Baseline** | Mediana de R$/m² do bairro |
| **Random Forest** | Ensemble baseado em árvores |
| **Gradient Boosting** | Modelo de boosting |

O modelo vencedor é definido pelo **menor MAPE**.

Dessa forma, o sistema evita utilizar Machine Learning quando uma regra simples apresenta desempenho superior.

### Métricas

O pipeline disponibiliza:

- `R²`
- `MAPE`
- `MAE`
- `baseline_mape`
- `best_ml_mape`
- `ml_beats_baseline`

Também é calculado um intervalo de aproximadamente **90% calibrado**, utilizando os erros reais fora da amostra.

> **Nota:** nos dados sintéticos, o baseline costuma vencer porque o gerador define o R$/m² principalmente pelo bairro. Com dados reais, variáveis como andar, idade, vagas e localização podem permitir que o Machine Learning apresente desempenho superior.

---

## 🎯 Motor de oportunidades

O `OpportunityFinder` estima o **valor justo** de cada anúncio utilizando previsão **out-of-fold**, evitando que o modelo avalie um imóvel utilizando informações do próprio anúncio.

O processo é:

```text
Preço anunciado
       │
       ▼
Valor justo estimado
       │
       ▼
Desconto
       │
       ▼
Yield líquido
       │
       ▼
Score 0–100
       │
       ▼
Motivo da oportunidade
```

Descontos iguais ou superiores a **40%** recebem:

```text
needs_review
```

Isso ajuda a identificar possíveis erros de preço, inconsistências ou anúncios suspeitos.

---

## 📡 Monitoramento

O pipeline compara a coleta atual com a coleta anterior.

São identificados:

- 🆕 Novos anúncios
- ❌ Anúncios retirados
- 📉 Reduções de preço
- 🔔 Alertas por tipo e cidade
- 🔎 Novos imóveis compatíveis com buscas salvas

No modo `demo`, o mercado **evolui entre execuções**, simulando:

- novos imóveis
- imóveis vendidos
- reduções de preço
- anúncios removidos

Assim, cada execução não simplesmente recria os mesmos dados.

---

## 🔌 API REST

A API é construída com **FastAPI** e possui documentação automática através do Swagger.

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
| `GET` | `/history/{city}` | Histórico |
| `POST` | `/pipeline/run` | Executa o pipeline |
| `POST` | `/auth/register` | Cria uma conta |
| `POST` | `/auth/login` | Login |
| `GET` | `/auth/me` | Usuário autenticado |
| `GET/POST/DELETE` | `/favorites` | Favoritos |
| `GET/POST/DELETE` | `/saved-searches` | Buscas salvas |

### Swagger

Após iniciar a API:

```text
http://localhost:8000/docs
```

---

## 🔐 Autenticação

Contas de usuário permitem:

- Salvar imóveis favoritos
- Criar buscas personalizadas
- Receber alertas de novos imóveis compatíveis

Os critérios das buscas podem incluir:

- Cidade
- Bairro
- Faixa de preço
- Quantidade mínima de quartos

As buscas são reavaliadas a cada execução do pipeline.

### Criar conta

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

### Favoritos

```bash
curl http://localhost:8000/favorites \
  -H "Authorization: Bearer <access_token>"
```

### Busca salva

```bash
curl -X POST http://localhost:8000/saved-searches \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Apto em Pinheiros", "city": "São Paulo", "neighborhood": "Pinheiros", "max_price": 700000}'
```

### Segurança

As senhas são armazenadas utilizando:

```text
PBKDF2-HMAC-SHA256
```

com salt aleatório por usuário.

Os tokens são JWT assinados com `SECRET_KEY`.

> ⚠️ **Importante:** defina uma `SECRET_KEY` própria e forte no `.env` antes de utilizar o projeto em produção.

---

## ▶️ Execução

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
pip install -r requirements.txt
python main.py run
```

---

## 🐳 Docker

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

## 📁 Estrutura

```text
real-estate-monitor/
│
├── config/
│
├── src/
│   ├── data_ingestion/
│   ├── data_processing/
│   ├── data_storage/
│   ├── alerts/
│   ├── auth/
│   ├── orchestration/
│   ├── api/
│   └── visualization/
│
├── tests/
├── scripts/
│
├── main.py
├── requirements.txt
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🧪 Testes

Execute:

```bash
pytest
```

Para uma saída mais detalhada:

```bash
pytest -v
```

O projeto possui **GitHub Actions** para execução automática dos testes em:

- `push`
- `pull request`
- branch `main`

---

## ⚙️ Configuração

Para restringir origens e proteger o pipeline:

```env
CORS_ORIGINS=https://meuapp.com
PIPELINE_API_KEY=uma-chave-secreta
```

Quando configurada, a chave deve ser enviada no header:

```http
X-API-Key: uma-chave-secreta
```

Para autenticação JWT:

```env
SECRET_KEY=troque-por-uma-chave-aleatoria-forte
```

> ⚠️ Nunca publique chaves, tokens ou credenciais reais no repositório.

---

## ⚠️ Disclaimer

Os dados sintéticos, previsões de Machine Learning e estimativas de aluguel/yield são destinados a **prototipagem, estudos e demonstração técnica**.

Os resultados dependem da qualidade, quantidade e atualidade dos dados utilizados e **não substituem avaliação imobiliária, financeira ou profissional especializada**.

---

<div align="center">

### 🏠 Real Estate Monitor

**Python · FastAPI · Scikit-learn · Streamlit · Docker**

</div>
