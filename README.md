# nba-preditor

**English** · [Português](README.pt-BR.md)

An NBA win predictor (Elo) measured against Polymarket prices, to test **on paper
only** whether there is any edge before anyone thinks about money. The project only
reads public data. It never places orders and uses no wallet or keys.

Pure Python standard library (3.12+). The tests need `pytest`.

## Result so far

The market wins. On the 1,463 regular-season games with a Polymarket price
(2025-26 and the start of 2026-27):

- the model's log loss is worse: 0.596 against the market's 0.568, and the 95% CI
  of the difference is entirely above zero;
- the best weight for the model in a model + market blend is 0;
- the simulated betting rule loses 17% (95% CI −26% to −8%) over 902 bets.

Details are in [`reports/relatorio.md`](reports/relatorio.md). Tested theories live
in [`estudos/`](estudos/). The jetlag theory, for example, did not pass.

## Usage

```bash
python fetch_results.py      # schedule and scores since 2018-19 (fixturedownload.com)
python fetch_polymarket.py   # price 1h before each closed Polymarket game (~20 min)
python model.py --fit        # fit Elo on 2019-2024 ONLY (optional: params are committed)
python evaluate.py           # model vs market -> reports/relatorio.md
python paper_collect.py      # paper capture of upcoming games (run hourly)
python evaluate.py --paper   # score of the prospective test
python -m pytest
```

On Windows, `run_paper.cmd` is meant for Task Scheduler. It uses the Python in the
`NBA_PYTHON` environment variable when set.

## What is inside

| File | Purpose |
|---|---|
| `fetch_results.py` | Downloads regular-season CSVs into `data/games.csv` |
| `fetch_polymarket.py` | Lists NBA game events on Polymarket and stores the home team's price 60 min before tip-off in `data/market.csv` |
| `model.py` | Elo with home court, margin of victory, between-season regression and a back-to-back penalty, predicted game by game from the past only |
| `evaluate.py` | Log loss, Brier, calibration and simulated ROI with taker fee and bootstrap 95% CIs |
| `paper_collect.py` | Appends the prediction plus the order book's bid/ask to `data/paper_log.csv`, and calls `injuries.py` |
| `injuries.py` | Stores only the changes in ESPN's injury list in `data/injuries_log.csv` |
| `estudos/` | Theories tested with pre-registration |
| `PROTOCOLO.md` | Rules of the paper test, fixed before it started |

Data files (`data/*.csv`) are not committed. The scripts download everything again.

Docs and code comments are mostly in Portuguese. Issues and PRs in English are welcome.

## Ground rules

- **No leakage:** each prediction uses only earlier games. A test changes one game's
  score and checks that its own prediction does not move.
- **Beat the market, not accuracy:** picking the favourite already wins about 66% of
  NBA games.
- **Better log loss is not profit**, and fewer than ~500 bets is noise.
- **Fees:** Polymarket charges NBA takers `0.05 × p × (1 − p)` per share.

## Limitations

- Regular season only: playoffs and play-in are missing.
- The historical price is near the middle of the book, not the ask. The backtest adds
  half a cent on top. The paper test uses the real ask.
- The model knows nothing about injuries or planned rest. The market does.

Check whether prediction markets are legal where you live. This is a study, not
betting advice.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). MIT licensed.
