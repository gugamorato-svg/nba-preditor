# Contributing

Thanks for helping. Issues and PRs in English or Portuguese are welcome.

## Setup

Python 3.12+ and nothing else to install for the scripts. For the tests:

```bash
pip install pytest
python -m pytest
```

## Rules for model changes

The project's job is to tell the truth about whether there is an edge, so:

1. **No leakage.** A prediction may only use information available before tip-off.
   If you add a feature, add a test showing that changing the game's own result does
   not change its prediction.
2. **Compare with the market.** Report log loss against the Polymarket price
   (`python evaluate.py`), not accuracy.
3. **Fit on old seasons only.** Parameters are fitted on 2019-2024. Evaluate on
   2025 onwards and never tune on it.
4. **Pre-register theories.** Put a new idea in `estudos/<name>.md` with the
   hypothesis, the exact definition and the pass criterion **before** running it,
   then add the result, even if it fails. See `estudos/jetlag.md`.
5. **Any change to `p_model` is a new model version** and restarts the paper test
   in `PROTOCOLO.md`.

## Out of scope

- Code that places orders, signs transactions or handles wallets or private keys.
- Committing downloaded data (`data/*.csv`) or API keys.

## Good places to start

- A data source for playoff and play-in games.
- An analysis of `data/injuries_log.csv` against `data/paper_log.csv`: does the
  price move before or after injury news?
- A totals (over/under) model with the same market comparison.
