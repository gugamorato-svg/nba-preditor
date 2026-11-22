"""Captura em papel: previsão do modelo e livro da Polymarket dos próximos jogos.

Só lê dados públicos e acrescenta linhas em data/paper_log.csv (nunca apaga).
Não envia ordens, não usa carteira nem chave.

Rode de hora em hora nos dias de jogo (por exemplo pelo Agendador de Tarefas).
O teste usa a última captura de cada jogo feita 30+ min antes do início
(veja PROTOCOLO.md e `python evaluate.py --paper`).

Uso:  python paper_collect.py
"""
import csv
import os
from datetime import datetime, timezone

import injuries
from fetch_polymarket import CLOB, list_game_events, moneyline_info
from fetch_results import load_all_games
from model import load_params, params_version, walk_forward
from nba_common import PAPER_CSV, http_get_json, index_by_pair, match_game, write_games

HORIZON_HOURS = 36

PAPER_COLUMNS = ["captured_utc", "slug", "game_id", "start_utc", "minutes_before", "home", "away",
                 "p_model", "bid_home", "ask_home", "mid_home", "bid_away", "ask_away",
                 "model_version"]


def best_quotes(token):
    """(melhor bid, melhor ask) do livro; None onde o lado está vazio."""
    book = http_get_json(f"{CLOB}/book?token_id={token}", pause=0.15)
    bids = [float(level["price"]) for level in book.get("bids", [])]
    asks = [float(level["price"]) for level in book.get("asks", [])]
    return (max(bids) if bids else None), (min(asks) if asks else None)


def collect(now=None):
    now = now or datetime.now(timezone.utc)
    games = load_all_games(refresh_current=True)
    write_games(games)
    params = load_params()
    version = params_version(params)
    predictions = {g["game_id"]: p for g, p in walk_forward(games, params)[0]}
    pairs = index_by_pair(games)

    rows = []
    for event in list_game_events(closed=False):
        info = moneyline_info(event)
        if info is None:
            continue
        minutes = (info["start"] - now).total_seconds() / 60
        if not 0 < minutes <= HORIZON_HOURS * 60:
            continue
        team_a, team_b = list(info["token"])
        game = match_game(pairs, team_a, team_b, info["start"])
        if game is None or game["home_pts"] is not None:
            continue  # fora da temporada regular, ou já jogado
        bid_home, ask_home = best_quotes(info["token"][game["home"]])
        bid_away, ask_away = best_quotes(info["token"][game["away"]])
        mid = (bid_home + ask_home) / 2 if bid_home is not None and ask_home is not None else None
        rows.append({
            "captured_utc": now.isoformat(timespec="seconds"),
            "slug": event["slug"],
            "game_id": game["game_id"],
            "start_utc": info["start"].isoformat(),
            "minutes_before": round(minutes, 1),
            "home": game["home"],
            "away": game["away"],
            "p_model": round(predictions[game["game_id"]], 4),
            "bid_home": bid_home if bid_home is not None else "",
            "ask_home": ask_home if ask_home is not None else "",
            "mid_home": round(mid, 4) if mid is not None else "",
            "bid_away": bid_away if bid_away is not None else "",
            "ask_away": ask_away if ask_away is not None else "",
            "model_version": version,
        })

    new_file = not os.path.exists(PAPER_CSV)
    with open(PAPER_CSV, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)
    return rows


def main():
    rows = collect()
    print(f"{len(rows)} jogos capturados em data/paper_log.csv")
    try:
        total, new = injuries.capture()
        print(f"lesões (ESPN): {total} na lista, {new} novas ou alteradas em data/injuries_log.csv")
    except Exception as error:  # a captura de preço não pode cair por causa da ESPN
        print(f"AVISO: não consegui ler as lesões da ESPN: {error}")
    for r in rows:
        print(f"  {r['start_utc'][:16]}  {r['away']} @ {r['home']}: modelo {float(r['p_model']):.1%} "
              f"mandante, mercado {r['mid_home'] or '?'} (ask {r['ask_home'] or '?'})")


if __name__ == "__main__":
    main()
