"""Baixa calendário e resultados da temporada regular (fixturedownload.com).

Uma requisição por temporada. As temporadas antigas ficam em cache; a atual
é baixada de novo a cada execução, porque os resultados vão chegando.

Uso:  python fetch_results.py
"""
import argparse
import csv
import io
import os

from nba_common import CACHE, current_season, http_get, parse_fixture_rows, write_games

FIRST_SEASON = 2018  # 2015-2017 não existem lá


def fixture_text(season, refresh):
    path = os.path.join(CACHE, f"fixture_{season}.csv")
    if refresh or not os.path.exists(path):
        text = http_get(f"https://fixturedownload.com/download/nba-{season}-UTC.csv")
        os.makedirs(CACHE, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return handle.read()


def load_all_games(refresh_current=True):
    games = []
    last = current_season()
    for season in range(FIRST_SEASON, last + 1):
        text = fixture_text(season, refresh=refresh_current and season == last)
        games.extend(parse_fixture_rows(csv.DictReader(io.StringIO(text)), season))
    games.sort(key=lambda g: (g["start_utc"], g["game_id"]))
    return games


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="não baixar de novo a temporada atual")
    args = parser.parse_args()
    games = load_all_games(refresh_current=not args.offline)
    write_games(games)
    played = sum(1 for g in games if g["home_pts"] is not None)
    print(f"{len(games)} jogos ({played} com resultado) em data/games.csv")


if __name__ == "__main__":
    main()
