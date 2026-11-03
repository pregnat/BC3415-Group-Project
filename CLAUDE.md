# CLAUDE.md

moomoo SG Margin Risk Assistant: a group project (BC3415, Option A: Coding) for a Claude-based
support agent. It answers "Am I going to get liquidated?", cites moomoo SG help-centre rules,
escalates disputes to a human risk desk, and never gives buy/sell advice. Deadline: Sun 15 Nov 2026,
with an internal target of 18:00. The README covers setup, layout, owners and the S1-S5 demo table.

## Commands

```bash
python3.11 -m venv .venv && source .venv/bin/activate   # 3.11: chromadb is untested on the default 3.13
pip install -r requirements.txt
pytest                          # 75 tests, all offline; no API key needed
streamlit run app/streamlit_app.py
python -m eval.run_eval         # calls the Claude API: costs money, ask first
```

## Team and ownership

| Owner | Layer | Folders |
|---|---|---|
| A: Yuqing | Data and margin engine | `data/`, `engine/`, `notebooks/` |
| B: Nat | RAG and eval | `rag/`, `eval/`, README |
| C: Caleb | Agent, app and deployment | `agent/`, `app/` |

`contracts.py` holds the shared data shapes. Changing it needs a PR that both other teammates
approve, plus matching updates to `tests/test_contracts.py`. Mark a change in someone else's layer
in the PR description.

## Ground rules

- Every merge to `main` goes through a PR reviewed by another teammate. Never push to `main`.
- No secrets in the repo. `ANTHROPIC_API_KEY` and the optional `MOOMOO_ACCESS_TOKEN` go in `.env`
  locally and in Streamlit secrets in the cloud.
- The agent must quote numbers exactly as the engine returns them. The engine computes and the
  LLM explains.

## How the engine works

`engine/margin.py` is ported from `notebooks/data_margin_engine/Data and Margin Engine.ipynb`.
`engine/` is the source of truth. The notebook still uses a x1.25 uplift and has no 100% cap.

- Data comes from the CSVs in `data/`, not the `accounts.db` or `price_snapshot.parquet` the plan
  named.
- `data/stock_prices.csv` is the frozen demo snapshot. Rerunning the notebook overwrites it, which
  changes the demo numbers and fails `tests/test_margin.py`.
- `DEMO_NOW` (Fri 6 Nov 2026, 15:00 UTC) is the default clock, so S3 works on any day.
- These choices are deliberate, so don't change them without the team. The full list is in
  `docs/assumptions.md`.
  - Equity = market value + cash - loan.
  - The Friday soft-edge uplift is x1.5, from the help-centre example of 20% to 30%.
  - Drop distances are capped at 100%.
  - An unknown breach clock reports `anytime`.

## Status (as of 3 Nov 2026)

- PRs are stacked, and each needs review before it is merged:
  - #2 `rag-foundations` targets `main`.
  - #3 `contracts-match-plan` targets #2.
  - #4 `data-margin-engine` targets #3.
- Still to do:
  - A: holiday calendar, `next_market_open`, price data-quality checks
  - B: 30-question eval set, numeric-faithfulness check
  - C: citations panel, margin gauge, deployment
- The Streamlit app has not been launched, and no live Claude call has been made.

## Git on this machine

There is no global git identity. Commits so far use
`git -c user.name=pregnat -c user.email=pregnat@users.noreply.github.com commit ...`. GitHub
access goes through `gh` (account `pregnat`). The folder above this repo holds Yuqing's original
notebook files: they aren't part of the repo, so leave them alone.
