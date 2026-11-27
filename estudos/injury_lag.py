"""O preço da Polymarket reage antes ou depois da notícia de lesão? Regras em estudos/injury_lag.md.

Para cada NOTÍCIA de lesão (jogador que passa a "Out" na lista da ESPN), acha o próximo jogo do
time machucado em data/paper_log.csv e mede o preço DO TIME MACHUCADO em volta de `espn_utc`:

  principal  histórico minuto a minuto da Polymarket (clob prices-history, fidelity=1):
             preço 60 min antes, na hora da notícia e 60 min depois (ou até o jogo começar)
  conferência  as capturas de hora em hora do paper_log (antes / depois / 3 h antes)

As capturas de hora em hora não bastam: a última antes da notícia pode ter até ~1 h, então uma
queda que aconteceu ANTES da ESPN aparece como se fosse "depois". Por isso o veredito usa o
histórico por minuto. Notícias do mesmo time no mesmo jogo a menos de 60 min uma da outra viram
UM caso (o mesmo movimento de preço não pode contar várias vezes).

Negativo = o preço andou contra o time que perdeu o jogador.

Uso:  python estudos/injury_lag.py            (usa cache em data/cache/injury_lag/)
"""
import csv
import os
import statistics
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluate import bootstrap_ci, mean  # noqa: E402
from fetch_polymarket import CLOB, GAMMA, moneyline_info  # noqa: E402
from injuries import INJURIES_CSV  # noqa: E402
from nba_common import NICKNAME_TO_TEAM, PAPER_CSV, TEAMS, cached_json, http_get_json, parse_utc  # noqa: E402

WINDOW_MIN = 60          # minutos antes e depois da notícia
CLUSTER_MIN = 60         # notícias do mesmo jogo/time dentro disso viram um caso
EARLIER_HOURS = 3        # conferência pelas capturas: preço 3 h antes
MAX_HOURS_TO_GAME = 36   # horizonte do coletor; notícia mais longe que isso não é sobre esse jogo
SMALL_SAMPLE = 30
MOVE = 0.01              # 1 centavo


def team_name(raw):
    raw = raw.strip()
    return raw if raw in TEAMS else NICKNAME_TO_TEAM.get(raw)


def news_events(rows):
    """Notícias: jogador que vira Out vindo de outro status, ou entra na lista já Out.

    A primeira captura do registro é a lista que já existia (não é notícia), e um jogador fora
    há semanas gera linhas novas só porque a ESPN mexeu no comentário.
    """
    if not rows:
        return []
    first_capture = rows[0]["captured_utc"]
    last_status, events = {}, []
    for row in rows:
        key = (row["team"], row["player"])
        previous = last_status.get(key)
        if row["status"] == "Out":
            changed = previous is not None and previous != "Out"
            new_listing = previous is None and row["captured_utc"] != first_capture
            if changed or new_listing:
                events.append(row)
        last_status[key] = row["status"]
    return events


def side_mid(capture, side):
    """(bid+ask)/2 do lado pedido; sem livro desse lado, 1 − o do outro."""
    def mid(bid, ask):
        return (float(bid) + float(ask)) / 2 if bid and ask else None
    home = mid(capture["bid_home"], capture["ask_home"])
    away = mid(capture["bid_away"], capture["ask_away"])
    if side == "home":
        return home if home is not None else (1 - away if away is not None else None)
    return away if away is not None else (1 - home if home is not None else None)


def build_cases(injury_rows, paper_rows):
    captures = {}
    for row in paper_rows:
        row["_t"] = parse_utc(row["captured_utc"])
        row["_start"] = parse_utc(row["start_utc"])
        captures.setdefault(row["game_id"], []).append(row)
    for caps in captures.values():
        caps.sort(key=lambda r: r["_t"])
    games = {gid: caps[0] for gid, caps in captures.items()}

    cases, skipped = [], {"time_desconhecido": 0, "sem_jogo_capturado": 0}
    for event in sorted(news_events(injury_rows), key=lambda r: r["espn_utc"]):
        team = team_name(event["team"])
        if team is None:
            skipped["time_desconhecido"] += 1
            continue
        news_t = parse_utc(event["espn_utc"])
        upcoming = [g for g in games.values() if team in (g["home"], g["away"])
                    and news_t < g["_start"] <= news_t + timedelta(hours=MAX_HOURS_TO_GAME)]
        if not upcoming:
            skipped["sem_jogo_capturado"] += 1
            continue
        game = min(upcoming, key=lambda g: g["_start"])
        same =[c for c in cases if c["game_id"] == game["game_id"] and c["team"] == team
                and news_t - c["news"] <= timedelta(minutes=CLUSTER_MIN)]
        if same:
            same[-1]["players"].append(event["player"])
            continue
        side = "home" if team == game["home"] else "away"
        caps = [c for c in captures[game["game_id"]] if c["_t"] < game["_start"]]
        before = [c for c in caps if c["_t"] <= news_t]
        after = [c for c in caps if c["_t"] > news_t]
        earlier = [c for c in caps if c["_t"] <= news_t - timedelta(hours=EARLIER_HOURS)]
        cases.append({
            "game_id": game["game_id"], "slug": game["slug"], "team": team, "side": side,
            "players": [event["player"]], "news": news_t, "start": game["_start"],
            "cap_earlier": side_mid(earlier[-1], side) if earlier else None,
            "cap_before": side_mid(before[-1], side) if before else None,
            "cap_after": side_mid(after[0], side) if after else None,
        })
    return cases, skipped


def team_token(slug, team):
    def fetch():
        events = http_get_json(f"{GAMMA}/events?slug={slug}")
        return [{"slug": e["slug"], "markets": [m for m in e.get("markets", [])
                                                 if m.get("sportsMarketType") == "moneyline"]}
                for e in events]
    events = cached_json(os.path.join("injury_lag", f"event_{slug}.json"), fetch)
    info = moneyline_info(events[0]) if events else None
    return info["token"].get(team) if info else None


def minute_prices(token, news_t, start):
    """Pontos (ts, preço) de 3 h antes até 60 min depois da notícia, cortados no início do jogo."""
    begin = int((news_t - timedelta(hours=EARLIER_HOURS)).timestamp())
    end = int(min(news_t + timedelta(minutes=WINDOW_MIN), start).timestamp())

    def fetch():
        url = f"{CLOB}/prices-history?market={token}&startTs={begin}&endTs={end}&fidelity=1"
        return http_get_json(url, pause=0.15).get("history", [])
    return sorted(cached_json(os.path.join("injury_lag", f"{token}_{begin}_{end}.json"), fetch),
                  key=lambda p: p["t"])


def price_at(points, ts):
    """Último preço registrado até `ts`."""
    known = [p["p"] for p in points if p["t"] <= ts]
    return known[-1] if known else None


def add_minute_prices(case):
    case.update(m_before=None, m_news=None, m_after=None)
    token = team_token(case["slug"], case["team"])
    if not token:
        return
    points = minute_prices(token, case["news"], case["start"])
    t = int(case["news"].timestamp())
    end = min(t + WINDOW_MIN * 60, int(case["start"].timestamp()))
    case["m_before"] = price_at(points, t - WINDOW_MIN * 60)
    case["m_news"] = price_at(points, t)
    case["m_after"] = price_at(points, end) if end > t else None


def summarise(label, values):
    if not values:
        print(f"  {label}: sem casos")
        return None
    low, high = bootstrap_ci(values, mean) if len(values) > 1 else (values[0], values[0])
    down = sum(1 for v in values if v <= -MOVE)
    print(f"  {label}: n={len(values)}  média {mean(values) * 100:+.1f}c  mediana {statistics.median(values) * 100:+.1f}c  "
          f"IC95 [{low * 100:+.1f}c; {high * 100:+.1f}c]  caiu 1c+ em {down}")
    return mean(values), low, high


def fmt(p):
    return f"{p:.3f}" if p is not None else "  —  "


def main():
    for path in (INJURIES_CSV, PAPER_CSV):
        if not os.path.exists(path):
            print(f"falta {os.path.relpath(path)}: rode `python paper_collect.py` por alguns dias de jogo")
            return
    with open(INJURIES_CSV, newline="", encoding="utf-8") as handle:
        injury_rows = list(csv.DictReader(handle))
    with open(PAPER_CSV, newline="", encoding="utf-8") as handle:
        paper_rows = list(csv.DictReader(handle))

    cases, skipped = build_cases(injury_rows, paper_rows)
    for case in cases:
        add_minute_prices(case)
    events = len(news_events(injury_rows))
    print(f"notícias de lesão (viraram Out): {events} -> {len(cases)} casos (mesmo jogo/time em {CLUSTER_MIN} min = 1 caso) "
          f"| descartadas: {skipped}")
    print("Preço do TIME MACHUCADO. Por minuto = histórico da Polymarket; capturas = paper_log (médio bid/ask).")
    print()
    print(f"  {'notícia (UTC)':12} {'jogadores':30} {'time':22} | por minuto: -{WINDOW_MIN}m  notícia  +{WINDOW_MIN}m"
          f" | capturas: -{EARLIER_HOURS}h  antes  depois")
    for c in cases:
        who = ", ".join(c["players"])[:30]
        print(f"  {c['news']:%m-%d %H:%M}  {who:30} {c['team'][:22]:22} | {fmt(c['m_before'])}  {fmt(c['m_news'])}  "
              f"{fmt(c['m_after'])} | {fmt(c['cap_earlier'])}  {fmt(c['cap_before'])}  {fmt(c['cap_after'])}")

    minute = [c for c in cases if None not in (c["m_before"], c["m_news"], c["m_after"])]
    caps = [c for c in cases if c["cap_before"] is not None and c["cap_after"] is not None]
    print()
    print("=== Por minuto (decide o veredito) ===")
    pre = summarise(f"{WINDOW_MIN} min ANTES da notícia (notícia − antes)", [c["m_news"] - c["m_before"] for c in minute])
    post = summarise(f"{WINDOW_MIN} min DEPOIS da notícia (depois − notícia)", [c["m_after"] - c["m_news"] for c in minute])
    print()
    print("=== Capturas de hora em hora (só conferência: a janela abraça a notícia) ===")
    summarise(f"{EARLIER_HOURS} h antes -> última antes", [c["cap_before"] - c["cap_earlier"] for c in cases
                                                           if c["cap_before"] is not None and c["cap_earlier"] is not None])
    summarise("última antes -> primeira depois", [c["cap_after"] - c["cap_before"] for c in caps])

    print()
    if len(minute) < SMALL_SAMPLE:
        verdict = f"AMOSTRA PEQUENA ({len(minute)} < {SMALL_SAMPLE} casos com preço por minuto): sem veredito"
    elif post and post[0] <= -MOVE and post[2] < 0:
        verdict = "HÁ ATRASO: o preço ainda cai depois da notícia da ESPN"
    elif pre and pre[2] < 0:
        verdict = "O MERCADO SE ANTECIPA: o preço cai antes da notícia da ESPN e não anda depois"
    else:
        verdict = "SEM EFEITO VISÍVEL em volta da notícia"
    print(f"VEREDITO (regras em estudos/injury_lag.md): {verdict}")


if __name__ == "__main__":
    main()
