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
| `data/`, `engine/` | A | Synthetic accounts, prices, margin ratios, margin engine, trading calendar |
| `rag/`, `eval/` | B | Help-centre scrape, index, retriever; 30-question eval harness; README |
| `agent/`, `app/` | C | Claude tool-use loop, tools, escalation, Streamlit UI, deployment |

Every module currently returns **stub data** in the contract shapes, so all three layers can be
built in parallel. Replace the `TODO(owner)` bodies, but keep the signatures and keep
`tests/test_contracts.py` passing.

## Deployment (Streamlit Community Cloud)

Main file: `app/streamlit_app.py`. Put `ANTHROPIC_API_KEY` in the app's **Secrets** settings and
never commit it.
