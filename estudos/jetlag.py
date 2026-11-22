"""Estudo da teoria do jetlag. Regras em estudos/jetlag.md (pré-registro).

Uso:  python estudos/jetlag.py
"""
import csv
import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluate import bootstrap_ci, mean  # noqa: E402
from model import FIT_SEASONS, load_params, walk_forward  # noqa: E402
from nba_common import CACHE, MARKET_CSV, game_day, read_csv, read_games  # noqa: E402

# Arena de cada time: (latitude, longitude, fuso UTC no inverno).
ARENAS = {
    "Atlanta Hawks": (33.757, -84.396, -5), "Boston Celtics": (42.366, -71.062, -5),
    "Brooklyn Nets": (40.683, -73.976, -5), "Charlotte Hornets": (35.225, -80.839, -5),
    "Chicago Bulls": (41.881, -87.674, -6), "Cleveland Cavaliers": (41.496, -81.688, -5),
    "Dallas Mavericks": (32.790, -96.810, -6), "Denver Nuggets": (39.749, -105.008, -7),
    "Detroit Pistons": (42.341, -83.055, -5), "Golden State Warriors": (37.768, -122.388, -8),
    "Houston Rockets": (29.751, -95.362, -6), "Indiana Pacers": (39.764, -86.156, -5),
    "LA Clippers": (33.945, -118.343, -8), "Los Angeles Lakers": (34.043, -118.267, -8),
    "Memphis Grizzlies": (35.138, -90.051, -6), "Miami Heat": (25.781, -80.188, -5),
    "Milwaukee Bucks": (43.045, -87.917, -6), "Minnesota Timberwolves": (44.979, -93.276, -6),
    "New Orleans Pelicans": (29.949, -90.082, -6), "New York Knicks": (40.751, -73.993, -5),
    "Oklahoma City Thunder": (35.463, -97.515, -6), "Orlando Magic": (28.539, -81.384, -5),
    "Philadelphia 76ers": (39.901, -75.172, -5), "Phoenix Suns": (33.446, -112.071, -7),
    "Portland Trail Blazers": (45.532, -122.667, -8), "Sacramento Kings": (38.580, -121.500, -8),
    "San Antonio Spurs": (29.427, -98.438, -6), "Toronto Raptors": (43.643, -79.379, -5),
    "Utah Jazz": (40.768, -111.901, -7), "Washington Wizards": (38.898, -77.021, -5),
}
# Locais neutros ou temporários que aparecem na coluna Location.
SPECIAL_VENUES = {
    "Amalie Arena": (27.943, -82.452, -5),          # Raptors em Tampa, 2020-21
    "AdventHealth Arena": (28.337, -81.556, -5),    # bolha de Orlando, 2020
    "VISA Athletic Center": (28.337, -81.556, -5),
    "The Field House": (28.337, -81.556, -5),
    "T-Mobile Arena": (36.103, -115.178, -8),       # Copa NBA, Las Vegas
    "Moody Center": (30.288, -97.732, -6),          # Austin
    "Alamodome": (29.417, -98.479, -6),
    "Hinkle Fieldhouse": (39.839, -86.169, -5),
    "Accor Arena": (48.839, 2.379, 1), "AccorHotels Arena": (48.839, 2.379, 1),
    "Arena Ciudad de Mexico": (19.495, -99.170, -6), "Arena CDMX": (19.495, -99.170, -6),
    "Mexico City Arena": (19.495, -99.170, -6),
    "The O2 Arena": (51.503, 0.003, 0), "Co-op Live": (53.486, -2.199, 0),
    "Uber Arena": (52.507, 13.443, 1),
}

MIN_ZONES, MAX_DAYS = 2, 2           # definição principal (pré-registrada)
J_GRID = [0, 10, 20, 30, 40, 50, 60, 80]


def venue_by_game():
    """game_id -> nome do local, lido dos CSVs do fixturedownload em cache."""
    venues = {}
    for name in os.listdir(CACHE):
        if not (name.startswith("fixture_") and name.endswith(".csv")):
            continue
        season = int(name[8:12])
        with open(os.path.join(CACHE, name), encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                venues[f"{season}-{int(row['Match Number']):04d}"] = row["Location"].strip()
    return venues


def place(game, venues):
    return SPECIAL_VENUES.get(venues.get(game["game_id"], ""), ARENAS[game["home"]])


def km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def travel_features(games):
    """game_id -> {mandante/visitante: (dias, fusos com sinal, km, jet)}. Só usa o calendário."""
    venues = venue_by_game()
    last = {}  # time -> (dia, local)
    features = {}
    for game in games:
        here = place(game, venues)
        day = game_day(game["start_utc"])
        row = {}
        for side, team in (("home", game["home"]), ("away", game["away"])):
            if team in last:
                previous_day, previous_place = last[team]
                days = (day - previous_day).days
                zones = here[2] - previous_place[2]
                distance = km(previous_place, here)
            else:
                days, zones, distance = 99, 0, 0.0
            jet = int(abs(zones) >= MIN_ZONES and days <= MAX_DAYS)
            row[side] = (days, zones, distance, jet)
            last[team] = (day, here)
        features[game["game_id"]] = row
    return features


def jet_diff(feature):
    return feature["away"][3] - feature["home"][3]


def per_game_loss(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def outcome(game):
    return 1 if game["home_pts"] > game["away_pts"] else 0


def main():
    games = read_games()
    params = load_params()
    features = travel_features(games)
    played = [g for g in games if g["home_pts"] is not None]

    print("== Quantos jogos têm jetlag (definição principal) ==")
    flagged = [g for g in played if jet_diff(features[g["game_id"]]) != 0]
    print(f"{len(flagged)} de {len(played)} jogos ({len(flagged) / len(played):.1%}) têm jet só de um lado")

    # 0) Descritivo: desempenho do time com jet contra o que o Elo esperava.
    base, _ = walk_forward(games, params)
    base_p = {g["game_id"]: p for g, p in base}
    residuals = []
    for g in flagged:
        d = jet_diff(features[g["game_id"]])  # +1 = visitante cansado (ajuda o mandante)
        residuals.append(d * (outcome(g) - base_p[g["game_id"]]))
    low, high = bootstrap_ci(residuals, mean)
    print(f"[descritivo] lado SEM jet vence {mean(residuals):+.1%} acima do Elo "
          f"(IC95 {low:+.1%} a {high:+.1%}, n={len(residuals)})")

    # 1) Contra o Elo: ajusta J em 2019-2024, avalia fora.
    print()
    print("== Teste 1: contra o Elo ==")
    best = None
    for j in J_GRID:
        extra = {gid: j * jet_diff(f) for gid, f in features.items()}
        preds, _ = walk_forward(games, params, extra)
        pairs = [(p, outcome(g)) for g, p in preds if g["season"] in FIT_SEASONS and g["home_pts"] is not None]
        loss = mean([per_game_loss(p, y) for p, y in pairs])
        print(f"  J={j:3d}: log loss 2019-24 {loss:.5f}")
        if best is None or loss < best[0]:
            best = (loss, j)
    j = best[1]
    extra = {gid: j * jet_diff(f) for gid, f in features.items()}
    with_jet = {g["game_id"]: p for g, p in walk_forward(games, params, extra)[0]}
    test_games = [g for g in played if g["season"] >= 2025]
    diffs = [per_game_loss(with_jet[g["game_id"]], outcome(g)) - per_game_loss(base_p[g["game_id"]], outcome(g))
             for g in test_games]
    low, high = bootstrap_ci(diffs, mean)
    test1 = high < 0
    print(f"  melhor J (ajustado só em 2019-24) = {j}")
    print(f"  2025-27 fora da amostra: log loss com jet − sem jet = {mean(diffs):+.5f} "
          f"(IC95 {low:+.5f} a {high:+.5f}, n={len(diffs)}) -> {'MELHORA' if test1 else 'não melhora'}")

    # 2) Contra o mercado.
    print()
    print("== Teste 2: contra o preço da Polymarket ==")
    results = {g["game_id"]: g for g in played}
    market_res = []
    for m in read_csv(MARKET_CSV):
        g = results.get(m["game_id"])
        if not g:
            continue
        d = jet_diff(features[g["game_id"]])
        if d:
            market_res.append(d * (outcome(g) - float(m["p_home"])))
    if market_res:
        low, high = bootstrap_ci(market_res, mean)
        test2 = low > 0
        print(f"  lado SEM jet vence {mean(market_res):+.1%} acima do preço "
              f"(IC95 {low:+.1%} a {high:+.1%}, n={len(market_res)}) -> {'PASSA' if test2 else 'não passa'}")
    else:
        test2 = False
        print("  nenhum jogo com preço e jet")

    # Exploratório: direção e distância (não decide nada).
    print()
    print("== Exploratório (não decide) ==")
    for label, rule in (("viagem para o LESTE", lambda f: f[1] >= MIN_ZONES),
                        ("viagem para o OESTE", lambda f: f[1] <= -MIN_ZONES),
                        ("2000+ km com dias<=2 (qualquer fuso)", lambda f: f[2] >= 2000)):
        res = []
        for g in played:
            f = features[g["game_id"]]
            tired_home = rule(f["home"]) and f["home"][0] <= MAX_DAYS
            tired_away = rule(f["away"]) and f["away"][0] <= MAX_DAYS
            d = int(tired_away) - int(tired_home)
            if d:
                res.append(d * (outcome(g) - base_p[g["game_id"]]))
        if res:
            low, high = bootstrap_ci(res, mean)
            print(f"  {label}: lado descansado {mean(res):+.1%} acima do Elo (IC95 {low:+.1%} a {high:+.1%}, n={len(res)})")

    print()
    verdict = ("PASSA" if test2 else
               "REAL, MAS O MERCADO JÁ PRECIFICA" if test1 else "NÃO PASSA")
    print(f"VEREDITO (pelo pré-registro): {verdict}")
    print(f"(rodado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)")


if __name__ == "__main__":
    main()
