from estudos.injury_lag import build_cases, news_events, price_at, side_mid


def injury(captured, espn, player, status, team="Oklahoma City Thunder"):
    return {"captured_utc": captured, "espn_utc": espn, "team": team, "player": player,
            "status": status, "comment": ""}


def capture(captured, bid_home="0.50", ask_home="0.52", bid_away="0.48", ask_away="0.50"):
    return {"captured_utc": captured, "slug": "nba-okc-mia-2026-11-22", "game_id": "2026-0300",
            "start_utc": "2026-11-22T23:00:00+00:00", "home": "Miami Heat",
            "away": "Oklahoma City Thunder", "bid_home": bid_home, "ask_home": ask_home,
            "bid_away": bid_away, "ask_away": ask_away}


def test_news_is_a_change_to_out_not_the_first_snapshot_or_a_comment_update():
    rows = [
        injury("2026-11-21T20:00:00+00:00", "2026-11-20T10:00Z", "Already Out", "Out"),      # lista inicial
        injury("2026-11-21T20:00:00+00:00", "2026-11-20T11:00Z", "Doubtful Guy", "Day-To-Day"),
        injury("2026-11-21T21:00:00+00:00", "2026-11-21T20:30Z", "Already Out", "Out"),      # só o comentário
        injury("2026-11-21T22:00:00+00:00", "2026-11-21T21:30Z", "Doubtful Guy", "Out"),     # mudou: notícia
        injury("2026-11-21T22:00:00+00:00", "2026-11-21T21:40Z", "New Guy", "Out"),          # entrou já Out
    ]
    assert [r["player"] for r in news_events(rows)] == ["Doubtful Guy", "New Guy"]


def test_price_is_the_injured_teams_side():
    row = capture("2026-11-22T20:00:00+00:00")
    assert side_mid(row, "home") == 0.51
    assert side_mid(row, "away") == 0.49
    no_away_book = capture("2026-11-22T20:00:00+00:00", bid_away="", ask_away="")
    assert abs(side_mid(no_away_book, "away") - 0.49) < 1e-9


def test_same_game_news_within_an_hour_is_one_case_and_capture_sides():
    rows = [
        injury("2026-11-22T10:00:00+00:00", "2026-11-22T09:00Z", "A", "Day-To-Day"),
        injury("2026-11-22T10:00:00+00:00", "2026-11-22T09:01Z", "B", "Day-To-Day"),
        injury("2026-11-22T21:00:00+00:00", "2026-11-22T20:30Z", "A", "Out"),
        injury("2026-11-22T21:00:00+00:00", "2026-11-22T20:40Z", "B", "Out"),
    ]
    paper = [capture("2026-11-22T20:00:00+00:00", bid_away="0.48", ask_away="0.50"),
             capture("2026-11-22T21:00:00+00:00", bid_away="0.38", ask_away="0.40")]
    cases, skipped = build_cases(rows, paper)
    assert skipped == {"time_desconhecido": 0, "sem_jogo_capturado": 0}
    assert len(cases) == 1 and cases[0]["players"] == ["A", "B"]
    assert cases[0]["side"] == "away"
    assert abs(cases[0]["cap_before"] - 0.49) < 1e-9 and abs(cases[0]["cap_after"] - 0.39) < 1e-9


def test_price_at_takes_the_last_point_not_after_the_time():
    points = [{"t": 100, "p": 0.5}, {"t": 160, "p": 0.4}, {"t": 220, "p": 0.3}]
    assert price_at(points, 159) == 0.5
    assert price_at(points, 160) == 0.4
    assert price_at(points, 99) is None
