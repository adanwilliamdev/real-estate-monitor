# Changelog

## v2 — de "retrato do mercado" a monitor

### Correções
- `run_pipeline` apagava **todas** as cidades a cada coleta; agora substitui só as coletadas (`clear_listings(cities=...)`).
- Ranking de yield dava o mesmo valor para todo imóvel da mesma cidade (aluguel = preço × razão). Agora o aluguel usa o valor justo.
- Buscas salvas eram avaliadas só contra o lote atual (alternar cidades zerava o contador e repetia alertas); agora usam o mercado inteiro e alertam por imóveis *novos*.

### Novo
- `ml_models`: alvo log(R$/m²), CV K-Fold, baseline concorrente, intervalo conformal, seleção automática.
- `opportunities.py`, `lifecycle.py`, `serialization.py`, `evolve_synthetic_listings`.
- API: `GET /opportunities`; `/predict` e `/pipeline/run` com campos extras.

### Compatibilidade
- Modelo salvo pela v1 é recusado (features diferentes): rode o pipeline para re-treinar.
- `PricePredictionModel.train()` perdeu o parâmetro `test_size` (usa CV).

### Não coberto / próximos passos
- Dashboard Streamlit não foi alterado (não exibe oportunidades/eventos ainda).
- Dias no mercado e histórico de preço por anúncio exigem tabela nova + migração (Alembic).
- Scraper ao vivo usa seletores fictícios; dado real é o maior ganho pendente.
- Aluguel segue heurístico (razão fixa por cidade).
