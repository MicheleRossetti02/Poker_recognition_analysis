"""
Production-Ready Poker GTO Bot V3
Complete integration with advanced action detection and logging
"""

import cv2
import torch
import numpy as np
import mss
import time
import threading
import easyocr
import ssl
import json
import csv
import os
import re
from datetime import datetime
from collections import deque
from queue import Queue, Empty, Full
from ultralytics import YOLO
from gto_engine import get_action, normalize_hand
from live_coach import live_decision, format_suggestion
from hud_overlay import GTOOverlay
from window_capture import WindowCapture
from websocket_server import GameStateWebSocket, create_game_state_message
from tournament_reporter import TournamentReporter

# Fix SSL
ssl._create_default_https_context = ssl._create_unverified_context

# Config
MODEL_PATH = "POKER_GTO_BOT_V3/weights/best.pt"
CONF_THRESHOLD = 0.35  # Lowered for better card detection (was 0.5)
DEVICE = 'mps' if torch.backends.mps.is_available() else 'cpu'
STREET_MAP = {0: "Preflop", 3: "Flop", 4: "Turn", 5: "River"}

# Database files
PLAYERS_DB_PATH = "players_history.json"
SESSION_LOG_PATH = "session_log.csv"
TOURNAMENT_REPORT_JSON_PATH = "tournament_report_latest.json"
TOURNAMENT_REPORT_MD_PATH = "tournament_report_latest.md"

class PlayerDatabase:
    """Persistent player statistics database"""
    def __init__(self, path=PLAYERS_DB_PATH):
        self.path = path
        self.data = self.load()
        self.save_interval_seconds = 2.0
        self._last_save_ts = 0.0
    
    def load(self):
        """Load player database from JSON"""
        if os.path.exists(self.path):
            with open(self.path, 'r') as f:
                return json.load(f)
        return {}
    
    def save(self, force=False):
        """Save database to disk"""
        now = time.time()
        if not force and (now - self._last_save_ts) < self.save_interval_seconds:
            return
        with open(self.path, 'w') as f:
            json.dump(self.data, f, indent=2)
        self._last_save_ts = now
    
    def get_player(self, name):
        """Get player stats or create new entry"""
        if not self.is_trackable_name(name):
            return None
        if name not in self.data:
            self.data[name] = {
                'name': name,
                'hands_seen': 0,
                'aggression_factor': 1.0,  # Default neutral
                'vpip': 0.0,  # Voluntarily Put money In Pot
                'pfr': 0.0,   # Preflop Raise
                'total_raises': 0,
                'total_calls': 0,
                'total_folds': 0,
                'vpip_actions': 0,
                'pfr_actions': 0,
                'total_actions_observed': 0,
            }
        return self.data[name]
    
    @staticmethod
    def is_trackable_name(name):
        if not name:
            return False
        text = " ".join(str(name).strip().split())
        if not text:
            return False
        lower = text.lower()

        invalid_exact = {
            "unknown", "err", "?", "ante", "check", "fold", "tempo",
            "dealer", "button", "piatto", "metti sb", "metti bb",
            "all-in", "all in", "sit out",
        }
        invalid_contains = [
            "ante", "check", "fold", "tempo", "piatto", "dealer",
            "button", "metti", "sit out", "all-in", "all in",
            "chiama", "rilancia", "posta",
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
        return len(text) <= 24

    def update_action(self, name, action, is_preflop=False):
        """Update player stats based on action"""
        player = self.get_player(name)
        if player is None:
            return

        action_upper = str(action).upper().strip()
        player.setdefault('hands_seen', 0)
        player.setdefault('total_raises', 0)
        player.setdefault('total_calls', 0)
        player.setdefault('total_folds', 0)
        player.setdefault('vpip_actions', 0)
        player.setdefault('pfr_actions', 0)
        player.setdefault('total_actions_observed', 0)

        player['hands_seen'] += 1

        is_raise_action = action_upper == 'RAISE' or 'BET' in action_upper
        is_call_action = action_upper in ['CALL', 'LIMP']
        is_fold_action = action_upper == 'FOLD'

        if is_raise_action:
            player['total_raises'] += 1
        elif is_call_action:
            player['total_calls'] += 1
        elif is_fold_action:
            player['total_folds'] += 1

        if is_raise_action or is_call_action:
            player['vpip_actions'] += 1
        if is_preflop and is_raise_action:
            player['pfr_actions'] += 1

        observed = player['total_raises'] + player['total_calls'] + player['total_folds']
        player['total_actions_observed'] = observed

        # Update aggression factor: AF = Raises / Calls
        if player['total_calls'] > 0:
            player['aggression_factor'] = player['total_raises'] / player['total_calls']
        else:
            player['aggression_factor'] = float(player['total_raises'])

        if observed > 0:
            player['vpip'] = (player['vpip_actions'] / observed) * 100.0
            player['pfr'] = (player['pfr_actions'] / observed) * 100.0
        else:
            player['vpip'] = 0.0
            player['pfr'] = 0.0
        
        self.save()

class SessionLogger:
    """CSV logger for session tracking"""
    def __init__(self, path=SESSION_LOG_PATH):
        self.path = path
        self.fieldnames = [
            'timestamp', 'hand_id', 'hero_position', 'hero_cards',
            'opponent_actions', 'hero_decision', 'gto_suggestion',
            'result_bb', 'notes'
        ]
        
        # Create file if it doesn't exist
        if not os.path.exists(self.path):
            with open(self.path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()
    
    def log_hand(self, hand_data):
        """Log a hand to CSV"""
        with open(self.path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writerow(hand_data)

class PlayerState:
    """Advanced player state with delta-stack tracking"""
    def __init__(self, pid):
        self.id = pid
        self.name = "Unknown"
        self.bb_current = 0.0
        self.bb_prev_frame = 0.0
        self.bb_street_start = 0.0  # BB at start of current street
        self.position = "?"
        self.status = "Folded"
        self.prev_status = "Folded"
        self.is_dealer = False
        self.detected_action = None
        self.action_this_street = None  # First action detected this street
        self.last_action_invested = 0.0
        
    def reset_for_street(self):
        """Reset for new street"""
        self.bb_street_start = self.bb_current
        self.bb_prev_frame = self.bb_current
        self.action_this_street = None
        self.detected_action = None
        self.last_action_invested = 0.0
    
    def reset_for_hand(self):
        """Reset for new hand"""
        self.bb_street_start = self.bb_current
        self.bb_prev_frame = self.bb_current
        self.action_this_street = None
        self.detected_action = None
        self.last_action_invested = 0.0
        self.status = "Folded"
        self.prev_status = "Folded"
    
    def detect_fold(self):
        """Fold: Active → Folded"""
        return self.prev_status == "Active" and self.status == "Folded"
    
    def detect_action_from_delta(self, high_bet, raises_count, bb_blind=1.0):
        """
        Advanced action detection from stack delta
        
        Args:
            high_bet: Current highest bet this street
            raises_count: Number of raises so far this street
            bb_blind: Big blind value
        
        Returns:
            tuple: (action_name, new_high_bet)
        """
        if self.bb_prev_frame == 0:
            return None, high_bet
        
        delta = self.bb_prev_frame - self.bb_current

        # Stack increased: usually pot collection / OCR bounce, not a betting action.
        if delta <= -0.15:
            return None, high_bet
        
        # ALL-IN: Stack went to 0
        if self.bb_current <= 0.01 and delta > 0.5:
            return 'ALL-IN', max(high_bet, delta)
        
        # No change or very small
        if abs(delta) < 0.05:
            # True no-change can only be CHECK in unopened pots.
            if high_bet <= bb_blind * 1.5:
                return 'CHECK' if raises_count == 0 else None, high_bet
            return None, high_bet
        
        # Bet detected
        total_invested_street = max(0.0, self.bb_street_start - self.bb_current)
        call_tolerance = max(0.35, bb_blind * 0.45)
        
        # CALL: Matches current high bet
        if high_bet > 0 and abs(total_invested_street - high_bet) <= call_tolerance:
            return 'CALL', high_bet
        
        # RAISE family: Investment exceeds high bet
        if total_invested_street > high_bet + call_tolerance:
            new_high = total_invested_street
            
            if raises_count == 0:
                return 'RAISE', new_high
            elif raises_count == 1:
                return '3BET', new_high
            elif raises_count == 2:
                return '4BET', new_high
            else:
                return f'{raises_count+2}BET', new_high
        
        return None, high_bet


class LatencyProfiler:
    """Sliding-window latency profiler with p95 reporting."""

    def __init__(self, window_size=600, report_every=80):
        self.window_size = window_size
        self.report_every = report_every
        self.sample_count = 0
        self.e2e_ms = deque(maxlen=window_size)
        self.capture_ms = deque(maxlen=window_size)
        self.infer_ms = deque(maxlen=window_size)
        self.state_ms = deque(maxlen=window_size)
        self.emit_ms = deque(maxlen=window_size)

    @staticmethod
    def _percentile(values, percentile):
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = max(0, min(len(ordered) - 1, int(round((percentile / 100.0) * (len(ordered) - 1)))))
        return ordered[idx]

    @staticmethod
    def _mean(values):
        return sum(values) / len(values) if values else 0.0

    def add(self, capture_ms, infer_ms, state_ms, emit_ms, e2e_ms):
        self.sample_count += 1
        self.capture_ms.append(capture_ms)
        self.infer_ms.append(infer_ms)
        self.state_ms.append(state_ms)
        self.emit_ms.append(emit_ms)
        self.e2e_ms.append(e2e_ms)

    def should_report(self):
        return len(self.e2e_ms) >= 20 and (self.sample_count % self.report_every == 0)

    def summary(self):
        return {
            "samples": len(self.e2e_ms),
            "e2e_p50_ms": self._percentile(self.e2e_ms, 50),
            "e2e_p95_ms": self._percentile(self.e2e_ms, 95),
            "e2e_p99_ms": self._percentile(self.e2e_ms, 99),
            "e2e_mean_ms": self._mean(self.e2e_ms),
            "capture_mean_ms": self._mean(self.capture_ms),
            "infer_mean_ms": self._mean(self.infer_ms),
            "state_mean_ms": self._mean(self.state_ms),
            "emit_mean_ms": self._mean(self.emit_ms),
        }

class PokerVisionPro:
    """Production-ready poker vision system"""
    def __init__(self):
        print("="*70)
        print("🚀 POKER GTO BOT V3 - PRODUCTION SYSTEM")
        print("="*70)
        print(f"\n📍 Device: {DEVICE}")
        print(f"📍 Model: {MODEL_PATH}")

        # Optional runtime flags for constrained environments
        self.enable_ws = os.getenv("POKER_DISABLE_WS", "0") != "1"
        self.enable_hud = os.getenv("POKER_DISABLE_HUD", "0") != "1"
        self.prefer_window_id_capture = os.getenv("POKER_CAPTURE_WINDOW_ID", "1") != "0"
        self.strict_window_id_capture = os.getenv("POKER_STRICT_WINDOW_ID_CAPTURE", "1") != "0"
        
        # Core systems
        self.model = YOLO(MODEL_PATH)
        self.model.to(DEVICE)
        self.inference_kwargs = {"conf": CONF_THRESHOLD, "verbose": False}
        self.reader = easyocr.Reader(['en'], gpu=(DEVICE=='mps'))
        self.sct = mss.mss()
        
        # Window capture (ROI-based)
        print("🔍 Searching for poker window...")
        self.window_capture = WindowCapture(
            refresh_interval=1.0,
            allow_fullscreen_fallback=False,
            preferred_owners=["PokerStars"]
        )
        if self.prefer_window_id_capture:
            if self.window_capture.is_window_id_capture_available():
                print("📷 Capture backend: window-id (Quartz direct)")
                if self.strict_window_id_capture:
                    print("🛡️  Strict window-id mode: ON (no ROI fallback on window-id miss)")
            else:
                print("⚠️  Window-id capture unavailable, fallback to ROI capture.")
        else:
            print("ℹ️  Window-id capture disabled by env (POKER_CAPTURE_WINDOW_ID=0).")
        
        # Databases
        self.player_db = PlayerDatabase()
        self.session_logger = SessionLogger()
        self.tournament_reporter = TournamentReporter(
            session_log_path=self.session_logger.path,
            report_json_path=TOURNAMENT_REPORT_JSON_PATH,
            report_md_path=TOURNAMENT_REPORT_MD_PATH,
            name_validator=PlayerDatabase.is_trackable_name,
        )
        print(f"✅ Player DB loaded: {len(self.player_db.data)} players")
        try:
            self.tournament_reporter.generate_report(self.player_db.data, force=True)
            print(f"✅ Tournament report ready: {TOURNAMENT_REPORT_JSON_PATH}")
        except Exception as e:
            print(f"⚠️  Initial report unavailable: {e}")
        
        # WebSocket server for real-time dashboard
        self.ws_server = None
        if self.enable_ws:
            print("📡 Starting WebSocket server for dashboard...")
            self.ws_server = GameStateWebSocket(host='0.0.0.0', port=8765)
            ws_thread = self.ws_server.run_in_thread()
        else:
            ws_thread = None
        self.last_gto_suggestion = "Waiting..."  # Store last suggestion for WebSocket
        if ws_thread and self.ws_server is not None:
            print("✅ WebSocket server ready on ws://localhost:8765")
        elif not self.enable_ws:
            print("ℹ️  WebSocket disabled by env (POKER_DISABLE_WS=1).")
        else:
            print("⚠️  WebSocket unavailable in this environment. Continuing without dashboard broadcast.")
        
        # Game state
        self.players = {}
        self.hero_hand = None
        self.hero_cards = []
        self.hero_position = None
        self.hero_box = None
        self.hero_pid = None
        self.hero_pid_missing_frames = 0
        self.hero_pid_hold_frames = 80
        self.hero_name_hint = (os.getenv("POKER_HERO_NAME", "MicheleR02") or "").strip()
        self.hero_name_aliases = self._build_hero_aliases(self.hero_name_hint)
        self.hero_hold_frames = 18
        self.hero_missing_frames = 0
        self.last_confirmed_hero_hand = None
        self.last_confirmed_hero_cards = []
        self.last_confirmed_hero_box = None
        self.hero_stack_hand_start = 0.0  # Track hero stack at hand start
        self.hero_decision = None  # Track hero's decision
        self.gto_suggestion = None  # Track GTO suggestion
        
        # Hand tracking
        self.hand_id = 0
        self.current_hand_actions = []
        self.hand_start_time = None
        
        # Street tracking
        self.game_state = {
            "street": "Preflop",
            "board_count": 0,
        }
        self.prev_board_count = 0
        
        # Action tracking per street
        self.high_bet_current_street = 1.0  # Starts at BB
        self.raises_count = 0

        # Runtime tuning / throttling
        def _env_int(name, default, min_value=1):
            try:
                return max(min_value, int(os.getenv(name, str(default))))
            except Exception:
                return default

        def _env_float(name, default, min_value=0.0):
            try:
                return max(min_value, float(os.getenv(name, str(default))))
            except Exception:
                return default

        self.frame_count = 0
        self.name_ocr_interval_frames_active = _env_int("POKER_NAME_OCR_ACTIVE", 10)
        self.name_ocr_interval_frames_idle = _env_int("POKER_NAME_OCR_IDLE", 18)
        self.current_ocr_interval = self.name_ocr_interval_frames_idle
        self.bb_ocr_interval_frames_active = _env_int("POKER_BB_OCR_ACTIVE", 2)
        self.bb_ocr_interval_frames_idle = _env_int("POKER_BB_OCR_IDLE", 6)
        self.current_bb_ocr_interval = self.bb_ocr_interval_frames_idle
        self.ocr_min_crop_side = 20
        self.max_detectable_bb = 1500.0
        self.max_bb_jump_ratio = 8.0
        self.max_bb_jump_abs = 250.0
        self.max_name_ocr_players_per_frame = _env_int("POKER_NAME_OCR_BUDGET", 1)
        self.max_bb_ocr_players_per_frame = _env_int("POKER_BB_OCR_BUDGET", 4)
        self.max_bb_ocr_players_per_frame_burst = _env_int("POKER_BB_OCR_BURST_BUDGET", 7)
        self.name_bootstrap_frames = _env_int("POKER_NAME_BOOTSTRAP_FRAMES", 90)
        self.name_bootstrap_budget = _env_int("POKER_NAME_BOOTSTRAP_BUDGET", 4)
        self.hand_name_bootstrap_frames_left = self.name_bootstrap_frames
        self.postflop_min_ocr_interval = 16
        self.name_ocr_round_robin_cursor = 0
        self.bb_ocr_round_robin_cursor = 0
        self.action_rearm_invest_delta = 0.35
        self.bb_ocr_interval_frames_burst = _env_int("POKER_BB_OCR_BURST_INTERVAL", 1)
        self.bb_ocr_burst_duration_frames = _env_int("POKER_BB_OCR_BURST_FRAMES", 14)
        self.bb_ocr_burst_frames = 0
        self.bb_suspicious_drop_abs = _env_float("POKER_BB_SUSP_DROP_ABS", 15.0)
        self.bb_suspicious_drop_ratio = _env_float("POKER_BB_SUSP_DROP_RATIO", 0.5)
        self.bb_suspicious_confirm_hits = _env_int("POKER_BB_SUSP_CONFIRM_HITS", 2)
        self.bb_suspicious_tolerance = _env_float("POKER_BB_SUSP_TOL", 1.8)
        self.name_stale_frames = 120
        self.invalid_name_reset_hits = 2
        self.name_confirm_hits = 2
        self.name_replace_confirm_hits = 3
        self.name_refresh_multiplier = 4
        self.ocr_name_blocklist_exact = {
            "ante", "check", "fold", "call", "raise", "all-in", "all in",
            "metti sb", "metti bb", "small blind", "big blind",
            "sit out", "in sit out", "piatto", "dealer", "button", "tempo",
        }
        self.ocr_name_blocklist_contains = [
            "ante", "check", "fold", "vinto", "piatto", "metti", "tempo",
            "all-in", "sit out", "small blind", "big blind", "chiama",
        ]
        self.player_ocr_cache = {}
        self.track_match_max_distance = _env_float("POKER_TRACK_MATCH_DIST", 170.0)
        self.track_ttl_frames = _env_int("POKER_TRACK_TTL_FRAMES", 220)
        self._track_centers = {}
        self._track_last_seen = {}
        self._next_track_id = 1
        self.folded_player_ids_hand = set()
        self.fold_candidate_counts = {}
        self.fold_confirm_frames = 2
        self.debug_cards = False
        self.verbose_runtime = False
        self.loop_sleep_active = 0.12
        self.loop_sleep_idle = 0.25
        self.loop_sleep_seconds = self.loop_sleep_idle
        self.main_loop_sleep_active = 0.006
        self.main_loop_sleep_idle = 0.02
        self.main_loop_sleep = self.main_loop_sleep_idle
        self.capture_thread_sleep_active = 0.01
        self.capture_thread_sleep_idle = 0.02
        self.capture_thread_sleep = self.capture_thread_sleep_idle
        self.console_log_interval = 24
        self._emit_counter = 0
        self.current_roi_bounds = None
        self.wait_log_interval = 2.0
        self._last_wait_log_ts = 0.0
        self._last_wait_message = ""
        self.ws_broadcast_min_interval = 0.08
        self._last_ws_broadcast_ts = 0.0
        print(
            "⚙️ OCR policy: "
            f"name={self.name_ocr_interval_frames_active}f(active)/{self.name_ocr_interval_frames_idle}f(idle), "
            f"bb={self.bb_ocr_interval_frames_active}f(active)/{self.bb_ocr_interval_frames_idle}f(idle), "
            f"budget(name/bb)={self.max_name_ocr_players_per_frame}/{self.max_bb_ocr_players_per_frame}, "
            f"bb-burst={self.bb_ocr_interval_frames_burst}f/{self.max_bb_ocr_players_per_frame_burst}players"
        )

        # Temporal filters (multi-frame anti-flicker)
        self.board_filter_window = 6
        self.board_up_confirm_hits = 2
        self.board_down_confirm_hits = 3
        self.board_swap_confirm_hits = 3
        self.board_cards_history = deque(maxlen=self.board_filter_window)
        self.board_cards_history.append(tuple())
        self.stable_board_cards = []

        self.hero_filter_window = 5
        self.hero_up_confirm_hits = 2
        self.hero_down_confirm_hits = 3
        self.hero_swap_confirm_hits = 3
        self.hero_cards_history = deque(maxlen=self.hero_filter_window)
        self.hero_cards_history.append(tuple())
        self.stable_hero_cards = []
        self.stable_hero_box = None

        # Async pipeline
        self.use_async_pipeline = True
        self.capture_queue = Queue(maxsize=2)
        self.infer_queue = Queue(maxsize=2)
        self.render_queue = Queue(maxsize=3)
        self.pipeline_stop = threading.Event()
        self.pipeline_threads = []
        self.reposition_interval = 0.20
        self._last_reposition_ts = 0.0

        # Latency profiler (p95 end-to-end)
        self.latency_profiler = LatencyProfiler(window_size=600, report_every=40)

        # HUD (PyQt6) - optional fallback when GUI is unavailable
        self.hud = None
        self.qt_available = False
        self._QApplication = None
        if not self.enable_hud:
            print("ℹ️  HUD disabled by env (POKER_DISABLE_HUD=1). Running without overlay.\n")
        else:
            try:
                print("🎨 Initializing HUD (PyQt6)...")
                from PyQt6.QtWidgets import QApplication
                self._QApplication = QApplication
                self.qt_available = True
                if QApplication.instance():
                    QApplication.processEvents()

                # Get initial window bounds for HUD positioning
                hud_bounds = self.window_capture.get_current_bounds()
                self.hud = GTOOverlay(window_bounds=hud_bounds)
                self.hud.start()
                print("✅ HUD Active!\n")
            except Exception as e:
                self.hud = None
                self.qt_available = False
                self._QApplication = None
                print(f"⚠️  HUD unavailable ({e}). Continuing in headless mode.\n")
    
    def detect_new_hand(self, board_count):
        """New hand: board goes from >0 back to 0"""
        return self.prev_board_count > 0 and board_count == 0
    
    def detect_street_change(self, new_street):
        """Street changed"""
        return new_street != self.game_state['street']
    
    def reset_hand(self):
        """Reset all state for new hand"""
        # Log previous hand if it exists
        if self.hand_id > 0:
            self.log_hand_result()
        
        self.hand_id += 1
        self.current_hand_actions = []
        self.hand_start_time = datetime.now()
        self.hero_hand = None
        self.hero_cards = []
        self.hero_box = None
        self.hero_position = None
        self.hero_missing_frames = 0
        self.last_confirmed_hero_hand = None
        self.last_confirmed_hero_cards = []
        self.last_confirmed_hero_box = None
        self.stable_hero_cards = []
        self.stable_hero_box = None
        self.hero_decision = None
        self.gto_suggestion = None
        self.high_bet_current_street = 1.0
        self.raises_count = 0
        self.hand_name_bootstrap_frames_left = self.name_bootstrap_frames
        self.folded_player_ids_hand = set()
        self.fold_candidate_counts = {}
        self.name_ocr_round_robin_cursor = 0
        self.bb_ocr_round_robin_cursor = 0
        self.board_cards_history.clear()
        self.board_cards_history.append(tuple())
        self.hero_cards_history.clear()
        self.hero_cards_history.append(tuple())
        self.stable_board_cards = []
        self.game_state['board_cards'] = []
        
        # Save hero stack at start of hand
        self.hero_stack_hand_start = 0.0
        hero_ref = self.players.get(self.hero_pid) if self.hero_pid else None
        if hero_ref is not None:
            self.hero_stack_hand_start = hero_ref.bb_current
        for player in self.players.values():
            if hero_ref is None and player.position == self.hero_position:
                self.hero_stack_hand_start = player.bb_current
            player.reset_for_hand()
        
        print(f"\n{'🎲'*25}")
        print(f"  NEW HAND #{self.hand_id}")
        print(f"{'🎲'*25}\n")
    
    def reset_street(self):
        """Reset state for new street"""
        # Preflop starts from BB baseline; postflop starts from 0.
        if self.game_state.get('street') == "Preflop":
            self.high_bet_current_street = 1.0
        else:
            self.high_bet_current_street = 0.0
        self.raises_count = 0
        
        for player in self.players.values():
            player.reset_for_street()
        
        print(f"\n{'─'*50}")
        print(f"  STREET RESET: {self.game_state['street']}")
        print(f"  high_bet={self.high_bet_current_street:.1f} | raises=0")
        print(f"{'─'*50}\n")
    
    def capture(self):
        """Capture screen preferring window-id direct capture, with ROI fallback."""
        # Get window bounds
        roi = self.window_capture.get_roi_for_mss()

        # Preferred path: direct window content capture by locked window-id.
        if self.prefer_window_id_capture:
            window_bgra = self.window_capture.capture_window_bgra()
            if window_bgra is not None:
                self.current_roi_bounds = roi
                return cv2.cvtColor(window_bgra, cv2.COLOR_BGRA2BGR)
            if self.strict_window_id_capture and self.window_capture.is_window_id_capture_available():
                # Safer than ROI fallback when another window may occlude the table.
                self.current_roi_bounds = None
                return None
        
        if roi:
            # Capture specific window
            sct_img = self.sct.grab(roi)
        elif self.window_capture.mode == 'fullscreen':
            # Fallback to fullscreen
            sct_img = self.sct.grab(self.sct.monitors[1])
        else:
            # Controlled fallback: no random full-screen grabs when target window is missing
            self.current_roi_bounds = None
            return None
        
        img = np.array(sct_img)
        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        # Store original bounds for HUD coordinate mapping
        self.current_roi_bounds = roi
        
        # YOLO can handle any image size - no need to resize!
        # Just return the original captured image
        return img
    
    @staticmethod
    def _split_player_info_crop(crop):
        """
        Split player-info crop into name area (top) and BB area (bottom).
        """
        if crop is None or crop.size == 0:
            return crop, crop
        h = int(crop.shape[0])
        if h < 6:
            return crop, crop
        split = max(2, min(h - 2, int(h * 0.55)))
        name_crop = crop[:split, :]
        bb_crop = crop[split - 2:, :]
        return name_crop, bb_crop

    def parse_player_name(self, crop):
        """OCR focused on player nickname."""
        try:
            res = self.reader.readtext(crop, detail=0, paragraph=False)
            name = "Unknown"
            name_candidates = []

            for text_raw in res:
                if not text_raw:
                    continue
                t = str(text_raw).strip()
                if not t:
                    continue
                t_norm = t.replace("\u00a0", " ").replace(",", ".")

                letters = sum(1 for ch in t_norm if ch.isalpha())
                digits = sum(1 for ch in t_norm if ch.isdigit())
                if (
                    letters >= 3
                    and letters >= digits
                    and len(t_norm) <= 24
                    and not self._is_noise_name(t_norm)
                ):
                    score = (letters * 2) - digits - (1 if " " in t_norm else 0)
                    name_candidates.append((score, t_norm))

            if name_candidates:
                name_candidates.sort(key=lambda x: x[0], reverse=True)
                name = name_candidates[0][1]
            return name
        except Exception:
            return "Unknown"

    def parse_player_bb(self, crop):
        """OCR focused on stack value in BB (dynamic, high frequency)."""
        try:
            try:
                res = self.reader.readtext(
                    crop,
                    detail=0,
                    paragraph=False,
                    allowlist="0123456789.,Bb",
                )
            except TypeError:
                res = self.reader.readtext(crop, detail=0, paragraph=False)

            numeric_candidates = []
            for text_raw in res:
                if not text_raw:
                    continue
                t = str(text_raw).strip()
                if not t:
                    continue

                t_norm = t.replace("\u00a0", " ").replace(",", ".")
                t_upper = t_norm.upper()
                for match in re.finditer(r"\d+(?:\.\d+)?", t_upper):
                    token = match.group(0)
                    try:
                        value = float(token)
                    except Exception:
                        continue
                    if 0.0 < value <= self.max_detectable_bb:
                        has_bb_hint = ("BB" in t_upper)
                        numeric_candidates.append((2 if has_bb_hint else 1, value))

            if numeric_candidates:
                numeric_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
                return numeric_candidates[0][1]
            return 0.0
        except Exception:
            return 0.0

    def parse_player_info(self, crop):
        """Compatibility wrapper: parse name and BB from split crop."""
        name_crop, bb_crop = self._split_player_info_crop(crop)
        return self.parse_player_name(name_crop), self.parse_player_bb(bb_crop)

    def _is_noise_name(self, value):
        if not value:
            return True
        text = " ".join(str(value).strip().lower().split())
        if not text:
            return True
        if text in self.ocr_name_blocklist_exact:
            return True
        return any(token in text for token in self.ocr_name_blocklist_contains)

    def _is_valid_player_name(self, value):
        if not value:
            return False
        text = str(value).strip()
        if text in ["Unknown", "Err", "?", "-"]:
            return False
        return not self._is_noise_name(text)

    @staticmethod
    def _normalize_name_token(value):
        if not value:
            return ""
        return re.sub(r"[^a-z0-9]", "", str(value).lower())

    def _build_hero_aliases(self, hero_name_hint):
        aliases = []
        if hero_name_hint:
            aliases.append(hero_name_hint)
        aliases.extend([
            "MicheleR02",
            "MicheleRO2",
            "micheler02",
            "michelero2",
            "michele",
            "rossetti",
        ])
        env_aliases = os.getenv("POKER_HERO_ALIASES", "")
        if env_aliases:
            aliases.extend([a.strip() for a in env_aliases.split(",") if a.strip()])

        normalized = set()
        for alias in aliases:
            token = self._normalize_name_token(alias)
            if len(token) >= 4:
                normalized.add(token)
        return sorted(normalized, key=len, reverse=True)

    def _is_hero_name_match(self, player_name):
        token = self._normalize_name_token(player_name)
        if not token:
            return False
        for alias in self.hero_name_aliases:
            if alias in token or token in alias:
                return True
        return False

    def _is_hero_player(self, player):
        if player is None:
            return False
        if self.hero_pid:
            return player.id == self.hero_pid
        return bool(self.hero_position) and player.position == self.hero_position

    def _update_name_consensus(self, cached, candidate_name):
        stable_name = cached.get("stable_name", cached.get("name", "Unknown"))
        pending_name = cached.get("pending_name")
        pending_hits = int(cached.get("pending_name_hits", 0))

        if not self._is_valid_player_name(candidate_name):
            return stable_name, pending_name, pending_hits

        candidate = str(candidate_name).strip()
        if not self._is_valid_player_name(stable_name):
            if pending_name == candidate:
                pending_hits += 1
            else:
                pending_name = candidate
                pending_hits = 1
            if pending_hits >= self.name_confirm_hits:
                stable_name = candidate
                pending_name = None
                pending_hits = 0
            return stable_name, pending_name, pending_hits

        if candidate == stable_name:
            return stable_name, None, 0

        if pending_name == candidate:
            pending_hits += 1
        else:
            pending_name = candidate
            pending_hits = 1

        if pending_hits >= self.name_replace_confirm_hits:
            stable_name = candidate
            pending_name = None
            pending_hits = 0
        return stable_name, pending_name, pending_hits

    def _is_plausible_bb_update(self, previous_bb, candidate_bb):
        """Reject OCR outliers and unrealistic one-frame stack jumps."""
        if candidate_bb <= 0.0 or candidate_bb > self.max_detectable_bb:
            return False
        if previous_bb <= 0.0:
            return True
        if candidate_bb > previous_bb:
            ratio_ok = candidate_bb <= (previous_bb * self.max_bb_jump_ratio)
            abs_ok = (candidate_bb - previous_bb) <= self.max_bb_jump_abs
            return ratio_ok or abs_ok
        return True

    def _sanitize_bb_value(self, value):
        """Normalize BB values and zero-out impossible values."""
        try:
            bb = float(value)
        except Exception:
            return 0.0
        if not np.isfinite(bb):
            return 0.0
        if bb < 0.0 or bb > self.max_detectable_bb:
            return 0.0
        return round(bb, 1)

    def _is_suspicious_bb_drop(self, previous_bb, candidate_bb):
        """Detect large one-frame drops that are likely OCR glitches."""
        if previous_bb <= 0.0 or candidate_bb <= 0.0 or candidate_bb >= previous_bb:
            return False
        drop = previous_bb - candidate_bb
        if drop < self.bb_suspicious_drop_abs:
            return False
        return (drop / max(previous_bb, 0.01)) >= self.bb_suspicious_drop_ratio

    def _apply_bb_consensus(self, player, candidate_bb, cache):
        """
        Confirm suspicious BB drops across multiple OCR hits before committing.

        Returns:
            tuple: (accepted_bb, updated_cache, committed)
        """
        next_cache = dict(cache)
        candidate = self._sanitize_bb_value(candidate_bb)
        current = self._sanitize_bb_value(player.bb_current)
        held = self._sanitize_bb_value(cache.get("bb", current))

        if candidate <= 0.0:
            return held, next_cache, False
        if not self._is_plausible_bb_update(current, candidate):
            return held, next_cache, False

        if self._is_suspicious_bb_drop(current, candidate):
            pending = self._sanitize_bb_value(next_cache.get("pending_bb", 0.0))
            pending_hits = int(next_cache.get("pending_bb_hits", 0))
            if pending > 0.0 and abs(pending - candidate) <= self.bb_suspicious_tolerance:
                pending_hits += 1
            else:
                pending = candidate
                pending_hits = 1
            next_cache["pending_bb"] = pending
            next_cache["pending_bb_hits"] = pending_hits
            if pending_hits < self.bb_suspicious_confirm_hits:
                return held, next_cache, False
        # Confirmed update (normal or multi-frame suspicious update)
        next_cache["pending_bb"] = 0.0
        next_cache["pending_bb_hits"] = 0
        return candidate, next_cache, True

    def _prune_stale_tracks(self):
        stale = [
            pid for pid, last_seen in self._track_last_seen.items()
            if (self.frame_count - int(last_seen)) > self.track_ttl_frames
        ]
        for pid in stale:
            self._track_last_seen.pop(pid, None)
            self._track_centers.pop(pid, None)
            self.player_ocr_cache.pop(pid, None)
            self.fold_candidate_counts.pop(pid, None)
            self.folded_player_ids_hand.discard(pid)
            self.players.pop(pid, None)
            if self.hero_pid == pid:
                self.hero_pid = None

    def _assign_player_ids(self, p_infos):
        """
        Assign stable player IDs by nearest-center tracking (avoids index-shift ghost names).
        """
        if not p_infos:
            self._prune_stale_tracks()
            return []

        active_track_pids = [
            pid for pid, last_seen in self._track_last_seen.items()
            if (self.frame_count - int(last_seen)) <= self.track_ttl_frames
        ]

        centers = []
        for box in p_infos:
            centers.append((
                float((box[0] + box[2]) / 2.0),
                float((box[1] + box[3]) / 2.0),
            ))

        pairings = []
        for idx, (cx, cy) in enumerate(centers):
            for pid in active_track_pids:
                prev = self._track_centers.get(pid)
                if prev is None:
                    continue
                dist = ((cx - prev[0]) ** 2 + (cy - prev[1]) ** 2) ** 0.5
                if dist <= self.track_match_max_distance:
                    pairings.append((dist, idx, pid))

        pairings.sort(key=lambda item: item[0])
        assigned_idx = {}
        used_idx = set()
        used_pids = set()
        for _, idx, pid in pairings:
            if idx in used_idx or pid in used_pids:
                continue
            assigned_idx[idx] = pid
            used_idx.add(idx)
            used_pids.add(pid)

        for idx in range(len(p_infos)):
            if idx in assigned_idx:
                continue
            pid = f"P{self._next_track_id}"
            self._next_track_id += 1
            assigned_idx[idx] = pid

        for idx, pid in assigned_idx.items():
            self._track_centers[pid] = centers[idx]
            self._track_last_seen[pid] = self.frame_count

        self._prune_stale_tracks()
        return [assigned_idx[idx] for idx in range(len(p_infos))]
    
    def log_hand_result(self):
        """Log hand result to CSV (only if hero had cards)"""
        # Only log if we detected hero cards at some point
        if not self.hero_position or self.hero_position == "?" or not self.hand_start_time or not self.hero_hand:
            return
        
        # Calculate result_bb (stack difference)
        result_bb = 0.0
        for player in self.players.values():
            if self._is_hero_player(player):
                result_bb = player.bb_current - self.hero_stack_hand_start
                break
        
        # Format opponent actions
        opponent_actions_list = [
            a['action'] for a in self.current_hand_actions
            if a['position'] != self.hero_position
        ]
        opponent_actions_str = str(opponent_actions_list)
        
        hand_data = {
            'timestamp': self.hand_start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'hand_id': self.hand_id,
            'hero_position': self.hero_position or '?',
            'hero_cards': self.hero_hand or 'Unknown',
            'opponent_actions': opponent_actions_str,
            'hero_decision': self.hero_decision or 'Unknown',
            'gto_suggestion': self.gto_suggestion or 'Unknown',
            'result_bb': f"{result_bb:.2f}",
            'notes': f"Street: {self.game_state['street']}"
        }
        
        self.session_logger.log_hand(hand_data)
        print(f"📝 Hand #{self.hand_id} logged: Result = {result_bb:+.2f}BB")
        try:
            self.tournament_reporter.generate_report(
                self.player_db.data,
                force=True,
                hand_data=hand_data,
            )
            print(f"📄 Tournament report updated: {TOURNAMENT_REPORT_JSON_PATH}")
        except Exception as e:
            print(f"⚠️  Tournament report update failed: {e}")
    
    @staticmethod
    def _put_latest(queue_obj, item):
        """Put item into queue; drop stale entries when full."""
        while True:
            try:
                queue_obj.put_nowait(item)
                return
            except Full:
                try:
                    queue_obj.get_nowait()
                except Empty:
                    return

    @staticmethod
    def _canonical_card_tuple(cards):
        """Canonical card tuple to make temporal voting order-invariant."""
        if not cards:
            return tuple()
        return tuple(sorted(cards))

    @staticmethod
    def _count_occurrences(values):
        counts = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        return counts

    def _stabilize_card_tuple(
        self,
        history,
        previous,
        up_hits,
        down_hits,
        swap_hits,
        allow_empty=True,
    ):
        """
        Stabilize card tuple with temporal majority + hysteresis.
        Increases are accepted faster than decreases to reduce flicker.
        """
        if not history:
            return list(previous)

        recent = [value for value in history if allow_empty or value]
        if not recent:
            return list(previous)

        counts = self._count_occurrences(recent)
        latest = history[-1]
        candidate, candidate_hits = max(
            counts.items(),
            key=lambda item: (item[1], 1 if item[0] == latest else 0, len(item[0])),
        )

        prev_tuple = self._canonical_card_tuple(previous)
        if candidate == prev_tuple:
            return list(previous)

        if len(candidate) > len(prev_tuple):
            threshold = up_hits
        elif len(candidate) < len(prev_tuple):
            threshold = down_hits
        else:
            threshold = swap_hits

        if candidate_hits >= threshold:
            return list(candidate)
        return list(previous)

    def _build_waiting_payload(self, message):
        return {
            "suggestion": message,
            "opponent_actions": [],
            "hero_box": None,
            "board_cards": 0,
            "active_mode": False,
            "street": self.game_state.get("street", "Preflop"),
            "hand_id": self.hand_id,
            "hero_hand": self.hero_hand,
            "hero_position": self.hero_position,
            "high_bet": self.high_bet_current_street,
            "raises_count": self.raises_count,
            "players_snapshot": [],
            "ws_message": None,
            "force_log": False,
        }

    def _process_state(self, frame, results):
        """Compute game state from a captured frame + inference result."""
        self.frame_count += 1

        # Parse detections
        dets = {n: [] for n in results.names.values()}
        for box in results.boxes:
            cls = int(box.cls[0])
            name = results.names[cls]
            bbox = box.xyxy[0].cpu().numpy()
            dets[name].append(bbox)

        # Board + hero detection (single pass + temporal filters)
        h, w = frame.shape[:2]
        center = (w / 2, h / 2)
        board_candidates = {}
        hero_candidates = {}
        all_cards_detected = []

        for box in results.boxes:
            cls = int(box.cls[0])
            name = results.names[cls]
            if len(name) != 2 and name not in ['Tc', 'Th', 'Ts', 'Td']:
                continue

            conf = float(box.conf[0])
            bbox = box.xyxy[0].cpu().numpy()
            bx = (bbox[0] + bbox[2]) / 2
            by = (bbox[1] + bbox[3]) / 2

            all_cards_detected.append({'name': name, 'conf': conf, 'y': by, 'y_pct': (by / h) * 100})

            if abs(bx - center[0]) < w * 0.3 and abs(by - center[1]) < h * 0.3 and conf >= 0.35:
                prev_conf = board_candidates.get(name, -1.0)
                if conf > prev_conf:
                    board_candidates[name] = conf

            if by > h * 0.5 and conf >= 0.3:
                prev = hero_candidates.get(name)
                if prev is None or conf > prev["conf"]:
                    hero_candidates[name] = {"name": name, "conf": conf, "bbox": bbox, "y": by}
                if self.debug_cards:
                    print(f"  🃏 HERO CARD CANDIDATE: {name} (conf={conf:.2f}, y={by:.0f}, y%={by / h * 100:.1f}%)")

        if self.debug_cards and all_cards_detected:
            print(f"\n🔍 DEBUG: Detected {len(all_cards_detected)} total cards:")
            for card in all_cards_detected:
                marker = "✅ HERO" if card['y_pct'] > 50 else "❌ BOARD/RIVAL"
                print(f"   {marker} {card['name']:4} conf={card['conf']:.2f} y={card['y']:.0f} ({card['y_pct']:.1f}%)")

        raw_board_card_names = [
            item[0]
            for item in sorted(board_candidates.items(), key=lambda item: item[1], reverse=True)[:5]
        ]
        self.board_cards_history.append(self._canonical_card_tuple(raw_board_card_names))
        self.stable_board_cards = self._stabilize_card_tuple(
            self.board_cards_history,
            self.stable_board_cards,
            up_hits=self.board_up_confirm_hits,
            down_hits=self.board_down_confirm_hits,
            swap_hits=self.board_swap_confirm_hits,
            allow_empty=True,
        )[:5]
        board_card_names = list(self.stable_board_cards)
        board_cards = min(5, len(board_card_names))
        new_street = STREET_MAP.get(board_cards, self.game_state.get('street', "Preflop"))
        self.game_state['board_cards'] = board_card_names

        if self.detect_new_hand(board_cards):
            self.reset_hand()

        street_changed = self.detect_street_change(new_street)
        if street_changed:
            print(f"\n{'🔔' * 25}")
            print(f"  STREET: {self.game_state['street']} → {new_street}")
            print(f"{'🔔' * 25}")
            self.game_state['street'] = new_street
            self.reset_street()
        self.prev_board_count = board_cards

        prev_hero_hand = self.hero_hand
        prev_hero_cards = tuple(self.hero_cards)

        hero_ranked = sorted(
            hero_candidates.values(),
            key=lambda item: (item["conf"], item["y"]),
            reverse=True,
        )
        raw_hero_cards = []
        raw_hero_box = None
        single_hero_detected = False
        if hero_ranked:
            raw_hero_cards = [hero_ranked[0]["name"]]
            single_hero_detected = True
        if len(hero_ranked) >= 2:
            selected = hero_ranked[:2]
            raw_hero_cards = [selected[0]["name"], selected[1]["name"]]
            single_hero_detected = False
            all_x = [c["bbox"][0] for c in selected] + [c["bbox"][2] for c in selected]
            all_y = [c["bbox"][1] for c in selected] + [c["bbox"][3] for c in selected]
            raw_hero_box = (min(all_x), min(all_y), max(all_x), max(all_y))

        raw_hero_tuple = self._canonical_card_tuple(raw_hero_cards) if len(raw_hero_cards) >= 2 else tuple()
        self.hero_cards_history.append(raw_hero_tuple)
        self.stable_hero_cards = self._stabilize_card_tuple(
            self.hero_cards_history,
            self.stable_hero_cards,
            up_hits=self.hero_up_confirm_hits,
            down_hits=self.hero_down_confirm_hits,
            swap_hits=self.hero_swap_confirm_hits,
            allow_empty=True,
        )[:2]

        if len(self.stable_hero_cards) >= 2:
            self.hero_cards = list(self.stable_hero_cards)
            self.hero_hand = normalize_hand(self.hero_cards[0], self.hero_cards[1])
            if (
                len(raw_hero_cards) >= 2
                and self._canonical_card_tuple(raw_hero_cards) == self._canonical_card_tuple(self.stable_hero_cards)
            ):
                self.stable_hero_box = raw_hero_box
            self.hero_box = self.stable_hero_box
            self.hero_missing_frames = 0
            self.last_confirmed_hero_hand = self.hero_hand
            self.last_confirmed_hero_cards = list(self.hero_cards)
            self.last_confirmed_hero_box = self.hero_box

            if self.verbose_runtime or self.hero_hand != prev_hero_hand or tuple(self.hero_cards) != prev_hero_cards:
                print(f"  ✅ HERO HAND: {self.hero_cards[0]} {self.hero_cards[1]} → {self.hero_hand}")
        else:
            self.hero_missing_frames += 1
            if self.last_confirmed_hero_hand and self.hero_missing_frames <= self.hero_hold_frames:
                self.hero_hand = self.last_confirmed_hero_hand
                self.hero_cards = list(self.last_confirmed_hero_cards)
                self.hero_box = self.last_confirmed_hero_box
                self.stable_hero_box = self.last_confirmed_hero_box
                if single_hero_detected and self.verbose_runtime:
                    print(f"  ⚠️  Hero partial detection, holding last hand: {self.hero_hand}")
            else:
                if single_hero_detected and (self.verbose_runtime or prev_hero_hand is not None):
                    print(f"  ⚠️  Only 1 hero card detected: {raw_hero_cards[0]}")
                elif self.hero_hand:
                    print(f"  ❌ No hero cards detected (was: {self.hero_hand})")
                self.hero_hand = None
                self.hero_cards = []
                self.hero_box = None
                self.stable_hero_box = None

        # Process players
        p_infos = dets.get('player_info', []) or dets.get('player-info', [])
        is_table_active = board_cards > 0 or bool(self.hero_hand) or len(p_infos) >= 2
        self.current_ocr_interval = (
            self.name_ocr_interval_frames_active if is_table_active else self.name_ocr_interval_frames_idle
        )
        if self.game_state.get('street') != "Preflop":
            self.current_ocr_interval = max(self.current_ocr_interval, self.postflop_min_ocr_interval)
        self.current_bb_ocr_interval = (
            self.bb_ocr_interval_frames_active if is_table_active else self.bb_ocr_interval_frames_idle
        )
        if self.bb_ocr_burst_frames > 0:
            self.bb_ocr_burst_frames -= 1
            self.current_bb_ocr_interval = min(self.current_bb_ocr_interval, self.bb_ocr_interval_frames_burst)

        def angle(b):
            return np.arctan2((b[1] + b[3]) / 2 - center[1], (b[0] + b[2]) / 2 - center[0])

        p_infos.sort(key=angle)
        player_ids = self._assign_player_ids(p_infos)
        dealer_btns = dets.get('dealer_btn', [])
        dealer_box = dealer_btns[0] if dealer_btns else None
        dealer_idx = -1
        current_players = []
        analysis_street = self.game_state.get("street", "Preflop")
        names_assigned = {}
        name_ocr_candidate_indices = set()
        bb_ocr_candidate_indices = set()
        bootstrap_name_scan = self.hand_name_bootstrap_frames_left > 0
        if self.hand_name_bootstrap_frames_left > 0:
            self.hand_name_bootstrap_frames_left -= 1
        if p_infos:
            unknown_cached = 0
            for pid in player_ids:
                cache = self.player_ocr_cache.get(pid, {})
                cached_name = cache.get("stable_name", cache.get("name", "Unknown"))
                if not self._is_valid_player_name(cached_name):
                    unknown_cached += 1
            dynamic_name_budget = self.max_name_ocr_players_per_frame
            if bootstrap_name_scan:
                dynamic_name_budget = max(dynamic_name_budget, self.name_bootstrap_budget)
            if unknown_cached >= max(2, len(p_infos) // 2):
                dynamic_name_budget = max(dynamic_name_budget, min(len(p_infos), self.name_bootstrap_budget))

            name_budget = min(dynamic_name_budget, len(p_infos))
            name_start_idx = self.name_ocr_round_robin_cursor % len(p_infos)
            for step in range(name_budget):
                name_ocr_candidate_indices.add((name_start_idx + step) % len(p_infos))
            self.name_ocr_round_robin_cursor = (name_start_idx + name_budget) % len(p_infos)

            bb_budget_target = (
                self.max_bb_ocr_players_per_frame_burst
                if self.bb_ocr_burst_frames > 0
                else self.max_bb_ocr_players_per_frame
            )
            bb_budget = min(bb_budget_target, len(p_infos))
            bb_start_idx = self.bb_ocr_round_robin_cursor % len(p_infos)
            for step in range(bb_budget):
                bb_ocr_candidate_indices.add((bb_start_idx + step) % len(p_infos))
            self.bb_ocr_round_robin_cursor = (bb_start_idx + bb_budget) % len(p_infos)

        for idx, box in enumerate(p_infos):
            pid = player_ids[idx] if idx < len(player_ids) else f"P{idx + 1}"
            if pid not in self.players:
                self.players[pid] = PlayerState(pid)
            player = self.players[pid]
            player.prev_status = player.status
            player.bb_prev_frame = player.bb_current

            player.is_dealer = False
            if dealer_box is not None:
                p_cent = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
                d_cent = ((dealer_box[0] + dealer_box[2]) / 2, (dealer_box[1] + dealer_box[3]) / 2)
                if ((p_cent[0] - d_cent[0]) ** 2 + (p_cent[1] - d_cent[1]) ** 2) ** 0.5 < 150:
                    player.is_dealer = True
                    dealer_idx = idx

            observed_active = False
            rival_cards = dets.get('rivals_card', [])
            for rc in rival_cards:
                r_cent = ((rc[0] + rc[2]) / 2, (rc[1] + rc[3]) / 2)
                p_cent = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
                if ((r_cent[0] - p_cent[0]) ** 2 + (r_cent[1] - p_cent[1]) ** 2) ** 0.5 < 200:
                    observed_active = True
                    break

            if pid in self.folded_player_ids_hand:
                player.status = "Folded"
            elif observed_active:
                player.status = "Active"
                self.fold_candidate_counts[pid] = 0
            else:
                if analysis_street != "Preflop":
                    # Postflop cards can be hidden; keep prior active state to avoid mass false folds.
                    player.status = "Active" if player.prev_status == "Active" else "Folded"
                    self.fold_candidate_counts[pid] = 0
                    cached = self.player_ocr_cache.get(pid, {})
                    stable_name = cached.get("stable_name", cached.get("name", player.name))
                    name = stable_name if self._is_valid_player_name(stable_name) else player.name
                    bb_val = self._sanitize_bb_value(cached.get("bb", player.bb_current))
                    if self._is_valid_player_name(name):
                        owner_pid = names_assigned.get(name)
                        if owner_pid is None or owner_pid == pid:
                            player.name = name
                            names_assigned[name] = pid
                            self.player_db.get_player(name)
                        else:
                            existing_name = str(player.name).strip()
                            if self._is_valid_player_name(existing_name):
                                existing_owner = names_assigned.get(existing_name)
                                if existing_owner is None or existing_owner == pid:
                                    names_assigned[existing_name] = pid
                                else:
                                    player.name = "Unknown"
                    if bb_val and bb_val > 0:
                        player.bb_current = self._sanitize_bb_value(bb_val)
                    # Continue processing OCR/action detection even when rivals_card is hidden.
                else:
                    if player.prev_status == "Active":
                        cnt = self.fold_candidate_counts.get(pid, 0) + 1
                        self.fold_candidate_counts[pid] = cnt
                        if cnt >= self.fold_confirm_frames:
                            player.status = "Folded"
                            self.folded_player_ids_hand.add(pid)
                            action_record = {'player': player.name, 'action': 'FOLD', 'position': player.position, 'amount': 0}
                            self.current_hand_actions.append(action_record)
                            self.player_db.update_action(
                                player.name,
                                'FOLD',
                                is_preflop=(analysis_street == "Preflop"),
                            )
                            print(f"  ❌ {player.name} ({player.position}) FOLDED")
                        else:
                            # Keep ACTIVE until fold is confirmed on multiple frames.
                            player.status = "Active"
                    else:
                        player.status = "Folded"

            cached = self.player_ocr_cache.get(pid, {})
            stable_name = cached.get("stable_name", cached.get("name", player.name))
            name = stable_name if self._is_valid_player_name(stable_name) else player.name
            player.bb_current = self._sanitize_bb_value(player.bb_current)
            player.bb_prev_frame = self._sanitize_bb_value(player.bb_prev_frame)
            bb_val = self._sanitize_bb_value(cached.get("bb", player.bb_current))
            bb_refreshed_this_frame = False
            cached_name_frame = cached.get("name_frame", cached.get("frame", -10_000))
            cached_bb_frame = cached.get("bb_frame", cached.get("frame", -10_000))
            stable_name_known = self._is_valid_player_name(stable_name)
            name_is_stale = (self.frame_count - cached_name_frame) >= self.name_stale_frames
            effective_name_interval = self.current_ocr_interval * (
                self.name_refresh_multiplier if stable_name_known else 1
            )
            name_interval_elapsed = (self.frame_count - cached_name_frame) >= effective_name_interval
            bb_interval_elapsed = (self.frame_count - cached_bb_frame) >= self.current_bb_ocr_interval
            priority_name_ocr = (
                player.name in ["Unknown", "?", ""]
                or not stable_name_known
            )
            priority_bb_ocr = (
                (player.status == "Active" and player.bb_current <= 0)
                or (self._is_hero_player(player) and player.bb_current <= 0)
            )
            should_run_name_ocr = (
                ((player.status == "Active" or priority_name_ocr) and street_changed)
                or (
                    idx in name_ocr_candidate_indices
                    and (name_interval_elapsed or priority_name_ocr or bootstrap_name_scan)
                )
                or (
                    idx in name_ocr_candidate_indices
                    and name_is_stale
                )
            )
            should_run_bb_ocr = (
                (player.status == "Active" and street_changed)
                or (
                    idx in bb_ocr_candidate_indices
                    and (bb_interval_elapsed or priority_bb_ocr)
                    and (player.status == "Active" or priority_bb_ocr)
                )
            )

            if should_run_name_ocr or should_run_bb_ocr:
                x1 = max(0, int(box[0] - 5))
                y1 = max(0, int(box[1] - 5))
                x2 = min(w, int(box[2] + 5))
                y2 = min(h, int(box[3] + 5))
                if (x2 - x1) >= self.ocr_min_crop_side and (y2 - y1) >= self.ocr_min_crop_side:
                    crop = frame[y1:y2, x1:x2]
                    name_crop, bb_crop = self._split_player_info_crop(crop)
                    next_cache = dict(cached)

                    if should_run_name_ocr:
                        ocr_name = self.parse_player_name(name_crop)
                        if self._is_valid_player_name(ocr_name):
                            stable_name, pending_name, pending_hits = self._update_name_consensus(cached, ocr_name)
                            if self._is_valid_player_name(stable_name):
                                name = stable_name
                            invalid_name_hits = 0
                        else:
                            stable_name = cached.get("stable_name", name)
                            pending_name = cached.get("pending_name")
                            pending_hits = int(cached.get("pending_name_hits", 0))
                            invalid_name_hits = int(cached.get("invalid_name_hits", 0)) + 1
                            # If name OCR is stale and repeatedly invalid, clear stale seat label.
                            if invalid_name_hits >= self.invalid_name_reset_hits and player.status != "Active":
                                stable_name = "Unknown"
                                name = "Unknown"
                                pending_name = None
                                pending_hits = 0
                        next_cache.update({
                            "name": name,
                            "stable_name": stable_name if self._is_valid_player_name(stable_name) else name,
                            "pending_name": pending_name,
                            "pending_name_hits": pending_hits,
                            "invalid_name_hits": invalid_name_hits,
                            "name_frame": self.frame_count,
                        })

                    if should_run_bb_ocr:
                        ocr_bb = self.parse_player_bb(bb_crop)
                        accepted_bb, next_cache, bb_committed = self._apply_bb_consensus(player, ocr_bb, next_cache)
                        if bb_committed:
                            bb_val = accepted_bb
                            bb_refreshed_this_frame = True
                        next_cache.update({
                            "bb": self._sanitize_bb_value(bb_val),
                            "bb_frame": self.frame_count if bb_committed else cached_bb_frame,
                        })

                    next_cache["frame"] = self.frame_count
                    self.player_ocr_cache[pid] = next_cache

            if self._is_valid_player_name(name):
                owner_pid = names_assigned.get(name)
                if owner_pid is None or owner_pid == pid:
                    player.name = name
                    names_assigned[name] = pid
                    self.player_db.get_player(name)
                else:
                    existing_name = str(player.name).strip()
                    if self._is_valid_player_name(existing_name):
                        existing_owner = names_assigned.get(existing_name)
                        if existing_owner is None or existing_owner == pid:
                            names_assigned[existing_name] = pid
                        else:
                            player.name = "Unknown"

            if bb_val and bb_val > 0:
                player.bb_current = self._sanitize_bb_value(bb_val)

            bb_ready_for_action = (
                player.bb_current > 0.0 and player.bb_prev_frame > 0.0 and player.bb_street_start > 0.0
            )
            if player.status == "Active" and bb_ready_for_action and (bb_refreshed_this_frame or street_changed):
                invested_now = max(0.0, player.bb_street_start - player.bb_current)
                can_rearm = invested_now >= (player.last_action_invested + self.action_rearm_invest_delta)
                allow_action_detection = (player.action_this_street is None) or can_rearm

                if allow_action_detection:
                    action, new_high = player.detect_action_from_delta(
                        self.high_bet_current_street,
                        self.raises_count,
                        bb_blind=1.0
                    )
                    if action:
                        action_upper = str(action).upper()
                        # Avoid repeating passive no-invest actions after first detection.
                        if player.action_this_street is not None and action_upper in ['CHECK', 'LIMP']:
                            pass
                        else:
                            player.detected_action = action
                            player.action_this_street = action
                            player.last_action_invested = max(player.last_action_invested, invested_now)
                            self.bb_ocr_burst_frames = max(
                                self.bb_ocr_burst_frames,
                                self.bb_ocr_burst_duration_frames,
                            )
                            if 'BET' in action or action == 'RAISE':
                                self.high_bet_current_street = new_high
                                self.raises_count += 1

                            action_record = {
                                'player': player.name,
                                'action': action,
                                'position': player.position,
                                'amount': max(0.0, player.bb_street_start - player.bb_current)
                            }
                            self.current_hand_actions.append(action_record)
                            self.player_db.update_action(
                                player.name,
                                action,
                                is_preflop=(analysis_street == "Preflop"),
                            )
                            emoji = {
                                'CALL': '🟡',
                                'CHECK': '⚪',
                                'LIMP': '🟢',
                                'RAISE': '🟢',
                                '3BET': '🔴',
                                '4BET': '🔥',
                                'ALL-IN': '💥'
                            }.get(action, '📊')
                            print(f"  {emoji} {player.name} ({player.position}): {action} ({action_record['amount']:.1f}BB)")
                            print(f"      └─ HighBet: {self.high_bet_current_street:.1f}BB | Raises: {self.raises_count}")

            current_players.append(player)

        self.game_state['pot'] = round(
            sum(max(0.0, p.bb_street_start - p.bb_current) for p in current_players), 2
        )

        if dealer_idx != -1:
            n = len(current_players)
            positions = ['BTN', 'SB', 'BB', 'UTG', 'MP', 'CO', 'UTG+1', 'UTG+2']
            for i, player in enumerate(current_players):
                offset = (i - dealer_idx) % n
                player.position = positions[offset] if offset < len(positions) else f"Pos{offset}"

        # Hero resolution: prefer name match, fallback to bottom-center seat geometry.
        frame_hero_pid_by_name = None
        frame_hero_pid_by_geometry = None
        best_geo_score = -10_000.0
        for i, player in enumerate(current_players):
            if self._is_hero_name_match(player.name):
                frame_hero_pid_by_name = player.id

            if i < len(p_infos):
                box = p_infos[i]
                cx = (box[0] + box[2]) / 2.0
                cy = (box[1] + box[3]) / 2.0
                if cy >= h * 0.56:
                    # Favors bottom-center seats to identify hero even with OCR name noise.
                    geo_score = (cy / max(h, 1.0)) * 2.0 - abs(cx - center[0]) / max(center[0], 1.0)
                    if geo_score > best_geo_score:
                        best_geo_score = geo_score
                        frame_hero_pid_by_geometry = player.id

        current_pids = {p.id for p in current_players}
        if frame_hero_pid_by_name and frame_hero_pid_by_name in current_pids:
            chosen_hero_pid = frame_hero_pid_by_name
            reason = "name"
        elif self.hero_pid in current_pids:
            # Keep previous hero lock stable; do not override with geometry noise.
            chosen_hero_pid = self.hero_pid
            reason = "sticky"
        else:
            chosen_hero_pid = frame_hero_pid_by_geometry
            reason = "geometry"

        if chosen_hero_pid and chosen_hero_pid in current_pids:
            if self.hero_pid != chosen_hero_pid:
                print(f"  👤 HERO LOCK ({reason}): pid={chosen_hero_pid}")
            self.hero_pid = chosen_hero_pid
            self.hero_pid_missing_frames = 0
        else:
            self.hero_pid_missing_frames += 1
            if self.hero_pid_missing_frames > self.hero_pid_hold_frames:
                self.hero_pid = None
                self.hero_position = None

        hero_state = next((p for p in current_players if self._is_hero_player(p)), None)
        if hero_state is not None:
            if hero_state.position and hero_state.position != "?" and hero_state.position != self.hero_position:
                print(f"  👤 HERO POSITION UPDATE: {hero_state.name} @ {hero_state.position}")
            if hero_state.position and hero_state.position != "?":
                self.hero_position = hero_state.position

        previous_suggestion = self.last_gto_suggestion
        suggestion = self.last_gto_suggestion or "Waiting..."
        opponent_actions = []
        hero_folded = False
        current_street = self.game_state.get("street", "Preflop")

        if self.hero_hand and self.hero_position and self.hero_position != "?":
            hero_state = next((p for p in current_players if self._is_hero_player(p)), None)
            active_players = [
                p for p in current_players
                if p.status == "Active" and p.id not in self.folded_player_ids_hand
            ]
            if hero_state is not None:
                hero_folded = hero_state.status == "Folded" or hero_state.id in self.folded_player_ids_hand
            else:
                hero_folded = any(
                    (p.position == self.hero_position) and (p.status == "Folded" or p.id in self.folded_player_ids_hand)
                    for p in current_players
                )
            if hero_folded:
                suggestion = "Hero foldato - attesa nuova mano"
                self.gto_suggestion = suggestion
                self.last_gto_suggestion = suggestion
            else:
                opponent_actions = [
                    p.detected_action for p in active_players
                    if (not self._is_hero_player(p)) and p.detected_action
                ]
                num_opp = max(1, len([p for p in active_players if not self._is_hero_player(p)]))
                hero_stack_bb = hero_state.bb_current if hero_state is not None else 100.0
                try:
                    # M3: unified preflop+postflop advice from the strong engine
                    # (postflop is now real equity/pot-odds, not a placeholder).
                    decision = live_decision(
                        self.hero_cards, self.game_state.get('board_cards', []),
                        self.hero_position, current_street,
                        self.game_state.get('pot', 0.0), self.high_bet_current_street,
                        self.raises_count, hero_stack_bb, num_opp,
                    )
                    suggestion = format_suggestion(decision, self.hero_hand)
                    self.gto_suggestion = suggestion
                    self.last_gto_suggestion = suggestion
                except Exception as e:
                    suggestion = f"{self.hero_hand} - CHECK"
                    self.gto_suggestion = suggestion
                    self.last_gto_suggestion = suggestion
                    print(f"  ⚠️ Engine Error: {e}")
        elif self.hero_hand and (not self.hero_position or self.hero_position == "?"):
            # Provide conservative fallback immediately while position is being resolved.
            opponent_actions = [
                p.detected_action for p in current_players
                if p.status == "Active" and p.detected_action and (not self._is_hero_player(p))
            ]
            try:
                num_opp = max(1, len([
                    p for p in current_players
                    if p.status == "Active" and not self._is_hero_player(p)
                ]))
                decision = live_decision(
                    self.hero_cards, self.game_state.get('board_cards', []),
                    None, current_street,
                    self.game_state.get('pot', 0.0), self.high_bet_current_street,
                    self.raises_count, 100.0, num_opp,
                )
                suggestion = f"{format_suggestion(decision, self.hero_hand)} (provvisorio: posizione non rilevata)"
                self.gto_suggestion = suggestion
                self.last_gto_suggestion = suggestion
            except Exception as e:
                suggestion = f"{self.hero_hand} - CHECK"
                self.gto_suggestion = suggestion
                self.last_gto_suggestion = suggestion
                print(f"  ⚠️ Engine Error: {e}")
        elif not self.hero_position or self.hero_position == "?":
            suggestion = "Posizione non rilevata"
            self.gto_suggestion = suggestion
            self.last_gto_suggestion = suggestion
        elif not self.hero_hand:
            suggestion = "Carte non rilevate"
            self.gto_suggestion = suggestion
            self.last_gto_suggestion = suggestion

        suggestion_changed = suggestion != previous_suggestion
        if suggestion_changed:
            print(f"  🎯 GTO: {suggestion} (Position: {self.hero_position}, Hand: {self.hero_hand})")

        players_snapshot = [
            {
                "id": p.id,
                "name": p.name,
                "bb_current": p.bb_current,
                "status": p.status,
                "position": p.position,
                "is_dealer": p.is_dealer,
                "detected_action": p.detected_action,
            }
            for p in current_players
        ]

        ws_message = None
        if self.ws_server is not None:
            try:
                ws_message = create_game_state_message(self)
            except Exception:
                ws_message = None

        return {
            "suggestion": suggestion,
            "opponent_actions": opponent_actions,
            "hero_box": self.hero_box,
            "board_cards": board_cards,
            "active_mode": (board_cards > 0 or bool(self.hero_hand) or bool(current_players)),
            "street": self.game_state['street'],
            "hand_id": self.hand_id,
            "hero_hand": self.hero_hand,
            "hero_position": self.hero_position,
            "high_bet": self.high_bet_current_street,
            "raises_count": self.raises_count,
            "players_snapshot": players_snapshot,
            "ws_message": ws_message,
            "force_log": street_changed or suggestion_changed,
        }

    def _emit_runtime_output(self, payload):
        """Overlay + console + websocket output stage (main thread)."""
        suggestion = payload.get("suggestion", "Waiting...")
        opponent_actions = payload.get("opponent_actions", [])
        hero_box = payload.get("hero_box")
        players_snapshot = payload.get("players_snapshot", [])
        active_mode = bool(payload.get("active_mode"))

        self.loop_sleep_seconds = self.loop_sleep_active if active_mode else self.loop_sleep_idle
        self.main_loop_sleep = self.main_loop_sleep_active if active_mode else self.main_loop_sleep_idle
        self.capture_thread_sleep = self.capture_thread_sleep_active if active_mode else self.capture_thread_sleep_idle

        if not active_mode:
            now_ts = time.time()
            if (
                suggestion != self._last_wait_message
                or (now_ts - self._last_wait_log_ts) >= self.wait_log_interval
            ):
                print(f"⏳ {suggestion}")
                self._last_wait_message = suggestion
                self._last_wait_log_ts = now_ts

        if hero_box and self.hud is not None:
            try:
                x, y, x2, y2 = hero_box
                w = x2 - x
                h = y2 - y
                if self.hud.window_bounds is not None:
                    draw_x, draw_y = int(x), int(y)
                else:
                    x_screen, y_screen = self.window_capture.map_roi_to_screen(x, y)
                    draw_x, draw_y = int(x_screen), int(y_screen)

                suggestion_upper = suggestion.upper()
                if 'RAISE' in suggestion_upper or 'BET' in suggestion_upper:
                    color = 'green'
                elif 'CALL' in suggestion_upper:
                    color = 'yellow'
                elif 'FOLD' in suggestion_upper:
                    color = 'red'
                else:
                    color = 'orange'

                self.hud.update_suggestion(suggestion, draw_x, draw_y, int(w), int(h), color)
                self.hud.show_overlay()
            except Exception as e:
                print(f"  ⚠️ HUD update error: {e}")
        elif self.hud is not None:
            self.hud.hide_overlay()

        self._emit_counter += 1
        should_log_summary = payload.get("force_log", False) or (
            active_mode and (self._emit_counter % self.console_log_interval == 0)
        )

        if should_log_summary:
            print(f"\n📊 {payload.get('street')} | Hand #{payload.get('hand_id')} | Cards: {payload.get('board_cards')}")
            print(f"💰 HighBet: {payload.get('high_bet', 0.0):.1f}BB | Raises: {payload.get('raises_count', 0)}")
            if payload.get("hero_hand"):
                print(f"🃏 Hero: {payload.get('hero_hand')} @ {payload.get('hero_position')}")
            print("-" * 60)
            for p in players_snapshot:
                marks = []
                if p.get("is_dealer"):
                    marks.append("🔘")
                if p.get("detected_action"):
                    marks.append(f"[{p.get('detected_action')}]")
                marks_str = " ".join(marks)
                print(
                    f"{p.get('id')}: {p.get('name', 'Unknown'):12} | "
                    f"{p.get('bb_current', 0.0):6.1f}BB | {p.get('status', '?'):8} | "
                    f"{p.get('position', '?'):6} {marks_str}"
                )
            if opponent_actions:
                print(f"   vs: {opponent_actions}")
            print("")

        ws_message = payload.get("ws_message")
        if ws_message and self.ws_server is not None:
            now_perf = time.perf_counter()
            if payload.get("force_log", False) or (now_perf - self._last_ws_broadcast_ts) >= self.ws_broadcast_min_interval:
                try:
                    self.ws_server.broadcast_sync(ws_message)
                    self._last_ws_broadcast_ts = now_perf
                except Exception:
                    pass

    def _record_latency(self, payload, emit_start, emit_end):
        timestamps = payload.get("timestamps", {})
        capture_start = timestamps.get("capture_start")
        capture_end = timestamps.get("capture_end")
        infer_start = timestamps.get("infer_start")
        infer_end = timestamps.get("infer_end")
        state_start = timestamps.get("state_start")
        state_end = timestamps.get("state_end")
        if None in [capture_start, capture_end, infer_start, infer_end, state_start, state_end]:
            return

        capture_ms = max(0.0, (capture_end - capture_start) * 1000.0)
        infer_ms = max(0.0, (infer_end - infer_start) * 1000.0)
        state_ms = max(0.0, (state_end - state_start) * 1000.0)
        emit_ms = max(0.0, (emit_end - emit_start) * 1000.0)
        e2e_ms = max(0.0, (emit_end - capture_start) * 1000.0)
        self.latency_profiler.add(capture_ms, infer_ms, state_ms, emit_ms, e2e_ms)

        if self.latency_profiler.should_report():
            s = self.latency_profiler.summary()
            print(
                "⏱️ LATENCY "
                f"p50={s['e2e_p50_ms']:.1f}ms "
                f"p95={s['e2e_p95_ms']:.1f}ms "
                f"p99={s['e2e_p99_ms']:.1f}ms | "
                f"mean(c/i/s/e)={s['capture_mean_ms']:.1f}/{s['infer_mean_ms']:.1f}/{s['state_mean_ms']:.1f}/{s['emit_mean_ms']:.1f}ms"
            )

    def _capture_worker(self):
        while not self.pipeline_stop.is_set():
            t0 = time.perf_counter()
            frame = self.capture()
            t1 = time.perf_counter()
            packet = {
                "frame": frame,
                "timestamps": {
                    "capture_start": t0,
                    "capture_end": t1,
                }
            }
            self._put_latest(self.capture_queue, packet)
            time.sleep(0.05 if frame is None else self.capture_thread_sleep)

    def _inference_worker(self):
        while not self.pipeline_stop.is_set():
            try:
                packet = self.capture_queue.get(timeout=0.2)
            except Empty:
                continue

            frame = packet.get("frame")
            timestamps = packet.setdefault("timestamps", {})
            if frame is None:
                now = time.perf_counter()
                timestamps["infer_start"] = now
                timestamps["infer_end"] = now
                packet["results"] = None
                self._put_latest(self.infer_queue, packet)
                continue

            try:
                timestamps["infer_start"] = time.perf_counter()
                packet["results"] = self.model(frame, **self.inference_kwargs)[0]
                timestamps["infer_end"] = time.perf_counter()
            except Exception as e:
                timestamps["infer_end"] = time.perf_counter()
                packet["results"] = None
                packet["error"] = f"Inference error: {e}"
            self._put_latest(self.infer_queue, packet)

    def _state_worker(self):
        while not self.pipeline_stop.is_set():
            try:
                packet = self.infer_queue.get(timeout=0.2)
            except Empty:
                continue

            frame = packet.get("frame")
            results = packet.get("results")
            timestamps = packet.setdefault("timestamps", {})
            timestamps["state_start"] = time.perf_counter()

            if frame is None or results is None:
                message = packet.get("error", "Waiting for table lock...")
                payload = self._build_waiting_payload(message)
            else:
                try:
                    payload = self._process_state(frame, results)
                except Exception as e:
                    payload = self._build_waiting_payload(f"State error: {e}")

            timestamps["state_end"] = time.perf_counter()
            payload["timestamps"] = timestamps
            self._put_latest(self.render_queue, payload)

    def _start_pipeline(self):
        self.pipeline_stop.clear()
        workers = [
            ("capture", self._capture_worker),
            ("inference", self._inference_worker),
            ("state", self._state_worker),
        ]
        self.pipeline_threads = []
        for name, target in workers:
            thread = threading.Thread(target=target, daemon=True, name=f"poker-{name}")
            thread.start()
            self.pipeline_threads.append(thread)
        print("✅ Async pipeline started: capture -> inference -> state -> overlay")

    def _stop_pipeline(self):
        self.pipeline_stop.set()
        for thread in self.pipeline_threads:
            thread.join(timeout=1.0)
        self.pipeline_threads = []

    def process(self):
        """Sequential fallback processing (used if async pipeline is disabled)."""
        frame = self.capture()
        if frame is None:
            payload = self._build_waiting_payload("Waiting for table lock...")
            self._emit_runtime_output(payload)
            return

        results = self.model(frame, **self.inference_kwargs)[0]
        payload = self._process_state(frame, results)
        self._emit_runtime_output(payload)

    def run(self):
        """Main loop"""
        QApplication = self._QApplication if self.qt_available else None

        print("\n" + "=" * 70)
        print("🎮 SYSTEM READY - Press Ctrl+C to stop")
        print("=" * 70 + "\n")

        try:
            if self.use_async_pipeline:
                self._start_pipeline()
                while True:
                    payload = None
                    try:
                        payload = self.render_queue.get(timeout=0.2)
                    except Empty:
                        payload = None

                    if payload is not None:
                        emit_start = time.perf_counter()
                        self._emit_runtime_output(payload)
                        emit_end = time.perf_counter()
                        self._record_latency(payload, emit_start, emit_end)

                    now = time.perf_counter()
                    if now - self._last_reposition_ts >= self.reposition_interval:
                        current_bounds = self.window_capture.get_current_bounds()
                        if current_bounds and self.hud is not None:
                            self.hud.reposition(current_bounds)
                        self._last_reposition_ts = now

                    if QApplication and QApplication.instance():
                        QApplication.processEvents()
                    time.sleep(self.main_loop_sleep)
            else:
                while True:
                    self.process()
                    current_bounds = self.window_capture.get_current_bounds()
                    if current_bounds and self.hud is not None:
                        self.hud.reposition(current_bounds)
                    if QApplication and QApplication.instance():
                        QApplication.processEvents()
                    time.sleep(self.loop_sleep_seconds)
        except KeyboardInterrupt:
            print("\n\n⛔ Shutting down...")
        finally:
            self._stop_pipeline()
            try:
                self.player_db.save(force=True)
            except Exception:
                pass
            try:
                self.tournament_reporter.generate_report(self.player_db.data, force=True)
            except Exception:
                pass
            try:
                if len(self.latency_profiler.e2e_ms) > 0:
                    s = self.latency_profiler.summary()
                    print(
                        "⏱️ LATENCY FINAL "
                        f"samples={s['samples']} "
                        f"p50={s['e2e_p50_ms']:.1f}ms "
                        f"p95={s['e2e_p95_ms']:.1f}ms "
                        f"p99={s['e2e_p99_ms']:.1f}ms"
                    )
            except Exception:
                pass
            if self.hud is not None:
                self.hud.stop()
            print("✅ Session saved. Goodbye!")

if __name__ == "__main__":
    bot = PokerVisionPro()
    bot.run()
