"""
Window Capture Module - macOS Quartz Implementation
Detects poker client windows and provides precise ROI capture
"""

import time
import numpy as np

# Try to import Quartz, fallback gracefully
try:
    import Quartz
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID
    )
    QUARTZ_AVAILABLE = True
    WINDOW_IMAGE_CAPTURE_AVAILABLE = all(
        hasattr(Quartz, attr)
        for attr in [
            "CGWindowListCreateImage",
            "kCGWindowListOptionIncludingWindow",
            "kCGWindowImageBoundsIgnoreFraming",
            "CGRectNull",
            "CGImageGetWidth",
            "CGImageGetHeight",
            "CGImageGetBytesPerRow",
            "CGImageGetDataProvider",
            "CGDataProviderCopyData",
        ]
    )
except ImportError:
    print("⚠️  Warning: pyobjc-framework-Quartz not found. Install with: pip install pyobjc-framework-Quartz")
    QUARTZ_AVAILABLE = False
    WINDOW_IMAGE_CAPTURE_AVAILABLE = False


class WindowCapture:
    """
    Manages poker window detection and ROI-based capture
    """
    
    # Common poker client keywords
    POKER_KEYWORDS = [
        "poker", "pokerstars", "888poker", "888", 
        "partypoker", "party", "ggpoker", "gg",
        "winamax", "unibet", "betfair", "bet365"
    ]

    # Browser owners to always exclude
    EXCLUDED_OWNERS = [
        "safari", "chrome", "firefox", "edge", "opera", "brave", "arc"
    ]

    # Non-table poker windows to avoid locking (lobby/popups)
    EXCLUDED_TITLE_KEYWORDS = [
        "lobby", "registrazione", "registration", "cashier", "cassa",
        "account", "impostazioni", "settings", "bonus", "deposit", "withdraw"
    ]

    # Real table hints (Italian + English)
    TABLE_HINT_KEYWORDS = ["tavolo", "table"]
    
    def __init__(
        self,
        keywords=None,
        refresh_interval=2.0,
        allow_fullscreen_fallback=False,
        preferred_owners=None
    ):
        """
        Initialize window capture
        
        Args:
            keywords: List of keywords to search for (default: POKER_KEYWORDS)
            refresh_interval: Seconds between window position refreshes
        """
        if not QUARTZ_AVAILABLE:
            print("❌ Quartz not available. Using fullscreen fallback.")
            self.mode = 'fullscreen'
        else:
            self.mode = 'window'
        
        self.keywords = keywords or self.POKER_KEYWORDS
        self.refresh_interval = refresh_interval
        self.allow_fullscreen_fallback = allow_fullscreen_fallback
        self.preferred_owners = [p.lower() for p in (preferred_owners or ["pokerstars"])]
        
        # State
        self.current_window = None
        self.current_bounds = None
        self.last_refresh = 0
        self.locked_window_id = None
        self.window_id_capture_enabled = bool(QUARTZ_AVAILABLE and WINDOW_IMAGE_CAPTURE_AVAILABLE)
        self._last_reported_window_id = None
        self._last_no_window_log_ts = 0.0
        self._last_hold_log_ts = 0.0
        self._last_capture_error_log_ts = 0.0
        self._window_id_capture_ok = 0
        self._window_id_capture_fail = 0

        # Try initial detection
        if self.mode == 'window':
            self._refresh_window()
    
    def find_poker_window(self):
        """
        Find poker client window using Quartz
        
        Returns:
            tuple: (window_id, title, bounds_dict) or None
        """
        if not QUARTZ_AVAILABLE:
            return None
        
        try:
            # Get all on-screen windows
            window_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID
            )
            if not window_list:
                now = time.time()
                if now - self._last_no_window_log_ts > 2.0:
                    print("⚠️  Quartz did not return window list. Waiting for target window...")
                    self._last_no_window_log_ts = now
                return None

            candidates = []

            for window in window_list:
                # Ignore non-standard layers (tooltips/overlays)
                if int(window.get('kCGWindowLayer', 0)) != 0:
                    continue

                title = str(window.get('kCGWindowName', '') or '')
                owner = str(window.get('kCGWindowOwnerName', '') or '')
                title_l = title.lower()
                owner_l = owner.lower()

                # Hard exclude browsers, even if title contains "poker"
                if any(ex in owner_l for ex in self.EXCLUDED_OWNERS):
                    continue

                search_text = f"{title_l} {owner_l}"
                keyword_match = any(k.lower() in search_text for k in self.keywords)
                preferred_match = any(p in owner_l or p in title_l for p in self.preferred_owners)
                table_like = any(k in title_l for k in self.TABLE_HINT_KEYWORDS)
                excluded_title = any(k in title_l for k in self.EXCLUDED_TITLE_KEYWORDS)

                # Only keep poker-related windows
                if not keyword_match and not preferred_match:
                    continue
                if excluded_title and not table_like:
                    continue

                window_id = int(window.get('kCGWindowNumber', 0))
                bounds = window.get('kCGWindowBounds', {})
                bounds_dict = {
                    'x': int(bounds.get('X', 0)),
                    'y': int(bounds.get('Y', 0)),
                    'width': int(bounds.get('Width', 0)),
                    'height': int(bounds.get('Height', 0))
                }

                # Skip invalid windows
                if bounds_dict['width'] < 300 or bounds_dict['height'] < 240:
                    continue

                score = 0
                if preferred_match:
                    score += 200
                if any(p in owner_l for p in self.preferred_owners):
                    score += 120
                if table_like:
                    score += 180
                if "torneo" in title_l or "tournament" in title_l:
                    score += 40
                if keyword_match:
                    score += 20
                if self.locked_window_id and window_id == self.locked_window_id:
                    score += 800

                candidates.append((score, window_id, title, owner, bounds_dict, table_like))

            if not candidates:
                now = time.time()
                if now - self._last_no_window_log_ts > 2.0:
                    print("⚠️  No poker window found. Waiting for target window...")
                    self._last_no_window_log_ts = now
                return None

            # Hard-keep the currently locked table if still visible.
            if self.locked_window_id is not None:
                for candidate in candidates:
                    if candidate[1] == self.locked_window_id:
                        score, window_id, title, owner, bounds_dict, _ = candidate
                        if self._last_reported_window_id != window_id:
                            print(f"✅ Locked poker window: '{title}' (Owner: {owner}, score={score})")
                            print(f"   Bounds: ({bounds_dict['x']}, {bounds_dict['y']}, {bounds_dict['width']}x{bounds_dict['height']})")
                            self._last_reported_window_id = window_id
                        return (window_id, title, bounds_dict)

            table_candidates = [c for c in candidates if c[5]]
            if table_candidates:
                candidates = table_candidates
            elif self.locked_window_id is not None:
                # Never switch from a locked table to a non-table poker window.
                return None

            candidates.sort(key=lambda c: c[0], reverse=True)
            score, window_id, title, owner, bounds_dict, _ = candidates[0]

            self.locked_window_id = window_id
            if self._last_reported_window_id != window_id:
                print(f"✅ Locked poker window: '{title}' (Owner: {owner}, score={score})")
                print(f"   Bounds: ({bounds_dict['x']}, {bounds_dict['y']}, {bounds_dict['width']}x{bounds_dict['height']})")
                self._last_reported_window_id = window_id
            return (window_id, title, bounds_dict)
            
        except Exception as e:
            print(f"❌ Error finding window: {e}")
            return None
    
    def _refresh_window(self):
        """Refresh window detection (called periodically)"""
        now = time.time()
        
        # Skip if recently refreshed
        if now - self.last_refresh < self.refresh_interval:
            return
        
        self.last_refresh = now
        
        # Find window
        result = self.find_poker_window()
        
        if result:
            window_id, title, bounds = result
            self.current_window = (window_id, title)
            self.current_bounds = bounds
            self.mode = 'window'
        else:
            # Lost window - keep last known bounds whenever possible
            if self.current_bounds is not None:
                now = time.time()
                if now - self._last_hold_log_ts > 2.0:
                    print("⚠️  Target window not found. Holding last known bounds.")
                    self._last_hold_log_ts = now
                return

            if self.allow_fullscreen_fallback:
                print("⚠️  Falling back to fullscreen mode")
                self.mode = 'fullscreen'
    
    def get_current_bounds(self):
        """
        Get current window bounds (refreshes periodically)
        
        Returns:
            dict: {'x', 'y', 'width', 'height'} or None for fullscreen
        """
        if self.mode == 'fullscreen':
            return None
        
        # Refresh if needed
        self._refresh_window()
        
        return self.current_bounds
    
    def get_roi_for_mss(self):
        """
        Get ROI dict for mss.grab()
        
        Returns:
            dict: {"left": x, "top": y, "width": w, "height": h} or None for fullscreen
        """
        bounds = self.get_current_bounds()
        
        if bounds is None:
            return None
        
        return {
            "left": bounds['x'],
            "top": bounds['y'],
            "width": bounds['width'],
            "height": bounds['height']
        }

    def is_window_id_capture_available(self):
        """Return True when Quartz window-id image capture is usable."""
        return self.mode == 'window' and self.window_id_capture_enabled

    def get_locked_window_id(self):
        """Return currently locked poker window id, if available."""
        if self.mode != 'window':
            return None
        self._refresh_window()
        if self.current_window is None:
            return None
        try:
            return int(self.current_window[0])
        except Exception:
            return None

    def capture_window_bgra(self):
        """
        Capture window content directly by locked window-id.

        Returns:
            np.ndarray (H,W,4) BGRA or None on failure.
        """
        if not self.is_window_id_capture_available():
            return None

        window_id = self.get_locked_window_id()
        if window_id is None:
            return None

        try:
            cg_image = Quartz.CGWindowListCreateImage(
                Quartz.CGRectNull,
                Quartz.kCGWindowListOptionIncludingWindow,
                window_id,
                Quartz.kCGWindowImageBoundsIgnoreFraming,
            )
            if cg_image is None:
                self._window_id_capture_fail += 1
                self._log_capture_error("CGWindowListCreateImage returned None")
                return None

            width = int(Quartz.CGImageGetWidth(cg_image))
            height = int(Quartz.CGImageGetHeight(cg_image))
            if width <= 0 or height <= 0:
                self._window_id_capture_fail += 1
                self._log_capture_error("Invalid image dimensions")
                return None

            bytes_per_row = int(Quartz.CGImageGetBytesPerRow(cg_image))
            provider = Quartz.CGImageGetDataProvider(cg_image)
            if provider is None:
                self._window_id_capture_fail += 1
                self._log_capture_error("Missing CGImage data provider")
                return None

            raw = Quartz.CGDataProviderCopyData(provider)
            if raw is None:
                self._window_id_capture_fail += 1
                self._log_capture_error("CGDataProviderCopyData returned None")
                return None

            expected = bytes_per_row * height
            buffer = np.frombuffer(raw, dtype=np.uint8)
            if buffer.size < expected:
                self._window_id_capture_fail += 1
                self._log_capture_error("Short image buffer from Quartz")
                return None

            row_view = buffer[:expected].reshape((height, bytes_per_row))
            pixel_width = width * 4
            if pixel_width > bytes_per_row:
                self._window_id_capture_fail += 1
                self._log_capture_error("Unexpected bytes_per_row < width*4")
                return None

            frame_bgra = row_view[:, :pixel_width].reshape((height, width, 4)).copy()
            self._window_id_capture_ok += 1
            return frame_bgra
        except Exception as e:
            self._window_id_capture_fail += 1
            self._log_capture_error(f"Window-id capture error: {e}")
            return None

    def _log_capture_error(self, message):
        """Rate-limited capture error logging."""
        now = time.time()
        if now - self._last_capture_error_log_ts < 2.0:
            return
        self._last_capture_error_log_ts = now
        print(
            "⚠️  Window-id capture fallback to ROI capture | "
            f"ok={self._window_id_capture_ok} fail={self._window_id_capture_fail} | {message}"
        )
    
    def map_roi_to_screen(self, x, y):
        """
        Map coordinates from ROI space to screen space
        
        Args:
            x, y: Coordinates in ROI (captured image)
        
        Returns:
            tuple: (screen_x, screen_y)
        """
        bounds = self.get_current_bounds()
        
        if bounds is None:
            # Fullscreen mode - no mapping needed
            return (x, y)
        
        return (bounds['x'] + x, bounds['y'] + y)


# Testing
if __name__ == "__main__":
    print("=" * 70)
    print("🔍 Window Capture Test")
    print("=" * 70)
    print("\nSearching for poker windows...")
    
    capture = WindowCapture()
    
    if capture.mode == 'fullscreen':
        print("\n❌ No Quartz support or no window found - would use fullscreen mode")
    else:
        bounds = capture.get_current_bounds()
        if bounds:
            print(f"\n✅ Window detected!")
            print(f"   Position: ({bounds['x']}, {bounds['y']})")
            print(f"   Size: {bounds['width']}x{bounds['height']}")
            
            roi = capture.get_roi_for_mss()
            print(f"\n📐 MSS ROI: {roi}")

            frame_bgra = capture.capture_window_bgra()
            if frame_bgra is not None:
                print(f"\n🪟 Window-id capture: OK ({frame_bgra.shape[1]}x{frame_bgra.shape[0]})")
            else:
                print("\n🪟 Window-id capture: unavailable/fallback")
            
            # Test coordinate mapping
            test_x, test_y = 100, 200
            screen_x, screen_y = capture.map_roi_to_screen(test_x, test_y)
            print(f"\n🗺️  Coordinate mapping test:")
            print(f"   ROI ({test_x}, {test_y}) → Screen ({screen_x}, {screen_y})")
        else:
            print("\n⚠️  Window not found")
    
    print("\n" + "=" * 70)
