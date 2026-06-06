"""
Tournament report generator.

Builds a compact tournament + opponent analytics report from runtime logs.
"""

import ast
import csv
import json
import os
import re
import time
from collections import Counter
from datetime import datetime


class TournamentReporter:
    """Generate JSON/Markdown reports from session logs and player stats."""

    def __init__(
        self,
        session_log_path="session_log.csv",
        report_json_path="tournament_report_latest.json",
        report_md_path="tournament_report_latest.md",
        name_validator=None,
    ):
        self.session_log_path = session_log_path
        self.report_json_path = report_json_path
        self.report_md_path = report_md_path
        self.name_validator = name_validator
        self.min_seconds_between_reports = 0.5
        self.min_actions_for_leaderboard = 3
        self.max_abs_result_bb = 5000.0
        self._last_report_ts = 0.0

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _safe_int(value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _read_csv_rows(path):
        if not os.path.exists(path):
            return []
        with open(path, "r", newline="") as f:
            return list(csv.DictReader(f))

    @staticmethod
    def _parse_actions(actions_raw):
        if not actions_raw:
            return []
        if isinstance(actions_raw, list):
            return [str(a).strip().upper() for a in actions_raw if str(a).strip()]
        text = str(actions_raw).strip()
        if not text:
            return []
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                return [str(a).strip().upper() for a in parsed if str(a).strip()]
        except Exception:
            pass
        return []

    @staticmethod
    def _parse_ts(value):
        if not value:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(value).strip(), fmt)
            except Exception:
                continue
        return None

    @staticmethod
    def _street_from_notes(notes):
        if not notes:
            return "Unknown"
        text = str(notes)
        match = re.search(r"Street:\s*([A-Za-z0-9+_-]+)", text)
        if match:
            return match.group(1)
        return "Unknown"

    def _is_trackable_name(self, name):
        if self.name_validator is not None:
            try:
                return bool(self.name_validator(name))
            except Exception:
                pass

        if not name:
            return False
        text = " ".join(str(name).strip().split())
        if not text:
            return False
        lower = text.lower()

        invalid_exact = {
            "unknown",
            "err",
            "?",
            "ante",
            "check",
            "fold",
            "tempo",
            "dealer",
            "button",
            "piatto",
            "metti sb",
            "metti bb",
            "all-in",
            "all in",
            "sit out",
        }
        invalid_contains = [
            "ante",
            "check",
            "fold",
            "tempo",
            "piatto",
            "dealer",
            "button",
            "metti",
            "sit out",
            "all-in",
            "all in",
            "chiama",
            "rilancia",
            "posta",
        ]
        if lower in invalid_exact:
            return False
        if any(token in lower for token in invalid_contains):
            return False
        if re.search(r"\b\d+(?:[.,]\d+)?\s*bb\b", lower):
            return False
        if re.fullmatch(r"[0-9.,\s]+", text):
            return False
        if sum(ch.isalpha() for ch in text) < 1:
            return False
        if len(text) > 24:
            return False
        return True

    @staticmethod
    def _classify_player(vpip, pfr, af, sample):
        if sample < 3:
            return "Unclear (low sample)"
        if vpip < 15 and pfr < 12:
            return "Nit"
        if vpip < 25 and pfr >= 12:
            return "TAG"
        if vpip < 40 and pfr >= 20:
            return "LAG"
        if vpip > 40 and pfr > 35:
            return "Maniac"
        if vpip > 35 and pfr < 15:
            return "Loose-Passive"
        if af >= 2.5:
            return "Aggressive"
        return "Balanced"

    @staticmethod
    def _atomic_write(path, content):
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)

    def _build_opponent_stats(self, player_db_data):
        opponents = []
        for raw_name, entry in (player_db_data or {}).items():
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or raw_name).strip()
            if not self._is_trackable_name(name):
                continue

            raises = self._safe_int(entry.get("total_raises"), 0)
            calls = self._safe_int(entry.get("total_calls"), 0)
            folds = self._safe_int(entry.get("total_folds"), 0)
            observed_actions = raises + calls + folds
            hands_seen = self._safe_int(entry.get("hands_seen"), 0)
            sample = max(hands_seen, observed_actions)

            if sample <= 0:
                continue

            aggression_factor = self._safe_float(entry.get("aggression_factor"), 0.0)
            vpip = self._safe_float(entry.get("vpip"), 0.0)
            pfr = self._safe_float(entry.get("pfr"), 0.0)

            if observed_actions > 0:
                if vpip <= 0.0:
                    vpip = ((raises + calls) / observed_actions) * 100.0
                if pfr <= 0.0:
                    pfr = (raises / observed_actions) * 100.0

            aggression_pct = (raises / observed_actions * 100.0) if observed_actions > 0 else 0.0
            call_pct = (calls / observed_actions * 100.0) if observed_actions > 0 else 0.0
            fold_pct = (folds / observed_actions * 100.0) if observed_actions > 0 else 0.0
            style = self._classify_player(vpip, pfr, aggression_factor, sample)

            opponents.append(
                {
                    "name": name,
                    "sample_size": sample,
                    "observed_actions": observed_actions,
                    "aggression_factor": round(aggression_factor, 2),
                    "aggression_pct": round(aggression_pct, 1),
                    "vpip_pct": round(vpip, 1),
                    "pfr_pct": round(pfr, 1),
                    "call_pct": round(call_pct, 1),
                    "fold_pct": round(fold_pct, 1),
                    "total_raises": raises,
                    "total_calls": calls,
                    "total_folds": folds,
                    "style": style,
                }
            )

        opponents.sort(key=lambda p: (p["sample_size"], p["observed_actions"]), reverse=True)
        qualified = [p for p in opponents if p["sample_size"] >= self.min_actions_for_leaderboard]

        leaders = {
            "most_aggressive": sorted(
                qualified, key=lambda p: (p["aggression_pct"], p["aggression_factor"]), reverse=True
            )[:5],
            "tightest": sorted(qualified, key=lambda p: (p["vpip_pct"], p["pfr_pct"]))[:5],
            "most_loose": sorted(
                qualified, key=lambda p: (p["vpip_pct"], p["sample_size"]), reverse=True
            )[:5],
        }

        return {
            "total_tracked_players": len(opponents),
            "qualified_players": len(qualified),
            "leaders": leaders,
            "players": opponents,
        }

    def _build_tournament_stats(self, rows):
        timestamps = [self._parse_ts(row.get("timestamp")) for row in rows]
        timestamps = [ts for ts in timestamps if ts is not None]

        raw_results = [self._safe_float(row.get("result_bb"), 0.0) for row in rows]
        outlier_results = [v for v in raw_results if abs(v) > self.max_abs_result_bb]
        results = [v for v in raw_results if abs(v) <= self.max_abs_result_bb]
        total_hands = len(rows)
        evaluated_hands = len(results)
        total_profit = sum(results)
        wins = sum(1 for v in results if v > 0.0)
        losses = sum(1 for v in results if v < 0.0)
        breakeven = sum(1 for v in results if abs(v) < 1e-9)

        avg_bb_per_hand = (total_profit / evaluated_hands) if evaluated_hands > 0 else 0.0
        bb100 = avg_bb_per_hand * 100.0
        win_rate_pct = (wins / evaluated_hands * 100.0) if evaluated_hands > 0 else 0.0

        duration_minutes = 0.0
        if len(timestamps) >= 2:
            duration_minutes = (max(timestamps) - min(timestamps)).total_seconds() / 60.0

        streets = Counter(self._street_from_notes(row.get("notes")) for row in rows)
        hero_positions = Counter((row.get("hero_position") or "?").strip() for row in rows)
        hero_cards = Counter(
            (row.get("hero_cards") or "Unknown").strip()
            for row in rows
            if (row.get("hero_cards") or "").strip() not in {"", "Unknown"}
        )
        hero_decisions = Counter(
            (row.get("hero_decision") or "Unknown").strip().upper()
            for row in rows
            if (row.get("hero_decision") or "").strip()
        )
        opponent_actions = Counter()
        for row in rows:
            opponent_actions.update(self._parse_actions(row.get("opponent_actions")))

        comparable = 0
        aligned = 0
        for row in rows:
            hero_decision = (row.get("hero_decision") or "").strip()
            gto_suggestion = (row.get("gto_suggestion") or "").strip()
            if not hero_decision or not gto_suggestion:
                continue
            if hero_decision == "Unknown" or gto_suggestion == "Unknown":
                continue
            comparable += 1
            if hero_decision.upper() == gto_suggestion.upper():
                aligned += 1

        biggest_win = max(results) if results else 0.0
        biggest_loss = min(results) if results else 0.0

        return {
            "hands_played": total_hands,
            "total_profit_bb": round(total_profit, 2),
            "avg_bb_per_hand": round(avg_bb_per_hand, 3),
            "bb_per_100": round(bb100, 2),
            "win_rate_pct": round(win_rate_pct, 2),
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "result_outliers_ignored": len(outlier_results),
            "evaluated_results_count": len(results),
            "duration_minutes": round(duration_minutes, 1),
            "started_at": min(timestamps).isoformat() if timestamps else None,
            "ended_at": max(timestamps).isoformat() if timestamps else None,
            "biggest_win_bb": round(biggest_win, 2),
            "biggest_loss_bb": round(biggest_loss, 2),
            "street_distribution": dict(streets),
            "hero_position_distribution": dict(hero_positions),
            "top_hero_hands": dict(hero_cards.most_common(10)),
            "hero_decision_distribution": dict(hero_decisions),
            "opponent_action_distribution": dict(opponent_actions),
            "gto_alignment_pct": round((aligned / comparable * 100.0), 2) if comparable > 0 else None,
            "gto_alignment_samples": comparable,
        }

    def _build_markdown(self, report):
        tournament = report.get("tournament", {})
        opponents = report.get("opponents", {})
        players = opponents.get("players", [])
        leaders = opponents.get("leaders", {})

        lines = []
        lines.append("# Tournament Report")
        lines.append("")
        lines.append(f"Generated at: {report.get('generated_at')}")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- Hands: {tournament.get('hands_played', 0)}")
        lines.append(f"- Profit: {tournament.get('total_profit_bb', 0.0)} BB")
        lines.append(f"- BB/100: {tournament.get('bb_per_100', 0.0)}")
        lines.append(f"- Win rate: {tournament.get('win_rate_pct', 0.0)}%")
        lines.append(
            f"- Biggest win/loss: {tournament.get('biggest_win_bb', 0.0)} / {tournament.get('biggest_loss_bb', 0.0)} BB"
        )
        lines.append("")

        lines.append("## Opponent Leaders")
        lines.append("")

        def leader_names(items):
            return ", ".join(p["name"] for p in items) if items else "n/a"

        lines.append(f"- Most aggressive: {leader_names(leaders.get('most_aggressive', []))}")
        lines.append(f"- Tightest: {leader_names(leaders.get('tightest', []))}")
        lines.append(f"- Most loose: {leader_names(leaders.get('most_loose', []))}")
        lines.append("")

        lines.append("## Opponent Stats")
        lines.append("")
        lines.append("| Name | Sample | AF | Agg% | VPIP% | PFR% | Raise/Call/Fold | Style |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |")
        for p in players[:30]:
            lines.append(
                f"| {p['name']} | {p['sample_size']} | {p['aggression_factor']:.2f} | "
                f"{p['aggression_pct']:.1f} | {p['vpip_pct']:.1f} | {p['pfr_pct']:.1f} | "
                f"{p['total_raises']}/{p['total_calls']}/{p['total_folds']} | {p['style']} |"
            )

        return "\n".join(lines).rstrip() + "\n"

    def generate_report(self, player_db_data, force=False, hand_data=None):
        now = time.time()
        if not force and (now - self._last_report_ts) < self.min_seconds_between_reports:
            return None

        rows = self._read_csv_rows(self.session_log_path)
        tournament_stats = self._build_tournament_stats(rows)
        opponent_stats = self._build_opponent_stats(player_db_data)

        report = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_files": {
                "session_log": self.session_log_path,
                "players_history": "in-memory",
            },
            "tournament": tournament_stats,
            "opponents": opponent_stats,
            "last_logged_hand": hand_data or (rows[-1] if rows else None),
        }

        self._atomic_write(self.report_json_path, json.dumps(report, indent=2, ensure_ascii=False))
        self._atomic_write(self.report_md_path, self._build_markdown(report))
        self._last_report_ts = now
        return report
