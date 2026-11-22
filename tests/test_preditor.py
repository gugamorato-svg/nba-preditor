import csv
import io
from datetime import datetime, timedelta, timezone

import pytest

from evaluate import blend, simulate_bets
from fetch_polymarket import moneyline_info
from model import DEFAULT_PARAMS, walk_forward
from nba_common import (TEAMS, game_day, index_by_pair, match_game, parse_fixture_rows, parse_utc,
                        taker_cost)

FIXTURE = """Match Number,Round Number,Date,Location,Home Team,Away Team,Result
1,1,21/10/2025 23:30,Paycom Center,Oklahoma City Thunder,Houston Rockets,125 - 124
2,1,22/10/2025 02:00,Crypto.com Arena,Los Angeles Lakers,Golden State Warriors,109 - 119
3,1,23/10/2025 00:00,Somewhere,To be announced,Boston Celtics,
4,1,24/10/2025 00:00,TD Garden,Boston Celtics,Miami Heat,
"""


def parse(text=FIXTURE, season=2025):
    return parse_fixture_rows(csv.DictReader(io.StringIO(text)), season)


def test_fixture_result_is_home_first_and_skips_placeholders():
    games = parse()
    assert [g["game_id"] for g in games] == ["2025-0001", "2025-0002", "2025-0004"]
    okc, lal, bos = games
    assert (okc["home"], okc["home_pts"], okc["away_pts"]) == ("Oklahoma City Thunder", 125, 124)
    assert (lal["home_pts"], lal["away_pts"]) == (109, 119)
    assert bos["home_pts"] is None
    assert okc["start_utc"] == datetime(2025, 10, 21, 23, 30, tzinfo=timezone.utc)


def test_game_day_puts_late_utc_tipoff_on_the_us_evening():
    assert str(game_day(datetime(2025, 10, 22, 2, 0, tzinfo=timezone.utc))) == "2025-10-21"


def test_parse_utc_formats():
    expected = datetime(2026, 4, 4, 23, 0, tzinfo=timezone.utc)
    assert parse_utc("2026-04-04 23:00:00+00") == expected
    assert parse_utc("2026-04-04T23:00:00Z") == expected


def test_every_team_has_a_unique_nickname():
    assert len(TEAMS) == 30
    assert len(set(TEAMS.values())) == 30


def test_taker_cost_adds_fee_and_slippage():
    assert taker_cost(0.5) == pytest.approx(0.5 + 0.05 * 0.25)
    assert taker_cost(0.8, slippage=0.005) == pytest.approx(0.8 + 0.05 * 0.16 + 0.005)


def synthetic_season(n=60, seed=7):
    import random
    rng = random.Random(seed)
    teams = sorted(TEAMS)[:6]
    start = datetime(2025, 10, 21, 23, 0, tzinfo=timezone.utc)
    games = []
    for i in range(n):
        home, away = rng.sample(teams, 2)
        games.append({"game_id": f"g{i:03d}", "season": 2025, "start_utc": start + timedelta(hours=20 * i),
                      "home": home, "away": away,
                      "home_pts": 100 + rng.randrange(30), "away_pts": 100 + rng.randrange(30)})
    return games


def test_prediction_never_sees_its_own_result():
    """Mudar o placar do jogo i não pode mudar a previsão do jogo i nem as anteriores."""
    games = synthetic_season()
    before, _ = walk_forward(games, DEFAULT_PARAMS)
    for i in (0, 17, 42):
        changed = [dict(g) for g in games]
        changed[i]["home_pts"], changed[i]["away_pts"] = changed[i]["away_pts"] + 40, changed[i]["home_pts"]
        after, _ = walk_forward(changed, DEFAULT_PARAMS)
        assert [p for _, p in after[: i + 1]] == [p for _, p in before[: i + 1]]
        assert any(a != b for (_, a), (_, b) in zip(after[i + 1:], before[i + 1:]))


def test_unplayed_games_get_a_prediction_but_do_not_move_elo():
    games = synthetic_season(10)
    games[5]["home_pts"] = games[5]["away_pts"] = None
    predictions, _ = walk_forward(games, DEFAULT_PARAMS)
    assert len(predictions) == 10
    # O jogo 5 sem placar só pode influenciar via calendário (descanso), não pelo Elo.
    params = dict(DEFAULT_PARAMS, b2b=0.0)
    with_gap = [p for g, p in walk_forward(games, params)[0] if g["game_id"] != "g005"]
    without_gap = [p for _, p in walk_forward(games[:5] + games[6:], params)[0]]
    assert with_gap == pytest.approx(without_gap)


def test_back_to_back_lowers_the_tired_team():
    base = datetime(2025, 11, 1, 0, 0, tzinfo=timezone.utc)
    a, b, c = "Boston Celtics", "Miami Heat", "Utah Jazz"
    rested = [{"game_id": "1", "season": 2025, "start_utc": base, "home": c, "away": b, "home_pts": 100, "away_pts": 99},
              {"game_id": "2", "season": 2025, "start_utc": base + timedelta(days=3), "home": a, "away": b,
               "home_pts": None, "away_pts": None}]
    tired = [dict(rested[0], home=c, away=a), dict(rested[1])]
    p_rested = walk_forward(rested, DEFAULT_PARAMS)[0][1][1]
    tired[1]["start_utc"] = base + timedelta(days=1)
    p_home_tired = walk_forward(tired, DEFAULT_PARAMS)[0][1][1]
    # No 2º jogo o mandante (Celtics) vem de jogo na véspera em `tired`.
    assert p_home_tired < p_rested


def test_match_game_by_pair_and_time():
    games = parse()
    index = index_by_pair(games)
    found = match_game(index, "Golden State Warriors", "Los Angeles Lakers",
                       datetime(2025, 10, 22, 2, 30, tzinfo=timezone.utc))
    assert found["game_id"] == "2025-0002"
    assert match_game(index, "Golden State Warriors", "Los Angeles Lakers",
                      datetime(2025, 10, 25, tzinfo=timezone.utc)) is None


def test_moneyline_info_reads_polymarket_market():
    event = {"slug": "nba-det-phi-2026-04-04", "markets": [{
        "sportsMarketType": "moneyline", "gameStartTime": "2026-04-04 23:00:00+00",
        "outcomes": '["Pistons", "76ers"]', "outcomePrices": '["1", "0"]',
        "clobTokenIds": '["111", "222"]', "volumeNum": 1234.5}]}
    info = moneyline_info(event)
    assert info["token"] == {"Detroit Pistons": "111", "Philadelphia 76ers": "222"}
    assert info["final"]["Detroit Pistons"] == "1"
    assert info["start"] == datetime(2026, 4, 4, 23, 0, tzinfo=timezone.utc)


def test_injuries_only_new_or_changed_rows_are_appended(tmp_path):
    from injuries import append_new, parse_injuries
    payload = {"injuries": [{"displayName": "New York Knicks", "injuries": [
        {"status": "Out", "date": "2026-11-21T20:55Z", "shortComment": "Robinson (illness)  is out.",
         "athlete": {"displayName": "Mitchell Robinson"}}]}]}
    path = tmp_path / "inj.csv"
    now = datetime(2026, 11, 21, 21, 0, tzinfo=timezone.utc)
    rows = parse_injuries(payload)
    assert rows[0]["comment"] == "Robinson (illness) is out."
    assert append_new(rows, now, path) == 1
    assert append_new(rows, now, path) == 0  # mesma situação: nada novo
    payload["injuries"][0]["injuries"][0].update(status="Day-To-Day", date="2026-11-22T15:00Z")
    assert append_new(parse_injuries(payload), now, path) == 1
    with open(path, newline="", encoding="utf-8") as handle:
        assert [r["status"] for r in csv.DictReader(handle)] == ["Out", "Day-To-Day"]


def test_blend_endpoints():
    assert blend(0.7, 0.4, 0.0) == pytest.approx(0.4)
    assert blend(0.7, 0.4, 1.0) == pytest.approx(0.7)


def test_simulated_bet_pays_net_of_fee():
    rows = [{"p_model": 0.70, "p_market": 0.50, "y": 1}, {"p_model": 0.52, "p_market": 0.50, "y": 0}]
    profits = simulate_bets(rows, "p_model", threshold=0.03, slippage=0.0)
    cost = 0.5 + 0.05 * 0.25
    assert profits == [pytest.approx(1 / cost - 1)]  # o 2º jogo não passa no limiar
