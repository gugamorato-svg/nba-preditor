"""Modelo x mercado da Polymarket, nos jogos que têm preço 1h antes.

- log loss e Brier do modelo, do mercado e de uma mistura dos dois;
- IC95 por bootstrap pareado da diferença de log loss (modelo - mercado);
- calibração por faixa;
- ROI simulado de apostas de 1 unidade quando o modelo vê vantagem, já com
  taxa de taker e derrapagem, com IC95 por bootstrap.

A mistura tem o peso ajustado em 2025-26 e é avaliada em 2026-27. Em 2025-26
o número dela é dentro da amostra (otimista), e o relatório diz isso.

Uso:  python evaluate.py           (backtest; grava reports/relatorio.md)
      python evaluate.py --paper   (teste prospectivo de data/paper_log.csv)
"""
import argparse
import math
import os
import random
from datetime import datetime, timezone

from model import brier, load_params, log_loss, params_version, walk_forward
from nba_common import (MARKET_CSV, PAPER_CSV, REPORTS, parse_utc, read_csv, read_games,
                        taker_cost)

EDGE_THRESHOLD = 0.03   # regra principal, fixada ANTES de olhar o resultado
SENSITIVITY = [0.0, 0.02, 0.05, 0.08]
SLIPPAGE = 0.005        # meio centavo acima do preço do histórico (spread da NBA ~1c)
BOOTSTRAP = 2000
VALIDATION_SEASON, TEST_SEASON = 2025, 2026


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def blend(p_model, p_market, weight):
    """Mistura no espaço logit: weight=0 é só mercado, 1 é só modelo."""
    z = weight * logit(p_model) + (1 - weight) * logit(p_market)
    return 1 / (1 + math.exp(-z))


def fit_blend_weight(rows):
    best = None
    for step in range(21):
        weight = step / 20
        loss = log_loss([(blend(r["p_model"], r["p_market"], weight), r["y"]) for r in rows])
        if best is None or loss < best[0]:
            best = (loss, weight)
    return best[1]


def percentile(values, q):
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[index]


def bootstrap_ci(values, statistic, reps=BOOTSTRAP, seed=42):
    rng = random.Random(seed)
    n = len(values)
    stats = [statistic([values[rng.randrange(n)] for _ in range(n)]) for _ in range(reps)]
    return percentile(stats, 0.025), percentile(stats, 0.975)


def mean(values):
    return sum(values) / len(values)


def loss_diff_ci(rows, key):
    """Diferença média de log loss por jogo (key - mercado) com IC95 pareado."""
    def single(p, y):
        p = min(max(p, 1e-6), 1 - 1e-6)
        return -(y * math.log(p) + (1 - y) * math.log(1 - p))
    diffs = [single(r[key], r["y"]) - single(r["p_market"], r["y"]) for r in rows]
    low, high = bootstrap_ci(diffs, mean)
    return mean(diffs), low, high


def simulate_bets(rows, key, threshold, slippage=SLIPPAGE, price_key="p_market"):
    """Aposta 1 unidade no lado com maior vantagem (prob - custo) se passar do limiar.

    Devolve a lista de lucros por aposta (em unidades apostadas).
    """
    profits = []
    for r in rows:
        best = None
        for prob, price, won in ((r[key], r[price_key], r["y"] == 1),
                                 (1 - r[key], 1 - r[price_key], r["y"] == 0)):
            if not 0.01 < price < 0.99:
                continue
            cost = taker_cost(price, slippage)
            edge = prob - cost
            if edge >= threshold and (best is None or edge > best[0]):
                best = (edge, cost, won)
        if best:
            profits.append(1 / best[1] - 1 if best[2] else -1.0)
    return profits


def calibration(rows, key, bins=10):
    table = []
    for b in range(bins):
        low, high = b / bins, (b + 1) / bins
        inside = [r for r in rows if low <= r[key] < high or (b == bins - 1 and r[key] == 1)]
        if len(inside) >= 15:
            table.append((low, high, len(inside), mean([r[key] for r in inside]),
                          mean([r["y"] for r in inside])))
    return table


def backtest_rows():
    games = read_games()
    params = load_params()
    predictions, _ = walk_forward(games, params)
    p_model = {g["game_id"]: p for g, p in predictions}
    results = {g["game_id"]: g for g in games}
    rows, disagreements = [], 0
    for m in read_csv(MARKET_CSV):
        game = results.get(m["game_id"])
        if not game or game["home_pts"] is None:
            continue
        y = 1 if game["home_pts"] > game["away_pts"] else 0
        if m["resolved_home_win"] != "" and int(m["resolved_home_win"]) != y:
            disagreements += 1
        rows.append({"game_id": m["game_id"], "season": game["season"], "y": y,
                     "p_model": p_model[m["game_id"]], "p_market": float(m["p_home"]),
                     "minutes_before": float(m["minutes_before"]), "volume": float(m["volume"])})
    return rows, params, disagreements


def fmt_ci(value, low, high, pct=False):
    if pct:
        return f"{value:+.1%} (IC95 {low:+.1%} a {high:+.1%})"
    return f"{value:+.4f} (IC95 {low:+.4f} a {high:+.4f})"


def season_label(season):
    return f"{season}-{(season + 1) % 100:02d}"


def report(rows, params, disagreements):
    weight = fit_blend_weight([r for r in rows if r["season"] == VALIDATION_SEASON])
    for r in rows:
        r["p_blend"] = blend(r["p_model"], r["p_market"], weight)
    lines = [
        "# Modelo Elo x mercado da Polymarket (NBA)",
        "",
        f"Gerado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Modelo versão `{params_version(params)}`, "
        f"parâmetros {params} ajustados só em 2019-2024.",
        f"Preço de referência: último preço do histórico pelo menos 60 min antes do jogo. "
        f"Jogos casados: {len(rows)}. Resultado da Polymarket diferente do placar: {disagreements}.",
        f"Mistura = logit com peso {weight:.2f} no modelo (ajustado em {season_label(VALIDATION_SEASON)}).",
        "",
    ]
    splits = [(season_label(VALIDATION_SEASON) + " (validação)", [r for r in rows if r["season"] == VALIDATION_SEASON]),
              (season_label(TEST_SEASON) + " (teste, fora de tudo)", [r for r in rows if r["season"] == TEST_SEASON]),
              ("todos", rows)]
    lines += ["## Qualidade da probabilidade", "",
              "| Recorte | Jogos | Log loss mercado | Log loss modelo | Log loss mistura | Brier mercado | Brier modelo | Modelo − mercado (log loss) |",
              "|---|---|---|---|---|---|---|---|"]
    for name, subset in splits:
        if not subset:
            continue
        diff = loss_diff_ci(subset, "p_model")
        lines.append(
            f"| {name} | {len(subset)} | {log_loss([(r['p_market'], r['y']) for r in subset]):.4f} | "
            f"{log_loss([(r['p_model'], r['y']) for r in subset]):.4f} | "
            f"{log_loss([(r['p_blend'], r['y']) for r in subset]):.4f} | "
            f"{brier([(r['p_market'], r['y']) for r in subset]):.4f} | "
            f"{brier([(r['p_model'], r['y']) for r in subset]):.4f} | {fmt_ci(*diff)} |")
    test = [r for r in rows if r["season"] == TEST_SEASON]
    if test:
        lines += ["", f"Mistura − mercado no teste: {fmt_ci(*loss_diff_ci(test, 'p_blend'))} "
                      "(negativo = mistura melhor que o mercado)."]

    lines += ["", "## Apostas simuladas (1 unidade, taxa de taker + 0,5c de derrapagem)", "",
              f"Regra principal: apostar quando prob − custo ≥ {EDGE_THRESHOLD:.0%}. "
              "As outras linhas são só sensibilidade, não escolha de limiar.", "",
              "| Fonte | Recorte | Limiar | Apostas | ROI | Lucro (u) |", "|---|---|---|---|---|---|"]
    sources = [("p_model", "modelo")]
    if weight > 0:
        sources.append(("p_blend", "mistura"))
    for key, label in sources:
        for name, subset in splits:
            for threshold in [EDGE_THRESHOLD] + SENSITIVITY:
                profits = simulate_bets(subset, key, threshold)
                if not profits:
                    lines.append(f"| {label} | {name} | {threshold:.0%} | 0 | — | 0 |")
                    continue
                low, high = bootstrap_ci(profits, mean)
                main_rule = " **(principal)**" if threshold == EDGE_THRESHOLD else ""
                lines.append(f"| {label} | {name} | {threshold:.0%}{main_rule} | {len(profits)} | "
                             f"{fmt_ci(mean(profits), low, high, pct=True)} | {sum(profits):+.1f} |")

    if weight == 0:
        lines += ["", "A mistura não aparece nas apostas: o melhor peso para o modelo foi 0, "
                      "ou seja, ela é o próprio mercado e nunca vê vantagem."]
    lines += ["", "## Calibração (todos os jogos)", "",
              "| Faixa | Jogos (mercado) | Mercado previu | Aconteceu | Jogos (modelo) | Modelo previu | Aconteceu |",
              "|---|---|---|---|---|---|---|"]
    market_cal = {round(c[0], 1): c for c in calibration(rows, "p_market")}
    model_cal = {round(c[0], 1): c for c in calibration(rows, "p_model")}
    for low in sorted(set(market_cal) | set(model_cal)):
        mk, md = market_cal.get(low), model_cal.get(low)
        left = f"{mk[2]} | {mk[3]:.1%} | {mk[4]:.1%}" if mk else "— | — | —"
        right = f"{md[2]} | {md[3]:.1%} | {md[4]:.1%}" if md else "— | — | —"
        lines.append(f"| {low:.0%}–{low + 0.1:.0%} | {left} | {right} |")
    return lines


def paper_report():
    """Teste prospectivo: última captura de cada jogo feita 30+ min antes do início."""
    games = {g["game_id"]: g for g in read_games()}
    best = {}
    for row in read_csv(PAPER_CSV):
        if not row["game_id"] or float(row["minutes_before"]) < 30:
            continue
        current = best.get(row["game_id"])
        if current is None or float(row["minutes_before"]) < float(current["minutes_before"]):
            best[row["game_id"]] = row
    rows, versions = [], set()
    for game_id, row in best.items():
        game = games.get(game_id)
        if not game or game["home_pts"] is None or not row["ask_home"] or not row["ask_away"]:
            continue
        versions.add(row["model_version"])
        rows.append({"y": 1 if game["home_pts"] > game["away_pts"] else 0,
                     "p_model": float(row["p_model"]), "p_market": float(row["mid_home"]),
                     "ask_home": float(row["ask_home"]), "ask_away": float(row["ask_away"])})
    print(f"Teste prospectivo: {len(rows)} jogos encerrados com captura válida; versões do modelo: {sorted(versions)}")
    if len(versions) > 1:
        print("ATENÇÃO: mais de uma versão do modelo no teste. Pelo PROTOCOLO.md a contagem recomeça.")
    if not rows:
        return
    print(f"log loss mercado {log_loss([(r['p_market'], r['y']) for r in rows]):.4f}  "
          f"modelo {log_loss([(r['p_model'], r['y']) for r in rows]):.4f}")
    print("modelo − mercado:", fmt_ci(*loss_diff_ci(rows, "p_model")))
    # No papel o custo usa o ASK capturado de verdade (mais a taxa), sem derrapagem inventada.
    profits = []
    for r in rows:
        best_bet = None
        for prob, ask, won in ((r["p_model"], r["ask_home"], r["y"] == 1),
                               (1 - r["p_model"], r["ask_away"], r["y"] == 0)):
            cost = taker_cost(ask)
            if prob - cost >= EDGE_THRESHOLD and (best_bet is None or prob - cost > best_bet[0]):
                best_bet = (prob - cost, cost, won)
        if best_bet:
            profits.append(1 / best_bet[1] - 1 if best_bet[2] else -1.0)
    if profits:
        low, high = bootstrap_ci(profits, mean)
        print(f"apostas pela regra principal: {len(profits)}  ROI {fmt_ci(mean(profits), low, high, pct=True)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", action="store_true")
    args = parser.parse_args()
    if args.paper:
        paper_report()
        return
    rows, params, disagreements = backtest_rows()
    lines = report(rows, params, disagreements)
    os.makedirs(REPORTS, exist_ok=True)
    path = os.path.join(REPORTS, "relatorio.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(chr(10).join(lines) + chr(10))
    print(chr(10).join(lines))
    print(f"(gravado em {path})")


if __name__ == "__main__":
    main()
