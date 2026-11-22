"""Relatório de lesões da ESPN, guardado só quando muda.

A cada captura lê a lista atual (endpoint público, sem chave) e acrescenta em
data/injuries_log.csv apenas as linhas novas: jogador que entrou na lista ou
que mudou de status. O campo `espn_utc` é a hora da atualização na ESPN; com
ele e o preço em data/paper_log.csv dá para medir, depois, quanto tempo a
Polymarket leva para reagir a uma notícia.

A ESPN só mostra a situação atual, sem histórico: o que não for capturado
agora não volta.

Uso:  python injuries.py   (também roda dentro de paper_collect.py)
"""
import csv
import os
from datetime import datetime, timezone

from nba_common import DATA, http_get_json

INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
INJURIES_CSV = os.path.join(DATA, "injuries_log.csv")
INJURY_COLUMNS = ["captured_utc", "espn_utc", "team", "player", "status", "comment"]


def parse_injuries(payload):
    """JSON da ESPN -> lista de dicts (time, jogador, status, hora, comentário curto)."""
    rows = []
    for team in payload.get("injuries", []):
        for item in team.get("injuries", []):
            athlete = item.get("athlete") or {}
            rows.append({
                "espn_utc": item.get("date", ""),
                "team": team.get("displayName", ""),
                "player": athlete.get("displayName", ""),
                "status": item.get("status", ""),
                "comment": " ".join((item.get("shortComment") or "").split())[:300],
            })
    return rows


def state_key(row):
    """O que define "mudou": mesmo jogador, mesmo status, mesma atualização da ESPN."""
    return (row["team"], row["player"], row["status"], row["espn_utc"])


def append_new(rows, now, path=INJURIES_CSV):
    """Acrescenta só as linhas ainda não vistas. Devolve quantas entraram."""
    seen = set()
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as handle:
            seen = {state_key(r) for r in csv.DictReader(handle)}
    new = [r for r in rows if state_key(r) not in seen]
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=INJURY_COLUMNS)
        if new_file:
            writer.writeheader()
        for row in new:
            writer.writerow({"captured_utc": now.isoformat(timespec="seconds"), **row})
    return len(new)


def capture(now=None):
    now = now or datetime.now(timezone.utc)
    rows = parse_injuries(http_get_json(INJURIES_URL))
    return len(rows), append_new(rows, now)


def main():
    total, new = capture()
    print(f"lesões na lista da ESPN: {total}; novas ou alteradas gravadas: {new}")


if __name__ == "__main__":
    main()
