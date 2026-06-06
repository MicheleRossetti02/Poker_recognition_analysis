"""
Main Coordinator - Poker Vision Assistant
==========================================
File principale che coordina tutti i moduli:
- Screen Capture
- Card Recognition (YOLO)
- OCR Game State Reader
- GUI Dashboard

Esegui con: python main.py
"""

import sys
import random
import time
import traceback
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, QMutex, QMutexLocker

# Import moduli locali
from screen_capture import ScreenRecorder, RETINA_SCALE
from card_recognizer import PokerBrain
from game_state_reader import TableReader, RegionConfig, combine_vision_data, GameState
from gui_dashboard import PokerDashboard


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# Intervallo tra frame in millisecondi (30 FPS = ~33ms)
FRAME_INTERVAL_MS = 100  # 10 FPS per non sovraccaricare

# Coordinate di cattura schermo (MODIFICA IN BASE ALLA TUA CONFIGURAZIONE)
# Queste sono coordinate logiche (prima della moltiplicazione Retina)
CAPTURE_CONFIG = {
    "top": 19,
    "left": 4,
    "width": 476,
    "height": 338
}

# Regione del Pot (CALIBRA con le tue coordinate di PokerStars)
POT_REGION = RegionConfig(
    top=200,
    left=380,
    width=140,
    height=35,
    name="Pot",
    scale=RETINA_SCALE
)

# Regione dello Stack Hero (CALIBRA)
STACK_REGION = RegionConfig(
    top=520,
    left=360,
    width=100,
    height=28,
    name="Hero Stack",
    scale=RETINA_SCALE
)

# Percorso al modello YOLO (usa "best.pt" dopo il training)
YOLO_MODEL_PATH = "yolov8n.pt"  # Modello generico per test


# ============================================================================
# WORKER THREAD
# ============================================================================

class VisionWorker(QThread):
    """
    Worker thread che esegue il loop di visione senza bloccare la GUI.
    
    Loop:
    1. Cattura frame
    2. Analizza carte (YOLO)
    3. Legge pot/stack (OCR)
    4. Calcola equity (placeholder)
    5. Emette segnale con dati
    """
    
    # Segnali
    data_ready = pyqtSignal(dict)  # Emesso quando i dati sono pronti
    status_update = pyqtSignal(str, bool)  # (messaggio, is_error)
    
    def __init__(
        self,
        capture_config: Dict[str, int],
        pot_region: Optional[RegionConfig] = None,
        stack_region: Optional[RegionConfig] = None,
        yolo_model_path: str = "yolov8n.pt",
        frame_interval_ms: int = 100
    ):
        super().__init__()
        
        self.capture_config = capture_config
        self.pot_region = pot_region
        self.stack_region = stack_region
        self.yolo_model_path = yolo_model_path
        self.frame_interval_ms = frame_interval_ms
        
        # Thread-safe flags with mutex protection
        self._mutex = QMutex()
        self._running = True
        self._paused = False
        
        # Adaptive frame rate tracking
        self._last_pot_size = 0.0
        self._last_pot_change_time = time.time()
        self._idle_threshold_seconds = 2.0  # Reduce FPS after 2s idle
        
        # Componenti (inizializzati nel thread)
        self.recorder: Optional[ScreenRecorder] = None
        self.brain: Optional[PokerBrain] = None
        self.reader: Optional[TableReader] = None
    
    def run(self):
        """Main loop del worker."""
        try:
            # Inizializza componenti nel thread
            self._initialize_components()
            
            # Loop principale (thread-safe con mutex)
            while True:
                # Check running flag atomically
                with QMutexLocker(self._mutex):
                    if not self._running:
                        break
                    is_paused = self._paused
                
                if is_paused:
                    time.sleep(0.1)
                    continue
                
                try:
                    # Esegui un ciclo di analisi
                    data = self._process_frame()
                    
                    if data:
                        self.data_ready.emit(data)
                    
                except Exception as e:
                    # Non crashare, logga e continua
                    error_msg = f"Frame error: {str(e)}"
                    self.status_update.emit(error_msg, True)
                    if self.recorder:
                        # Piccola pausa per evitare loop infinito di errori
                        time.sleep(0.5)
                
                # Intervallo tra frame (adattivo basato su attività pot)
                interval = self._get_adaptive_interval()
                time.sleep(interval / 1000.0)
        
        except Exception as e:
            self.status_update.emit(f"Critical error: {str(e)}", True)
            traceback.print_exc()
        
        finally:
            self._cleanup()
    
    def _initialize_components(self):
        """Inizializza i componenti di visione."""
        self.status_update.emit("Initializing screen capture...", False)
        
        try:
            # Screen Recorder
            self.recorder = ScreenRecorder(
                top=self.capture_config["top"],
                left=self.capture_config["left"],
                width=self.capture_config["width"],
                height=self.capture_config["height"]
            )
            self.status_update.emit("Screen capture ready", False)
        except Exception as e:
            self.status_update.emit(f"Screen capture error: {e}", True)
            raise
        
        try:
            # PokerBrain (YOLO)
            self.status_update.emit("Loading YOLO model...", False)
            self.brain = PokerBrain(
                model_path=self.yolo_model_path,
                verbose=False
            )
            self.status_update.emit("YOLO model loaded", False)
        except Exception as e:
            self.status_update.emit(f"YOLO error: {e}", True)
            # Continua senza YOLO
            self.brain = None
        
        try:
            # TableReader (OCR)
            self.status_update.emit("Loading OCR engine...", False)
            self.reader = TableReader(
                pot_region=self.pot_region,
                stack_region=self.stack_region,
                verbose=False
            )
            self.status_update.emit("OCR ready", False)
        except Exception as e:
            self.status_update.emit(f"OCR error: {e}", True)
            # Continua senza OCR
            self.reader = None
        
        self.status_update.emit("All systems ready!", False)
    
    def _process_frame(self) -> Optional[Dict[str, Any]]:
        """
        Processa un singolo frame e restituisce i dati.
        
        Returns:
            Dizionario con tutti i dati o None se errore
        """
        if not self.recorder:
            return None
        
        # 1. Cattura frame
        frame = self.recorder.grab_frame(color_format="BGR")
        
        # 2. Analizza carte (YOLO) + Position + Button
        cards_data = {"my_hand": [], "board": [], "game_stage": "Unknown"}
        hero_position = "Unknown"
        button_detected = False
        
        if self.brain:
            try:
                cards_result = self.brain.analyze_frame(frame, draw_boxes=False)
                cards_data = {
                    "my_hand": cards_result.get("my_hand", []),
                    "board": cards_result.get("board", []),
                    "game_stage": cards_result.get("game_stage", "Unknown")
                }
                hero_position = cards_result.get("hero_position", "Unknown")
                button_detected = cards_result.get("button_detected", False)
            except Exception:
                pass  # Ignora errori YOLO
        
        # 3. Leggi game state (OCR)
        game_state = GameState()
        if self.reader:
            try:
                game_state = self.reader.read_game_state(frame)
            except Exception:
                pass  # Ignora errori OCR
        
        # 4. Calcola Hand Evaluation (Treys)
        equity = None
        hand_description = "--"
        hand_rank = 0
        
        my_hand = cards_data.get("my_hand", [])
        board = cards_data.get("board", [])
        
        if self.brain and len(my_hand) == 2 and len(board) >= 3:
            try:
                eval_result = self.brain.calculate_equity(my_hand, board)
                if eval_result.get("valid", False):
                    hand_description = eval_result.get("description", "--")
                    hand_rank = eval_result.get("rank", 0)
                    # Usa percentile come equity
                    equity = eval_result.get("percentile", None)
            except Exception:
                pass  # Valutazione non disponibile
        
        # 5. Update adaptive frame rate tracking
        if game_state.pot_changed or game_state.pot_size != self._last_pot_size:
            self._last_pot_change_time = time.time()
            self._last_pot_size = game_state.pot_size
        
        # 6. Combina tutto
        result = {
            "cards": cards_data,
            "pot_size": game_state.pot_size,
            "hero_stack": game_state.hero_stack,
            "action_detected": game_state.action_detected,
            "pot_changed": game_state.pot_changed,
            "hero_position": hero_position,
            "button_detected": button_detected,
            "hand_description": hand_description,
            "hand_rank": hand_rank,
            "equity": equity
        }
        
        return result
    
    def _calculate_equity_dummy(
        self,
        my_hand: list,
        board: list
    ) -> Optional[float]:
        """
        Calcolo equity placeholder.
        
        TODO: Sostituire con calcolo reale usando Treys.
        Per ora restituisce valori semi-realistici basati sulla mano.
        
        Args:
            my_hand: Lista carte in mano
            board: Lista community cards
        
        Returns:
            Equity percentuale (0-100) o None
        """
        if not my_hand or len(my_hand) < 2:
            return None
        
        # Logica semplificata per demo
        # Premium hands hanno equity più alta
        premium_hands = ["AA", "KK", "QQ", "JJ", "AK", "AQ"]
        
        try:
            # Estrai i rank
            ranks = [c[0] for c in my_hand if len(c) >= 1]
            hand_str = "".join(sorted(ranks, reverse=True))
            
            # Check suited
            suits = [c[1] for c in my_hand if len(c) >= 2]
            is_suited = len(set(suits)) == 1 if len(suits) == 2 else False
            
            # Base equity
            if hand_str in ["AA"]:
                base_equity = 85
            elif hand_str in ["KK"]:
                base_equity = 82
            elif hand_str in ["QQ"]:
                base_equity = 79
            elif hand_str in ["JJ", "TT"]:
                base_equity = 75
            elif hand_str in ["AK"]:
                base_equity = 67
            elif hand_str in ["AQ", "AJ"]:
                base_equity = 65
            elif "A" in ranks:
                base_equity = 55
            elif "K" in ranks:
                base_equity = 50
            else:
                base_equity = 45
            
            # Bonus suited
            if is_suited:
                base_equity += 3
            
            # Aggiungi varianza random per demo
            equity = base_equity + random.uniform(-5, 5)
            
            return max(10, min(95, equity))
        
        except Exception:
            # Fallback random
            return random.uniform(40, 60)
    
    def _get_adaptive_interval(self) -> float:
        """
        Calcola intervallo adattivo con jitter anti-detection.
        
        LOGICA:
        - Pot cambiato recentemente (<2s): frame_interval_ms (10 FPS) - max responsiveness
        - Pot fermo (>2s): frame_interval_ms * 5 (2 FPS) - risparmio CPU ~60%
        - JITTER: ±10% randomness per mimare varianza umana (anti-pattern detection)
        
        Returns:
            Intervallo in millisecondi con randomness
        """
        import random
        
        current_time = time.time()
        time_since_change = current_time - self._last_pot_change_time
        
        if time_since_change < self._idle_threshold_seconds:
            # Attivo: velocità massima
            base_interval = self.frame_interval_ms
        else:
            # Idle: riduce FPS
            base_interval = self.frame_interval_ms * 5  # 100ms -> 500ms (10 FPS -> 2 FPS)
        
        # ADD JITTER: ±10% randomness (mimics human variance, evades pattern detection)
        jitter_range = base_interval * 0.1
        jitter = random.uniform(-jitter_range, jitter_range)
        final_interval = base_interval + jitter
        
        # Ensure minimum 50ms (avoid too fast)
        return max(50, final_interval)

    
    def stop(self):
        """Ferma il worker (thread-safe)."""
        with QMutexLocker(self._mutex):
            self._running = False
    
    def pause(self):
        """Mette in pausa il worker (thread-safe)."""
        with QMutexLocker(self._mutex):
            self._paused = True
    
    def resume(self):
        """Riprende il worker (thread-safe)."""
        with QMutexLocker(self._mutex):
            self._paused = False
    
    def _cleanup(self):
        """Pulisce le risorse."""
        if self.recorder:
            self.recorder.close()


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class PokerVisionApp:
    """
    Applicazione principale Poker Vision Assistant.
    
    Coordina GUI e Worker Thread.
    """
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.dashboard: Optional[PokerDashboard] = None
        self.worker: Optional[VisionWorker] = None
    
    def run(self):
        """Avvia l'applicazione."""
        print("=" * 60)
        print("♠ ♥ POKER VISION ASSISTANT ♦ ♣")
        print("=" * 60)
        print()
        
        # Crea dashboard
        self.dashboard = PokerDashboard()
        self.dashboard.show()
        
        # Crea e avvia worker
        self.worker = VisionWorker(
            capture_config=CAPTURE_CONFIG,
            pot_region=POT_REGION,
            stack_region=STACK_REGION,
            yolo_model_path=YOLO_MODEL_PATH,
            frame_interval_ms=FRAME_INTERVAL_MS
        )
        
        # Connetti segnali
        self.worker.data_ready.connect(self.dashboard.update_display)
        self.worker.status_update.connect(self.dashboard.set_status)
        
        # Avvia worker thread
        self.worker.start()
        
        # Esegui app
        result = self.app.exec()
        
        # Cleanup
        self.worker.stop()
        self.worker.wait(2000)  # Aspetta max 2 secondi
        
        return result


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Entry point principale."""
    app = PokerVisionApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()


# ============================================================================
# 📚 GUIDA CONFIGURAZIONE E CALIBRAZIONE
# ============================================================================
"""
================================================================================
                    GUIDA CONFIGURAZIONE POKER VISION
================================================================================

🔧 CONFIGURAZIONE INIZIALE
--------------------------

1. Posiziona la finestra di PokerStars sul monitor dove vuoi catturare.

2. Trova le coordinate della finestra:
   - Su Mac, usa Cmd+Shift+4 (screenshot) per vedere le coordinate
   - Oppure usa lo script di calibrazione:
   
   python -c "
   from screen_capture import find_screen_region_interactive
   coords = find_screen_region_interactive()
   print(f'Usa: top={coords[1]}, left={coords[0]}, width={coords[2]}, height={coords[3]}')
   "

3. Aggiorna CAPTURE_CONFIG in questo file con le tue coordinate.

4. Calibra le regioni OCR (pot e stack):
   
   python -c "
   from screen_capture import ScreenRecorder
   from game_state_reader import TableReader, RegionConfig
   import cv2
   
   # Cattura uno screenshot
   rec = ScreenRecorder(top=100, left=100, width=900, height=700)
   frame = rec.grab_frame()
   cv2.imwrite('calibration.png', frame)
   print('Screenshot salvato come calibration.png')
   print('Apri con Preview e annota le coordinate del pot e stack.')
   "

5. Aggiorna POT_REGION e STACK_REGION con le tue coordinate.


🚀 AVVIO APPLICAZIONE
---------------------

1. Assicurati che il venv sia attivo:
   source venv/bin/activate

2. Avvia l'applicazione:
   python main.py


📺 SECONDO MONITOR
------------------
Per posizionare la GUI sul secondo monitor:

1. Avvia l'app normalmente
2. Trascina la finestra sul secondo monitor
3. oppure modifica il codice:

   # In PokerDashboard.__init__, aggiungi:
   screens = QApplication.screens()
   if len(screens) > 1:
       screen = screens[1]  # Secondo monitor
       self.move(screen.geometry().x(), screen.geometry().y())


🔄 TRAINING MODELLO YOLO
------------------------
Dopo aver addestrato il modello con le tue carte:

1. Copia best.pt nella cartella del progetto
2. Modifica YOLO_MODEL_PATH:
   YOLO_MODEL_PATH = "best.pt"


⚠️ TROUBLESHOOTING
------------------

1. GUI bloccata / nessun dato:
   - Verifica che le coordinate di cattura siano corrette
   - Controlla i permessi di screen recording (Preferenze Sistema > Privacy)

2. OCR non legge i numeri:
   - Calibra le regioni usando calibrate_region()
   - Aumenta la dimensione delle regioni

3. YOLO non rileva carte:
   - Assicurati di usare un modello trainato sulle carte
   - yolov8n.pt è un modello generico (non per carte)

================================================================================
"""
