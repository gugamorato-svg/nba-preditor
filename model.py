"""Modelo Elo com mando de quadra, margem de vitória, regressão entre
temporadas e penalidade de back-to-back.

A previsão é walk-forward: cada jogo é previsto com o Elo de ANTES dele, e
só depois o resultado entra na conta. O descanso usa só o calendário (data
do jogo anterior), que já é público antes do jogo.

Uso:  python model.py --fit   (ajusta os parâmetros SÓ nas temporadas 2018-2024)
      python model.py         (mostra a qualidade com os parâmetros salvos)
"""
import argparse
import hashlib
import itertools
import json
import math

from nba_common import PARAMS_JSON, game_day, read_games

MEAN_ELO = 1500.0
DEFAULT_PARAMS = {"k": 20.0, "home": 70.0, "b2b": 40.0, "regress": 0.25}

FIT_SEASONS = range(2019, 2025)  # 2018 é aquecimento; 2025+ fica de fora do ajuste
GRID = {
    "k": [12, 16, 20, 24, 28],
    "home": [20, 30, 40, 55, 70, 85],
    "b2b": [0, 20, 35, 50, 70],
    "regress": [0.25, 0.4, 0.5, 0.6, 0.75],
}


def win_probability(diff):
    return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))


def mov_multiplier(margin, winner_diff):
    """Multiplicador de margem: vitória larga mexe mais, mas favorito ganha menos."""
    return ((abs(margin) + 3.0) ** 0.8) / (7.5 + 0.006 * winner_diff)


def walk_forward(games, params=None, extra=None):
    """Lista de (jogo, p_mandante) na ordem dos jogos, mais o estado final.

    Jogos sem resultado recebem previsão mas não mexem no Elo.
    `extra` (opcional, para estudos): {game_id: pontos de Elo a favor do mandante}.
    """
    extra = extra or {}
    params = params or DEFAULT_PARAMS
    elo, team_season, last_day = {}, {}, {}
    predictions = []
    for game in games:
        day = game_day(game["start_utc"])
        b2b = {}
        for team in (game["home"], game["away"]):
            if team_season.get(team) not in (None, game["season"]):
                elo[team] = MEAN_ELO + (1 - params["regress"]) * (elo[team] - MEAN_ELO)
            team_season[team] = game["season"]
            previous = last_day.get(team)
            b2b[team] = previous is not None and (day - previous).days == 1
            last_day[team] = day
        home_elo = elo.get(game["home"], MEAN_ELO)
        away_elo = elo.get(game["away"], MEAN_ELO)
        diff = (home_elo + params["home"] - away_elo
                - params["b2b"] * b2b[game["home"]] + params["b2b"] * b2b[game["away"]]
                + extra.get(game["game_id"], 0.0))
        p_home = win_probability(diff)
        predictions.append((game, p_home))
        if game["home_pts"] is None:
            continue
        margin = game["home_pts"] - game["away_pts"]
        home_won = 1.0 if margin > 0 else 0.0
        winner_diff = diff if margin > 0 else -diff
        delta = params["k"] * mov_multiplier(margin, winner_diff) * (home_won - p_home)
        elo[game["home"]] = home_elo + delta
        elo[game["away"]] = away_elo - delta
    return predictions, elo


def log_loss(pairs):
    """pairs = [(p, y)]; perda logarítmica média."""
    total = 0.0
    for p, y in pairs:
        p = min(max(p, 1e-6), 1 - 1e-6)
        total -= y * math.log(p) + (1 - y) * math.log(1 - p)
    return total / len(pairs)


def brier(pairs):
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def scored(predictions, seasons):
    return [(p, 1 if g["home_pts"] > g["away_pts"] else 0)
            for g, p in predictions
            if g["season"] in seasons and g["home_pts"] is not None]


def fit(games):
    """Busca em grade pela menor log loss nas temporadas de ajuste."""
    best = None
    keys = list(GRID)
    for values in itertools.product(*(GRID[k] for k in keys)):
        params = dict(zip(keys, map(float, values)))
        predictions, _ = walk_forward(games, params)
        loss = log_loss(scored(predictions, FIT_SEASONS))
        if best is None or loss < best[0]:
            best = (loss, params)
    return best


def params_version(params):
    """Impressão digital dos parâmetros: muda se alguém mexer no modelo."""
    text = json.dumps(params, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def load_params():
    try:
        with open(PARAMS_JSON, encoding="utf-8") as handle:
            return json.load(handle)["params"]
    except FileNotFoundError:
        return dict(DEFAULT_PARAMS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit", action="store_true")
    args = parser.parse_args()
    games = read_games()
    if args.fit:
        loss, params = fit(games)
        with open(PARAMS_JSON, "w", encoding="utf-8") as handle:
            json.dump({"params": params, "fit_seasons": [min(FIT_SEASONS), max(FIT_SEASONS)],
                       "fit_log_loss": round(loss, 5), "version": params_version(params)},
                      handle, indent=2)
        print(f"melhor ajuste em {min(FIT_SEASONS)}-{max(FIT_SEASONS)}: {params} log loss {loss:.4f}")
    params = load_params()
    predictions, _ = walk_forward(games, params)
    for season in sorted({g["season"] for g in games}):
        pairs = scored(predictions, [season])
        if not pairs:
            continue
        hits = sum(1 for p, y in pairs if (p > 0.5) == (y == 1)) / len(pairs)
        tag = "ajuste" if season in FIT_SEASONS else ("aquecimento" if season < min(FIT_SEASONS) else "FORA do ajuste")
        print(f"{season}-{(season + 1) % 100:02d}: {len(pairs):4d} jogos  log loss {log_loss(pairs):.4f}  "
              f"Brier {brier(pairs):.4f}  acerto {hits:.1%}  ({tag})")


if __name__ == "__main__":
    main()
