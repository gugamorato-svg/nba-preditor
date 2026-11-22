"""Preço pré-jogo da Polymarket para cada jogo da NBA já encerrado.

1. Lista os eventos de jogo da série NBA (gamma-api, só leitura, sem chave).
2. Pega o mercado moneyline e o token do MANDANTE.
3. Lê o histórico de preço (clob prices-history) e guarda o último preço
   registrado pelo menos LEAD_MINUTES antes do início.

Esse preço é o do histórico (perto do meio do livro), não o ask: o ROI em
evaluate.py cobra taxa de taker e uma derrapagem por cima para compensar.

Uso:  python fetch_polymarket.py            (usa cache, busca só o que falta)
      python fetch_polymarket.py --refresh  (relista os eventos)
"""
import argparse
import csv
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from nba_common import (CACHE, MARKET_CSV, NICKNAME_TO_TEAM, cached_json, http_get_json,
                        index_by_pair, match_game, parse_utc, read_games)

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
NBA_SERIES_ID = 10345
GAME_SLUG = re.compile("^nba-[a-z]{3}-[a-z]{3}-[0-9]{4}-[0-9]{2}-[0-9]{2}$")
LEAD_MINUTES = 60      # preço de referência: 1h antes do jogo
MAX_STALE_MINUTES = 360  # se o último preço for mais velho que isso, descarta

MARKET_COLUMNS = ["slug", "game_id", "start_utc", "home", "away", "home_token",
                  "p_home", "price_utc", "minutes_before", "volume", "resolved_home_win"]


def list_game_events(closed=True):
    """Todos os eventos de jogo da série (paginado de 100 em 100)."""
    events, offset = [], 0
    state = "true" if closed else "false"
    while True:
        page = http_get_json(f"{GAMMA}/events?series_id={NBA_SERIES_ID}&closed={state}"
                             f"&limit=100&offset={offset}&order=startTime&ascending=true")
        if not page:
            break
        for event in page:
            if GAME_SLUG.match(event.get("slug", "")):
                # Cada jogo tem ~500 mercados (props); só o moneyline interessa.
                moneyline = [m for m in event.get("markets", []) if m.get("sportsMarketType") == "moneyline"]
                events.append({"slug": event["slug"], "markets": moneyline})
        offset += len(page)
    return events


def moneyline_info(event):
    """(início, {time: token}, preços finais) do mercado moneyline, ou None."""
    for market in event.get("markets", []):
        if market.get("sportsMarketType") != "moneyline":
            continue
        outcomes = json.loads(market["outcomes"])
        tokens = json.loads(market["clobTokenIds"])
        prices = json.loads(market.get("outcomePrices") or "[]")
        teams = [NICKNAME_TO_TEAM.get(name) for name in outcomes]
        if None in teams or len(teams) != 2 or not market.get("gameStartTime"):
            return None
        return {
            "start": parse_utc(market["gameStartTime"]),
            "token": dict(zip(teams, tokens)),
            "final": dict(zip(teams, prices)),
            "volume": float(market.get("volumeNum") or market.get("volume") or 0),
        }
    return None


def price_before(token, start, lead_minutes=LEAD_MINUTES):
    """Último ponto do histórico com pelo menos lead_minutes antes do início."""
    start_ts = int(start.timestamp())
    end_ts = start_ts - lead_minutes * 60

    def fetch():
        url = (f"{CLOB}/prices-history?market={token}&startTs={end_ts - MAX_STALE_MINUTES * 60}"
               f"&endTs={end_ts}&fidelity=5")
        return http_get_json(url, pause=0.15).get("history", [])

    history = cached_json(os.path.join("prices", f"{token}_{end_ts}.json"), fetch)
    points = [p for p in history if p["t"] <= end_ts]
    if not points:
        return None
    last = max(points, key=lambda p: p["t"])
    return last["p"], last["t"], (start_ts - last["t"]) / 60


def build_rows(events, games, workers=4):
    pairs = index_by_pair(games)
    rows, skipped = [], {"sem_moneyline": 0, "sem_preco": 0}
    jobs = []
    for event in events:
        info = moneyline_info(event)
        if info is None:
            skipped["sem_moneyline"] += 1
            continue
        team_a, team_b = list(info["token"])
        game = match_game(pairs, team_a, team_b, info["start"])
        if game:
            home, away, game_id = game["home"], game["away"], game["game_id"]
        else:
            # pré-temporada, playoffs ou play-in: o slug traz o visitante primeiro
            home, away, game_id = team_b, team_a, ""
        jobs.append((event, info, home, away, game_id))

    # Poucas conexões em paralelo: rápido o bastante sem martelar a API.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        prices = list(pool.map(lambda job: price_before(job[1]["token"][job[2]], job[1]["start"]), jobs))

    for (event, info, home, away, game_id), found in zip(jobs, prices):
        if found is None:
            skipped["sem_preco"] += 1
            continue
        price, ts, minutes = found
        final_home = info["final"].get(home)
        resolved = "" if final_home not in ("0", "1") else int(final_home == "1")
        rows.append({
            "slug": event["slug"],
            "game_id": game_id,
            "start_utc": info["start"].isoformat(),
            "home": home,
            "away": away,
            "home_token": info["token"][home],
            "p_home": price,
            "price_utc": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
            "minutes_before": round(minutes, 1),
            "volume": round(info["volume"]),
            "resolved_home_win": resolved,
        })
    return rows, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="relistar os eventos encerrados")
    args = parser.parse_args()
    games = read_games()
    events = cached_json("pm_events_closed.json", list_game_events, refresh=args.refresh)
    print(f"{len(events)} eventos de jogo encerrados")
    rows, skipped = build_rows(events, games)
    with open(MARKET_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MARKET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    matched = sum(1 for r in rows if r["game_id"])
    print(f"{len(rows)} preços gravados em data/market.csv ({matched} casados com a temporada regular); "
          f"descartados: {skipped}")


if __name__ == "__main__":
    main()
