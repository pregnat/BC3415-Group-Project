# moomoo SG Margin Risk Assistant

AI support agent that answers "Am I going to get liquidated?" for moomoo SG margin customers.
It prices positions, compares equity against the maintenance and soft-edge requirements, cites
help-centre rules, and escalates disputes and extension requests to a human risk desk. It never
gives buy/sell advice.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your ANTHROPIC_API_KEY
pytest                      # contract tests must stay green
streamlit run app/streamlit_app.py
python -m eval.run_eval     # calls the API: costs money
```

## Layout and owners

| Folder | Owner | What |
|---|---|---|
| `contracts.py` | all | **Frozen** data shapes between layers. Changes need a PR that both other teammates approve. |
| `data/`, `engine/` | A | Synthetic accounts, frozen price snapshot, margin ratios, margin engine, trading calendar |
| `notebooks/data_margin_engine/` | A | The notebook the engine was ported from. Run it from its own folder; it refreshes `data/stock_prices.csv`. |
| `rag/`, `eval/` | B | Help-centre scrape, index, retriever; 30-question eval harness; README |
| `agent/`, `app/` | C | Claude tool-use loop, tools, escalation, Streamlit UI, deployment |

`engine/` runs on the CSVs in `data/`. Remaining `TODO(owner)` items still need finishing: keep the
signatures and keep `tests/test_contracts.py` passing.

`data/stock_prices.csv` is the frozen snapshot the demo runs on. Refreshing it changes the demo
numbers, and `tests/test_margin.py` will fail until its expected values are updated.

`get_prices(mode="live")` tries moomoo if `MOOMOO_ACCESS_TOKEN` is set, then yfinance, then the
snapshot. The agent's tools use the snapshot.

## Deployment (Streamlit Community Cloud)

Main file: `app/streamlit_app.py`. Put `ANTHROPIC_API_KEY` in the app's **Secrets** settings and
never commit it.
