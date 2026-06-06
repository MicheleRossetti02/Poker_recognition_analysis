"""Self-contained virtual-chip poker engine.

Pure-stdlib core (cards, evaluator, equity, ranges, engine, table) plus
pluggable bot strategies and a session simulator. No real money, no network,
no external poker client.
"""

from .cards import Card, Deck, make_card
from .engine import Decision, Situation, decide
from .equity import equity
from .evaluator import category_name, evaluate, evaluate7

try:  # optional numpy-accelerated path (N2)
    from .fast_equity import equity_fast, score7_batch
except Exception:  # pragma: no cover - numpy not installed
    equity_fast = None
    score7_batch = None
from .ranges import normalize_hand
from .range_model import expand_range, equity_vs_range
from .profiling import ProfileBook, PlayerProfile
from .table import ActionView, Player, Table
from .simulator import run_session, SessionResult
from .tournament import run_tournament, icm_equity, TournamentResult
from .history import leak_report, format_leak_report, write_history
from .arena import round_robin, tune_engine
from .store import StatsStore

__all__ = [
    "Card", "Deck", "make_card",
    "evaluate", "evaluate7", "category_name", "equity",
    "equity_fast", "score7_batch",
    "normalize_hand", "decide", "Decision", "Situation",
    "expand_range", "equity_vs_range",
    "ProfileBook", "PlayerProfile",
    "Table", "Player", "ActionView",
    "run_session", "SessionResult",
    "run_tournament", "icm_equity", "TournamentResult",
    "leak_report", "format_leak_report", "write_history",
    "round_robin", "tune_engine", "StatsStore",
]
