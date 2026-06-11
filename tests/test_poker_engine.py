"""Tests for the self-contained poker engine. Run: python -m pytest tests/ -q"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from itertools import combinations

from poker.cards import make_card, full_deck
from poker.coach import coach_insights, equity_breakdown
from poker.equity import equity
from poker.evaluator import evaluate, evaluate7, _score_5, category_name
from poker.ranges import normalize_hand
from poker.engine import Situation, decide
from poker.simulator import run_session


def cards(*ss):
    return [make_card(s) for s in ss]


# ---- evaluator ---------------------------------------------------------
def test_royal_flush_beats_quads():
    rf = evaluate(cards("Ah", "Kh", "Qh", "Jh", "Th"))
    quads = evaluate(cards("As", "Ad", "Ac", "Ah", "Kh"))
    assert rf > quads
    assert category_name(rf) == "Straight Flush"
    assert category_name(quads) == "Four of a Kind"


def test_wheel_straight():
    wheel = evaluate(cards("Ah", "2d", "3c", "4s", "5h"))
    assert category_name(wheel) == "Straight"


def test_full_house_over_flush():
    fh = evaluate(cards("Ah", "As", "Ad", "Kh", "Ks"))
    flush = evaluate(cards("2h", "5h", "8h", "Jh", "Kh"))
    assert fh > flush


def test_seven_card_picks_best():
    score = evaluate(cards("Ah", "Kh", "Qh", "Jh", "Th", "2c", "3d"))
    assert category_name(score) == "Straight Flush"


def test_two_pair_kicker():
    a = evaluate(cards("Ah", "As", "Kh", "Ks", "Qd"))
    b = evaluate(cards("Ah", "As", "Kh", "Ks", "Jd"))
    assert a > b


def test_fast_evaluator_matches_bruteforce():
    """evaluate7 must equal the combinatorial best-of-7 on random hands."""
    rng = random.Random(0)
    deck = full_deck()
    for _ in range(3000):
        rng.shuffle(deck)
        hand = deck[:7]
        brute = max(_score_5(c) for c in combinations(hand, 5))
        assert evaluate7(hand) == brute


# ---- equity ------------------------------------------------------------
def test_aa_crushes_preflop():
    rng = random.Random(42)
    eq = equity(cards("As", "Ad"), opponents=1, iterations=2000, rng=rng)
    assert eq > 0.8


def test_dominated_hand_low_equity():
    rng = random.Random(1)
    eq = equity(cards("7c", "2d"), opponents=1, iterations=2000, rng=rng)
    assert eq < 0.45


def test_made_flush_high_equity():
    rng = random.Random(7)
    eq = equity(cards("Ah", "Kh"), board=cards("Qh", "7h", "2h"),
                opponents=1, iterations=1500, rng=rng)
    assert eq > 0.85


def test_coach_insights_reports_flush_draw_and_outs():
    info = coach_insights(
        cards("Ah", "Kh"),
        cards("Qh", "7c", "2h"),
        opponents=2,
        iterations=120,
        rng=random.Random(9),
    )
    assert info["made_hand"] == "High Card"
    assert "flush draw" in info["draws"]
    assert info["outs"]["count"] >= 9
    assert info["outs"]["next_card_pct"] > 0.15
    assert info["outs"]["by_river_pct"] >= info["outs"]["next_card_pct"]
    assert info["heads_up_equity"] > info["equity_breakdown"]["equity"]


def test_equity_breakdown_is_normalized():
    bd = equity_breakdown(cards("As", "Ad"), board=cards("7h", "2c", "9d"),
                          opponents=2, iterations=150, rng=random.Random(4))
    total = bd["win_pct"] + bd["tie_pct"] + bd["lose_pct"]
    assert 0.99 <= total <= 1.01
    assert 0.0 <= bd["equity"] <= 1.0


# ---- ranges / engine ---------------------------------------------------
def test_normalize_hand():
    assert normalize_hand(make_card("As"), make_card("Ks")) == "AKs"
    assert normalize_hand(make_card("Ks"), make_card("Ah")) == "AKo"
    assert normalize_hand(make_card("Ad"), make_card("Ah")) == "AA"


def test_engine_opens_premium():
    s = Situation(hole=cards("As", "Ks"), board=[], position="BTN",
                  street="preflop", pot=1.5, to_call=1.0, hero_stack=100)
    d = decide(s)
    assert d.action == "raise"


def test_engine_folds_trash_utg():
    s = Situation(hole=cards("7c", "2d"), board=[], position="UTG",
                  street="preflop", pot=1.5, to_call=1.0, hero_stack=100)
    d = decide(s)
    assert d.action == "fold"


def test_engine_postflop_value_bets_nuts():
    rng = random.Random(3)
    s = Situation(hole=cards("Ah", "Kh"), board=cards("Qh", "Jh", "Th"),
                  position="BTN", street="flop", pot=10, to_call=0,
                  hero_stack=100, rng=rng)
    d = decide(s)
    assert d.action == "raise"
    assert d.equity > 0.8


def test_engine_folds_to_bad_odds():
    rng = random.Random(5)
    s = Situation(hole=cards("7c", "2d"), board=cards("Ah", "Kd", "Qs"),
                  position="BB", street="flop", pot=10, to_call=8,
                  hero_stack=100, rng=rng)
    d = decide(s)
    assert d.action == "fold"


# ---- simulator (rules integration) ------------------------------------
def test_session_conserves_chips():
    lineup = [("A", "engine"), ("B", "tag"), ("C", "station"), ("D", "rock")]
    res = run_session(lineup, hands=200, seed=99, rebuy=False)
    total_start = sum(r.start_stack for r in res.reports)
    total_end = sum(r.end_stack for r in res.reports)
    assert abs(total_start - total_end) < 1e-6  # no chips created/destroyed


def test_session_runs_and_reports():
    lineup = [("Hero", "engine"), ("Villain", "station")]
    res = run_session(lineup, hands=300, seed=7)
    assert res.hands > 0
    rows = res.summary_rows()
    assert len(rows) == 2
    assert all("bb100" in r for r in rows)


def test_engine_beats_station_long_run():
    lineup = [("Engine", "engine"), ("Station", "station")]
    res = run_session(lineup, hands=800, seed=123, rebuy=True)
    by_name = {r.name: r for r in res.reports}
    assert by_name["Engine"].net > by_name["Station"].net


def test_engine_no_longer_punts_vs_tag():
    """Regression for the all-in raise-war leak: engine must not get crushed."""
    lineup = [("Engine", "engine"), ("Tag", "tag")]
    res = run_session(lineup, hands=600, big_blind=1.0, start_stack=200, seed=1, rebuy=True)
    by_name = {r.name: r for r in res.reports}
    assert by_name["Engine"].net > -50 * 200  # not a catastrophic loss


# ---- P2 range model ----------------------------------------------------
def test_range_expansion_counts():
    from poker.range_model import expand_range
    assert len(expand_range(["AA"])) == 6
    assert len(expand_range(["AKs"])) == 4
    assert len(expand_range(["AKo"])) == 12
    assert len(expand_range(["TT+"])) == 30   # TT,JJ,QQ,KK,AA × 6


def test_equity_vs_range_orders_hands():
    from poker.range_model import expand_range, equity_vs_range, STRONG_BETTING_RANGE
    rng = random.Random(0)
    vr = expand_range(STRONG_BETTING_RANGE)
    aa = equity_vs_range(cards("As", "Ad"), vr, iterations=800, rng=rng)
    trash = equity_vs_range(cards("7c", "2d"), vr, iterations=800, rng=rng)
    assert aa > trash
    assert aa > 0.7


def test_equity_vs_ranges_multiway():
    from poker.range_model import expand_range, equity_vs_ranges
    rng = random.Random(0)
    tight = expand_range(["QQ+", "AKs", "AKo"])
    aa = equity_vs_ranges(cards("As", "Ad"), [tight, tight], iterations=1000, rng=rng)
    trash = equity_vs_ranges(cards("7c", "2d"), [tight, tight], iterations=1000, rng=rng)
    assert aa > trash          # AA still ahead of two strong ranges
    assert 0.5 < aa < 0.85     # but reduced multiway


# ---- P3 profiling ------------------------------------------------------
def test_profiling_classifies_station():
    from poker.profiling import ProfileBook
    book = ProfileBook()
    lineup = [("Eng", "engine"), ("Sta", "station")]
    res = run_session(lineup, hands=300, seed=5)
    for h in res.history:
        book.observe(h)
    sta = book.get("Sta")
    assert sta.vpip > 0.5          # station plays loose
    assert sta.fold_freq < 0.2     # rarely folds


# ---- P1 tournament + ICM ----------------------------------------------
def test_icm_conserves_prize_pool():
    from poker.tournament import icm_equity
    eq = icm_equity({"A": 5000, "B": 3000, "C": 2000}, [50, 30, 20])
    assert abs(sum(eq.values()) - 100) < 1e-6
    assert eq["A"] > eq["B"] > eq["C"]   # bigger stack = more equity


def test_tournament_has_single_winner():
    from poker.tournament import run_tournament
    res = run_tournament([("a", "engine"), ("b", "tag"), ("c", "station"), ("d", "rock")],
                         start_stack=100, hands_per_level=15, prize_pool=100, seed=4)
    assert len(res.finish_order) == 4
    assert res.prizes[res.finish_order[0]] == 50.0
    assert sum(res.prizes.values()) == 100.0


# ---- P5 leak report ----------------------------------------------------
def test_leak_report_per_position():
    from poker.history import leak_report
    res = run_session([("Hero", "engine"), ("V", "tag")], hands=300, seed=2)
    rows = leak_report(res.history, "Hero", 1.0)
    assert rows
    assert all("net_bb" in r and "position" in r for r in rows)


# ---- N2 vectorised evaluator / equity ---------------------------------
def test_vectorised_evaluator_order_isomorphic():
    """score7_batch must rank identically to the scalar evaluate7."""
    import numpy as np
    from poker.fast_equity import score7_batch, _CARD_INDEX
    rng = random.Random(0)
    deck = full_deck()
    hands, idxs = [], []
    for _ in range(4000):
        rng.shuffle(deck)
        h = deck[:7]
        hands.append(h)
        idxs.append([_CARD_INDEX[c] for c in h])
    scores = score7_batch(np.array(idxs))
    tuples = [evaluate7(h) for h in hands]
    order = sorted(range(len(hands)), key=lambda i: tuples[i])
    prev = -1
    for i in order:
        assert int(scores[i]) >= prev
        prev = int(scores[i])


def test_fast_equity_matches_scalar():
    from poker.fast_equity import equity_fast
    rng = random.Random(0)
    for hole in (["As", "Ad"], ["Kh", "Qh"], ["7c", "2d"]):
        scalar = equity(cards(*hole), opponents=2, iterations=4000, rng=rng)
        fast = equity_fast(cards(*hole), opponents=2, iterations=40000, seed=1)
        assert abs(scalar - fast) < 0.03   # same within Monte Carlo noise


# ---- N4 persistence ----------------------------------------------------
def test_store_roundtrip(tmp_path):
    from poker.store import StatsStore
    db = str(tmp_path / "s.db")
    st = StatsStore(db)
    res = run_session([("Eng", "engine"), ("Sta", "station")], hands=120, seed=1)
    sid = st.save_session(res)
    assert sid == 1
    assert len(st.all_profiles()) == 2
    assert st.get_profile("Sta")["hands"] > 0
    assert len(st.session_history("Eng")) == 1
    st.close()


# ---- N6 arena ----------------------------------------------------------
def test_arena_ranks_engine_high():
    from poker.arena import round_robin
    res = round_robin(["engine", "station", "rock"], hands=1500, seed=0, fast=True)
    assert len(res.ranking) == 3
    types = [r["type"] for r in res.ranking]
    # engine should not finish last vs a station/rock field
    assert types[-1] != "engine"


# ---- N3 range equity ---------------------------------------------------
def test_range_equity_toggle_folds_dominated():
    from poker import engine as eng
    from poker.engine import Situation, decide
    prev = eng.USE_RANGE_EQUITY
    eng.USE_RANGE_EQUITY = True
    try:
        s = Situation(hole=cards("Kd", "Qd"), board=cards("Ah", "7s", "2c"),
                      position="BTN", street="flop", pot=10, to_call=8,
                      hero_stack=100, rng=random.Random(1))
        d = decide(s)
        assert d.action == "fold"   # KQ high crushed by a betting range on A-high
    finally:
        eng.USE_RANGE_EQUITY = prev


def test_web_coach_payload_includes_didactic_insights():
    from web_api import WebGame
    from poker.table import ActionView

    game = WebGame(villains=["tag"], seed=7)
    game._pending_view = ActionView(
        hole=cards("Ah", "Kh"),
        board=cards("Qh", "7c", "2h"),
        position="BTN",
        street="flop",
        pot=6.0,
        to_call=2.0,
        min_raise=2.0,
        hero_stack=98.0,
        big_blind=1.0,
        num_active_opponents=1,
        facing_raise=True,
        street_invested=0.0,
        rng=random.Random(1),
    )
    coach = game._coach()
    assert coach["insights"]["made_hand"] == "High Card"
    assert "flush draw" in coach["insights"]["draws"]
    assert coach["insights"]["outs"]["count"] >= 9
    assert coach["insights"]["equity_breakdown"]["win_pct"] >= 0.0


def test_manual_overlay_advice_uses_engine_without_pyqt():
    from coach_overlay_app import OverlaySpot, compute_overlay_advice

    payload = compute_overlay_advice(
        OverlaySpot(hero_cards="Ah Kh", board_cards="Qh 7c 2h",
                    street="flop", pot_bb=6, to_call_bb=2, stack_bb=98)
    )
    assert payload["label"]
    assert payload["made_hand"] == "High Card"
    assert "flush draw" in payload["draws"]
    assert payload["outs"] >= 9


def test_overlay_capture_metadata_is_json_ready(tmp_path):
    from coach_overlay_app import (
        CaptureRegion,
        OverlaySpot,
        capture_metadata,
        create_capture_session,
    )

    session = create_capture_session(tmp_path)
    assert (session / "images").is_dir()
    record = capture_metadata(
        "shot.png",
        CaptureRegion(x=10, y=20, width=300, height=200, source="manual"),
        OverlaySpot(hero_cards="As Kh"),
        {"label": "RAISE to 3"},
        "manual",
        "Lettura stimata: RAISE to 3",
        {"hero_cards": ["As", "Kh"]},
    )
    assert record["filename"] == "shot.png"
    assert record["readout"] == "Lettura stimata: RAISE to 3"
    assert record["region"]["width"] == 300
    assert record["spot"]["hero_cards"] == "As Kh"
    assert record["vision"]["hero_cards"] == ["As", "Kh"]


def test_overlay_capture_session_falls_back_when_root_unusable(tmp_path):
    from coach_overlay_app import create_capture_session

    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    fallback = tmp_path / "fallback"
    session = create_capture_session(blocked, fallback_root=fallback)
    assert session.parent == fallback
    assert (session / "images").is_dir()


def test_overlay_region_from_points_normalizes_drag():
    from coach_overlay_app import region_from_points

    region = region_from_points(900, 700, 120, 80, source="selected")
    assert region.x == 120
    assert region.y == 80
    assert region.width == 780
    assert region.height == 620
    assert region.source == "selected"


def test_overlay_region_config_roundtrip(tmp_path):
    from coach_overlay_app import (
        CaptureRegion,
        capture_region_summary,
        load_saved_region,
        load_saved_vision_zones,
        load_overlay_config,
        relative_region,
        region_from_config,
        region_to_config,
        save_overlay_config,
        save_vision_zone,
    )

    path = tmp_path / "overlay.json"
    original = CaptureRegion(100, 124, 1111, 739, "area selezionata")
    save_overlay_config({"last_region": region_to_config(original)}, path)
    loaded = region_from_config(load_overlay_config(path)["last_region"])
    assert loaded == original
    assert load_saved_region(path) == original
    assert capture_region_summary(original) == "1111x739 @ 100,124 (area selezionata)"
    rel = relative_region(
        CaptureRegion(180, 240, 120, 90, "screen"),
        CaptureRegion(100, 200, 500, 400, "table"),
        "hero_zone",
    )
    assert rel == CaptureRegion(80, 40, 120, 90, "hero_zone")
    save_vision_zone("hero", rel, path)
    assert load_saved_vision_zones(path)["hero"] == rel


def test_window_capture_accepts_pokerstars_table_without_poker_title():
    from window_capture import WindowCapture

    capture = object.__new__(WindowCapture)
    capture.keywords = WindowCapture.POKER_KEYWORDS
    capture.preferred_owners = ["pokerstars"]
    assert capture._is_candidate_window({
        "owner": "PokerStars",
        "title": "Klumpkea II - No Limit Hold'em 100/200 Soldi virtuali",
        "bounds": {"x": 90, "y": 70, "width": 980, "height": 710},
    })


def test_window_capture_can_skip_initial_detection():
    from window_capture import WindowCapture

    capture = WindowCapture(auto_detect=False)
    assert capture.current_bounds is None


def test_overlay_estimated_readout_keeps_key_state_visible():
    from coach_overlay_app import OverlaySpot, format_estimated_readout

    text = format_estimated_readout(
        OverlaySpot(hero_cards="Ah Kh", board_cards="Qh 7c 2h",
                    street="flop", position="BTN", pot_bb=6, to_call_bb=2, opponents=1),
        {"label": "CALL 2", "equity": 0.62, "confidence": 0.8,
         "draws": ["flush draw"], "outs": 9},
        "finestra: PokerStars",
    )
    assert "CALL 2" in text
    assert "eq 62%" in text
    assert "conf 80%" in text
    assert "Hero Ah Kh" in text
    assert "Board Qh 7c 2h" in text
    assert "fonte finestra: PokerStars" in text
    assert "flush draw" in text
    assert "outs 9" in text


def test_overlay_compact_hud_keeps_advice_visible():
    from coach_overlay_app import OverlaySpot, format_compact_hud

    text = format_compact_hud(
        OverlaySpot(hero_cards="9d 5s", board_cards="", street="preflop", position="BTN"),
        {"label": "RAISE to 2", "equity": 0.68, "confidence": 0.8, "outs": 0},
        "visione area conf 0.77",
    )
    assert "RAISE to 2" in text
    assert "eq 68%" in text
    assert "Hero 9d 5s" in text
    assert "outs 0" in text


def test_overlay_vision_classifies_cards_by_table_geometry():
    from overlay_vision import (
        classify_card_detections,
        normalize_card_name,
        vision_is_actionable,
        vision_summary,
    )

    state = classify_card_detections(
        [
            {"name": "9d", "conf": 0.91, "box": [420, 520, 460, 590]},
            {"name": "5s", "conf": 0.88, "box": [465, 520, 505, 590]},
            {"name": "tc", "conf": 0.93, "box": [360, 260, 400, 330]},
            {"name": "Jh", "conf": 0.90, "box": [410, 260, 450, 330]},
            {"name": "8h", "conf": 0.89, "box": [460, 260, 500, 330]},
            {"name": "player_bar", "conf": 0.99, "box": [10, 10, 80, 40]},
        ],
        width=900,
        height=650,
    )
    assert normalize_card_name("tc") == "Tc"
    assert state["hero_cards"] == ["9d", "5s"]
    assert state["board_cards"] == ["Tc", "Jh", "8h"]
    assert state["street"] == "flop"
    assert vision_is_actionable(state)
    assert "OK: Hero 9d 5s" in vision_summary(state)


def test_overlay_vision_uses_calibrated_zones():
    from overlay_vision import classify_card_detections

    state = classify_card_detections(
        [
            {"name": "As", "conf": 0.91, "box": [80, 80, 120, 150]},
            {"name": "Kh", "conf": 0.90, "box": [130, 80, 170, 150]},
            {"name": "Qh", "conf": 0.92, "box": [250, 180, 290, 250]},
            {"name": "7c", "conf": 0.91, "box": [300, 180, 340, 250]},
            {"name": "2h", "conf": 0.89, "box": [350, 180, 390, 250]},
        ],
        width=700,
        height=500,
        zones={
            "hero": {"x": 70, "y": 70, "width": 120, "height": 100},
            "board": {"x": 230, "y": 160, "width": 190, "height": 120},
        },
    )
    assert state["hero_cards"] == ["As", "Kh"]
    assert state["board_cards"] == ["Qh", "7c", "2h"]
    assert state["zones"]["hero"]["width"] == 120


def test_overlay_vision_summary_marks_partial_reads():
    from overlay_vision import (
        classify_card_detections,
        debug_image_path,
        vision_is_actionable,
        vision_summary,
    )

    state = classify_card_detections(
        [{"name": "9d", "conf": 0.91, "box": [420, 520, 460, 590]}],
        width=900,
        height=650,
    )
    assert not vision_is_actionable(state)
    assert "DA VERIFICARE" in vision_summary(state)
    assert debug_image_path({"annotated_image": "annotated.png", "image": "raw.png"}) == "annotated.png"
    assert debug_image_path({"failure_image": "failure.png", "image": "raw.png"}) == "failure.png"
