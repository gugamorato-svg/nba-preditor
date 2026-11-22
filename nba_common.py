"""Funções comuns: download com cache, nomes dos times e leitura dos CSVs.

Só biblioteca padrão do Python. Nada aqui aposta ou mexe em carteira:
o projeto só lê dados públicos.
"""
import csv
import gzip
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

# O console do Windows (cp1252) quebra com acentos e sinais como "−" quando a saída é redirecionada.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(DATA, "cache")
REPORTS = os.path.join(ROOT, "reports")

GAMES_CSV = os.path.join(DATA, "games.csv")
MARKET_CSV = os.path.join(DATA, "market.csv")
PARAMS_JSON = os.path.join(DATA, "model_params.json")
PAPER_CSV = os.path.join(DATA, "paper_log.csv")

USER_AGENT = "nba-preditor/0.1 (estudo pessoal, sem apostas)"

# Nome completo no fixturedownload -> apelido usado nos outcomes da Polymarket.
TEAMS = {
    "Atlanta Hawks": "Hawks",
    "Boston Celtics": "Celtics",
    "Brooklyn Nets": "Nets",
    "Charlotte Hornets": "Hornets",
    "Chicago Bulls": "Bulls",
    "Cleveland Cavaliers": "Cavaliers",
    "Dallas Mavericks": "Mavericks",
    "Denver Nuggets": "Nuggets",
    "Detroit Pistons": "Pistons",
    "Golden State Warriors": "Warriors",
    "Houston Rockets": "Rockets",
    "Indiana Pacers": "Pacers",
    "LA Clippers": "Clippers",
    "Los Angeles Lakers": "Lakers",
    "Memphis Grizzlies": "Grizzlies",
    "Miami Heat": "Heat",
    "Milwaukee Bucks": "Bucks",
    "Minnesota Timberwolves": "Timberwolves",
    "New Orleans Pelicans": "Pelicans",
    "New York Knicks": "Knicks",
    "Oklahoma City Thunder": "Thunder",
    "Orlando Magic": "Magic",
    "Philadelphia 76ers": "76ers",
    "Phoenix Suns": "Suns",
    "Portland Trail Blazers": "Trail Blazers",
    "Sacramento Kings": "Kings",
    "San Antonio Spurs": "Spurs",
    "Toronto Raptors": "Raptors",
    "Utah Jazz": "Jazz",
    "Washington Wizards": "Wizards",
}
NICKNAME_TO_TEAM = {nick: full for full, nick in TEAMS.items()}

GAME_COLUMNS = ["game_id", "season", "start_utc", "home", "away", "home_pts", "away_pts"]

# Taxa de taker da Polymarket nos jogos da NBA: feeSchedule {rate: 0.05, exponent: 1}.
TAKER_FEE_RATE = 0.05


def http_get(url, pause=0.25, retries=3):
    """GET com gzip e algumas tentativas. Devolve o corpo como texto."""
    last_error = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
            time.sleep(pause)
            return body.decode("utf-8")
        except Exception as error:  # rede instável: espera e tenta de novo
            last_error = error
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"falhou depois de {retries} tentativas: {url}: {last_error}")


def http_get_json(url, pause=0.25):
    return json.loads(http_get(url, pause=pause))


def cached_json(name, fetch, refresh=False):
    """Lê data/cache/<name> se existir; senão chama fetch() e grava."""
    path = os.path.join(CACHE, name)
    if not refresh and os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    value = fetch()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle)
    return value


def season_of(moment):
    """Temporada pelo ano de início: outubro de 2025 a junho de 2026 = 2025."""
    return moment.year if moment.month >= 8 else moment.year - 1


def current_season():
    return season_of(datetime.now(timezone.utc))


def parse_utc(text):
    """Aceita '2026-04-04 23:00:00+00', '2026-04-04T23:00:00Z' e ISO com offset."""
    text = text.strip().replace("Z", "+00:00")
    if text.endswith("+00"):
        text += ":00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def game_day(start_utc):
    """Data do jogo no fuso dos EUA (aprox.): um jogo às 00:30 UTC é da noite anterior."""
    return (start_utc - timedelta(hours=6)).date()


def parse_fixture_rows(rows, season):
    """Linhas do CSV do fixturedownload -> jogos. Resultado é 'mandante - visitante'."""
    games = []
    for row in rows:
        home, away = row["Home Team"].strip(), row["Away Team"].strip()
        if home not in TEAMS or away not in TEAMS:
            continue  # 'To be announced' (mata-mata da Copa) e afins
        start = datetime.strptime(row["Date"].strip(), "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
        home_pts = away_pts = None
        result = row.get("Result", "").strip()
        if result:
            left, right = result.split("-")
            home_pts, away_pts = int(left), int(right)
        games.append({
            "game_id": f"{season}-{int(row['Match Number']):04d}",
            "season": season,
            "start_utc": start,
            "home": home,
            "away": away,
            "home_pts": home_pts,
            "away_pts": away_pts,
        })
    return games


def read_games(path=GAMES_CSV):
    games = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            games.append({
                "game_id": row["game_id"],
                "season": int(row["season"]),
                "start_utc": parse_utc(row["start_utc"]),
                "home": row["home"],
                "away": row["away"],
                "home_pts": int(row["home_pts"]) if row["home_pts"] else None,
                "away_pts": int(row["away_pts"]) if row["away_pts"] else None,
            })
    games.sort(key=lambda g: (g["start_utc"], g["game_id"]))
    return games


def write_games(games, path=GAMES_CSV):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=GAME_COLUMNS)
        writer.writeheader()
        for game in games:
            row = dict(game)
            row["start_utc"] = game["start_utc"].isoformat()
            row["home_pts"] = "" if game["home_pts"] is None else game["home_pts"]
            row["away_pts"] = "" if game["away_pts"] is None else game["away_pts"]
            writer.writerow(row)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def taker_cost(price, slippage=0.0):
    """Custo real de 1 share comprada a `price`: preço + taxa de taker + derrapagem."""
    return price + TAKER_FEE_RATE * price * (1.0 - price) + slippage


def match_game(games_by_pair, team_a, team_b, start_utc, max_hours=12):
    """Acha o jogo do par de times mais perto de start_utc (no máximo max_hours)."""
    best = None
    for game in games_by_pair.get(frozenset((team_a, team_b)), []):
        gap = abs((game["start_utc"] - start_utc).total_seconds()) / 3600
        if gap <= max_hours and (best is None or gap < best[0]):
            best = (gap, game)
    return None if best is None else best[1]


def index_by_pair(games):
    index = {}
    for game in games:
        index.setdefault(frozenset((game["home"], game["away"])), []).append(game)
    return index
