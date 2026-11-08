# Source quality

What the assistant's corpus is built from, and how far each source can be trusted. The full list
of indexed files is `rag/corpus_manifest.csv`; local sources are listed in `rag/sources/sources.csv`.

| Source | Publisher | Date | Product tag | Used for | Trust | Caveats |
|---|---|---|---|---|---|---|
| Help centre, Margin Trading section (15 articles, e.g. [topic5_493](https://www.moomoo.com/sg/support/topic5_493), [topic5_495](https://www.moomoo.com/sg/support/topic5_495)) | Moomoo Financial Singapore | No publish date shown; fetched 2 Nov 2026 | `securities_margin` | Every rule the agent cites to customers | High: it is moomoo's own statement of its rules | Ratios (40/30/20%, raised to 30% before a weekend) are worked examples, not live per-stock rates, so the engine uses an assumption table. "Typically" and "absolute discretion" mean the uplift timing isn't a firm rule. |
| Help centre, forex/CFD margin rules ([topic5_607](https://www.moomoo.com/sg/support/topic5_607) and 3 others) | Moomoo Financial Singapore | Fetched 2 Nov 2026 | `forex_cfd` | Nothing customer-facing: kept so the product filter can exclude it | High, for forex/CFD only | Different close-out rule (50% of initial margin, end-of-day margin calls). Quoting it for stocks would be wrong. |
| Help centre, futures margin rules ([topic5_150](https://www.moomoo.com/sg/support/topic5_150) and 2 others) | Moomoo Financial Singapore | Fetched 2 Nov 2026 | `futures` | Excluded, as above | High, for futures only | Has its own 48-hour margin-call rule. The title doesn't say "futures", so it is easy to cite by mistake. |
| Help centre, options margin ([topic5_315](https://www.moomoo.com/sg/support/topic5_315)) | Moomoo Financial Singapore | Fetched 2 Nov 2026 | `options` | Excluded | High, for options only | Out of scope for this assistant. |
| Help centre, IPO financing interest ([topic5_274](https://www.moomoo.com/sg/support/topic5_274)) | Moomoo Financial Singapore | Fetched 2 Nov 2026 | `ipo_financing` | Excluded | High, for IPO financing only | Its "interest charges" are not margin interest, although it ranked first for that query before it was relabelled. |
| Help centre, firm risk controls ([topic5_1264](https://www.moomoo.com/sg/support/topic5_1264)) | Moomoo Financial Singapore | Fetched 2 Nov 2026 | `general` | Excluded | High | About order restrictions, not margin. |
| Futu Holdings 2025 Form 20-F ([SEC EDGAR](https://www.sec.gov/Archives/edgar/data/1754581/000110465926043451/futu-20251231x20f.htm)) | Futu Holdings Ltd | Filed 15 Apr 2026 | `company_disclosure` | Background on margin-financing credit risk and client assets. Not cited to customers. | Medium-high: audited annual filing, legally reviewed | Written for investors in Futu, not for customers. Risk-factor language is broad and covers every market Futu operates in, not only Singapore. **Not yet in the corpus**: save it into `rag/sources/` (see below). |
| MAS Financial Stability Review 2026 | Monetary Authority of Singapore | 2026 | `regulatory` | The "why it matters" hook: retail leverage risk | High: the regulator | Macro-level. It describes systemic risk, not individual customer rules. **Not yet in the corpus**, and the URL in `sources.csv` comes from a search result and hasn't been opened. |
| MoneySense: Guide to shares; Understanding CFDs | MoneySense (MAS) | Undated pages | `regulatory` | Plain-language framing of margin and leverage risk | High: government investor education | General guidance, not moomoo's rules. **Not yet in the corpus**. |
| Article on Futu's CSRC fine | TODO(B): add the article | TODO | Not indexed | Context only | Low | The plan flags it for referral-fee bias: check whether the publisher earns referral fees from brokers before quoting it. |

## Known corpus issues

- **No publish dates.** Help-centre pages show none, so `date` in each chunk is the fetch date.
- **Off-topic matches.** Some unrelated queries still clear the score threshold (for example "what
  time does SGX open", 0.333), because the threshold is set to keep every on-topic test query. The
  system prompt tells the agent to ignore irrelevant results.
- **Very short queries.** "48 hours" and "weekend" return Intraday Leverage Plus chunks, not the
  forced-liquidation page. Full-sentence queries find it.
- **One page dominates S1.** "Difference between maintenance and soft-edge margin" returns five
  chunks of `topic5_493`, so the separate maintenance definition in `topic5_487` isn't returned.

## Adding the sources marked "not yet in the corpus"

These sites refuse automated downloads, so save each file from a browser:

1. Open the URL in `rag/sources/sources.csv` and save the page or PDF into `rag/sources/` under the
   name in the `file` column.
2. Run `python -m rag.scrape --local-only` (the help-centre pages aren't re-fetched).
3. Run `rm -rf rag/index && pytest`. The retriever tests catch any drop in help-centre results.

They are tagged `company_disclosure` or `regulatory`, so the agent's default `securities_margin`
search never returns them in place of moomoo's own rules.
