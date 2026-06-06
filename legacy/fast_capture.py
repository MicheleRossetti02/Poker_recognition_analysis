#!/usr/bin/env python3
"""
Fast Image Capture - Data Factory Hybrid Edition
=================================================
Sistema professionale con motion detection duale:
- MSE (Mean Squared Error)
- Percent-based (cv2.absdiff + binary threshold)

FEATURES:
- Dual motion detection selezionabile via CLI
- Session management automatico
- Metadata JSON completo
- UI preview con statistiche real-time
- Ottimizzazione CPU (resize 200x150)

USO:
    # Default: percent-based method
    python fast_capture.py --threshold 5.0 --interval 2
    
    # MSE method
    python fast_capture.py --motion-method mse --threshold 15 --interval 2
    
    # Manual mode
    python fast_capture.py --manual

OPZIONI:
    --motion-method [percent|mse]  Metodo rilevamento (default: percent)
    --threshold N                  Soglia movimento (default: 5.0 per percent, 15 per mse)
    --interval N                   Intervallo secondi (default: 2)
    --output DIR                   Directory output (default: dataset/raw)
    --version N                    Versione dataset (default: 4)
    --manual                       Modalità manuale (solo SPAZIO)
"""

import cv2
import mss
import numpy as np
import time
import os
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# ============================================================================
# CONFIGURAZIONE CATTURA
# ============================================================================
CAPTURE_TOP = 19
CAPTURE_LEFT = 4
CAPTURE_WIDTH = 476
CAPTURE_HEIGHT = 338
RETINA_SCALE = 2

# ============================================================================
# CONFIGURAZIONE MOTION DETECTION
# ============================================================================
DEFAULT_THRESHOLD_PERCENT = 5.0   # % pixel cambiati per percent method
DEFAULT_THRESHOLD_MSE = 15.0      # Errore quadratico medio per MSE method
DEFAULT_DATASET_VERSION = 4
DEFAULT_BASE_OUTPUT = "dataset/raw"

# Resize per ottimizzazione CPU
MOTION_RESIZE_WIDTH = 200
MOTION_RESIZE_HEIGHT = 150


class MotionDetector:
    """
    Rilevatore movimento con metodi duali: MSE e Percent-based.
    Ottimizzato con resize per performance CPU.
    """
    
    def __init__(self, method: str = "percent", threshold: float = 5.0):
        """
        Inizializza motion detector.
        
        Args:
            method: "percent" o "mse"
            threshold: Soglia per rilevamento (% per percent, valore MSE per mse)
        """
        self.method = method.lower()
        self.threshold = threshold
        self.previous_frame: Optional[np.ndarray] = None
        
        if self.method not in ["percent", "mse"]:
            raise ValueError(f"Method deve essere 'percent' o 'mse', non '{method}'")
    
    def _resize_for_detection(self, frame: np.ndarray) -> np.ndarray:
        """Resize frame per ottimizzazione CPU."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (MOTION_RESIZE_WIDTH, MOTION_RESIZE_HEIGHT))
        return resized
    
    def _detect_mse(self, current: np.ndarray, previous: np.ndarray) -> Tuple[bool, float]:
        """
        Rilevamento basato su MSE (Mean Squared Error).
        
        Args:
            current: Frame corrente (grayscale resized)
            previous: Frame precedente (grayscale resized)
        
        Returns:
            (movimento_rilevato, valore_mse)
        """
        # Calcola errore quadratico medio
        err = np.sum((current.astype("float") - previous.astype("float")) ** 2)
        mse = err / float(current.shape[0] * current.shape[1])
        
        motion_detected = mse > self.threshold
        return motion_detected, mse
    
    def _detect_percent(self, current: np.ndarray, previous: np.ndarray) -> Tuple[bool, float]:
        """
        Rilevamento basato su percentuale pixel cambiati.
        Usa cv2.absdiff + binary threshold.
        
        Args:
            current: Frame corrente (grayscale resized)
            previous: Frame precedente (grayscale resized)
        
        Returns:
            (movimento_rilevato, percentuale_cambiamento)
        """
        # Differenza assoluta
        diff = cv2.absdiff(previous, current)
        
        # Binary threshold a 25 (robusto per cambiamenti significativi)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        
        # Conta pixel cambiati
        changed_pixels = cv2.countNonZero(thresh)
        total_pixels = thresh.size
        change_percent = (changed_pixels / total_pixels) * 100
        
        motion_detected = change_percent >= self.threshold
        return motion_detected, change_percent
    
    def detect_motion(self, frame: np.ndarray) -> Tuple[bool, float, str]:
        """
        Rileva movimento nel frame corrente.
        
        Args:
            frame: Frame BGR corrente (full resolution)
        
        Returns:
            Tuple (movimento_rilevato, valore_metrica, label_metrica)
        """
        # Resize per performance
        processed = self._resize_for_detection(frame)
        
        # Primo frame: salva e considera movimento
        if self.previous_frame is None:
            self.previous_frame = processed.copy()
            return True, 100.0, "First Frame"
        
        # Applica metodo selezionato
        if self.method == "mse":
            motion_detected, value = self._detect_mse(processed, self.previous_frame)
            label = f"MSE: {value:.1f}"
        else:  # percent
            motion_detected, value = self._detect_percent(processed, self.previous_frame)
            label = f"Change: {value:.1f}%"
        
        # Aggiorna frame precedente solo se c'è stato movimento
        if motion_detected:
            self.previous_frame = processed.copy()
        
        return motion_detected, value, label


class SessionManager:
    """Gestisce sessione di cattura con metadata e statistiche."""
    
    def __init__(self, base_dir: str, version: int, motion_method: str, 
                 motion_threshold: float, capture_config: Dict[str, int]):
        """
        Inizializza sessione.
        
        Args:
            base_dir: Directory base
            version: Versione dataset
            motion_method: Metodo motion detection usato
            motion_threshold: Soglia configurata
            capture_config: Coordinate cattura
        """
        self.base_dir = Path(base_dir)
        self.version = version
        self.motion_method = motion_method
        self.motion_threshold = motion_threshold
        self.capture_config = capture_config
        
        # Session ID con timestamp completo
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.base_dir / f"session_{self.session_id}"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # Statistiche
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.frames_analyzed = 0
        self.images_saved = 0
        self.motion_detected_count = 0
        self.image_counter = 1
        
        # Calcola risoluzione effettiva
        width = capture_config['width'] * capture_config.get('scale', 2)
        height = capture_config['height'] * capture_config.get('scale', 2)
        self.resolution = (width, height)
        
        print(f"\n📁 Sessione: {self.session_dir.name}")
    
    def get_next_filename(self) -> str:
        """
        Genera filename: poker_{width}x{height}_v{version}_{timestamp}.jpg
        
        Returns:
            Nome file
        """
        width, height = self.resolution
        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]  # Include millisec
        filename = f"poker_{width}x{height}_v{self.version}_{timestamp}.jpg"
        self.image_counter += 1
        return filename
    
    def get_filepath(self) -> Path:
        """Restituisce path completo per prossima immagine."""
        return self.session_dir / self.get_next_filename()
    
    def record_frame_analyzed(self):
        """Incrementa contatore frame analizzati."""
        self.frames_analyzed += 1
    
    def record_motion_detected(self):
        """Incrementa contatore motion rilevato."""
        self.motion_detected_count += 1
    
    def record_image_saved(self):
        """Incrementa contatore immagini salvate."""
        self.images_saved += 1
    
    def finalize(self) -> Dict[str, Any]:
        """
        Finalizza sessione e salva session_info.json.
        
        Returns:
            Dizionario metadata
        """
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        
        save_rate = (self.images_saved / self.frames_analyzed * 100 
                    if self.frames_analyzed > 0 else 0)
        
        metadata = {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "frames_analyzed": self.frames_analyzed,
            "motion_detected_count": self.motion_detected_count,
            "images_saved": self.images_saved,
            "save_rate_percent": round(save_rate, 2),
            "dataset_version": self.version,
            "motion_detection": {
                "method": self.motion_method,
                "threshold": self.motion_threshold,
                "resize_optimization": f"{MOTION_RESIZE_WIDTH}x{MOTION_RESIZE_HEIGHT}"
            },
            "resolution": f"{self.resolution[0]}x{self.resolution[1]}",
            "capture_config": self.capture_config
        }
        
        # Salva session_info.json
        info_path = self.session_dir / "session_info.json"
        with open(info_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return metadata


def main():
    parser = argparse.ArgumentParser(
        description="Data Factory Hybrid - Motion Detection Duale",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  %(prog)s --motion-method percent --threshold 5.0
  %(prog)s --motion-method mse --threshold 15
  %(prog)s --manual
        """
    )
    
    parser.add_argument("--motion-method", "-m", 
                       choices=["percent", "mse"], 
                       default="percent",
                       help="Metodo motion detection (default: percent)")
    parser.add_argument("--threshold", "-t", type=float,
                       help="Soglia movimento (default: auto per metodo)")
    parser.add_argument("--interval", "-i", type=float, default=2.0,
                       help="Intervallo catture in secondi (default: 2)")
    parser.add_argument("--output", "-o", default=DEFAULT_BASE_OUTPUT,
                       help=f"Directory output (default: {DEFAULT_BASE_OUTPUT})")
    parser.add_argument("--version", "-v", type=int, default=DEFAULT_DATASET_VERSION,
                       help=f"Versione dataset (default: {DEFAULT_DATASET_VERSION})")
    parser.add_argument("--manual", action="store_true",
                       help="Modalità manuale (solo SPAZIO)")
    
    args = parser.parse_args()
    
    # Auto-detect threshold se non specificato
    if args.threshold is None:
        args.threshold = (DEFAULT_THRESHOLD_MSE if args.motion_method == "mse" 
                         else DEFAULT_THRESHOLD_PERCENT)
    
    # Monitor config
    monitor = {
        "top": CAPTURE_TOP * RETINA_SCALE,
        "left": CAPTURE_LEFT * RETINA_SCALE,
        "width": CAPTURE_WIDTH * RETINA_SCALE,
        "height": CAPTURE_HEIGHT * RETINA_SCALE,
    }
    
    capture_config = {
        "top": CAPTURE_TOP,
        "left": CAPTURE_LEFT,
        "width": CAPTURE_WIDTH,
        "height": CAPTURE_HEIGHT,
        "scale": RETINA_SCALE
    }
    
    # Inizializza componenti
    session = SessionManager(
        base_dir=args.output,
        version=args.version,
        motion_method=args.motion_method,
        motion_threshold=args.threshold,
        capture_config=capture_config
    )
    
    motion_detector = MotionDetector(
        method=args.motion_method,
        threshold=args.threshold
    )
    
    # Banner
    print("=" * 70)
    print("🏭 DATA FACTORY HYBRID - Motion Detection Duale")
    print("=" * 70)
    print(f"\n⚙️  Configurazione:")
    print(f"   Metodo: {args.motion_method.upper()}")
    print(f"   Soglia: {args.threshold}")
    print(f"   Risoluzione: {session.resolution[0]}x{session.resolution[1]}")
    print(f"   Ottimizzazione CPU: {MOTION_RESIZE_WIDTH}x{MOTION_RESIZE_HEIGHT}")
    print(f"   Versione: v{args.version}")
    
    if args.manual:
        print(f"   Modalità: MANUALE")
    else:
        print(f"   Modalità: AUTO ({args.interval}s)")
    
    print(f"\n🎮 Controlli:")
    print(f"   [SPAZIO] = Cattura manuale")
    print(f"   [P] = Pausa/Riprendi")
    print(f"   [Q] = Esci")
    print("\n" + "=" * 70 + "\n")
    
    last_capture = 0
    paused = args.manual
    
    with mss.mss() as sct:
        cv2.namedWindow("Data Factory Hybrid", cv2.WINDOW_NORMAL)
        
        while True:
            current_time = time.time()
            session.record_frame_analyzed()
            
            # Cattura frame
            screenshot = sct.grab(monitor)
            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            # Rileva movimento
            motion_detected, metric_value, metric_label = motion_detector.detect_motion(frame)
            if motion_detected:
                session.record_motion_detected()
            
            # Auto-capture con motion
            should_capture = False
            if not paused and not args.manual:
                if current_time - last_capture >= args.interval:
                    if motion_detected:
                        should_capture = True
            
            # Prepara display
            display = cv2.resize(frame, (CAPTURE_WIDTH, CAPTURE_HEIGHT))
            
            # Overlay UI
            if paused:
                status = "⏸️ PAUSA"
                status_color = (100, 100, 100)
            elif args.manual:
                status = "📸 MANUALE"
                status_color = (255, 255, 0)
            else:
                status = f"🔴 REC ({args.interval}s)"
                status_color = (0, 0, 255)
            
            cv2.putText(display, status, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            
            # Statistiche
            save_rate = (session.images_saved / session.frames_analyzed * 100 
                        if session.frames_analyzed > 0 else 0)
            
            cv2.putText(display, f"Salvate: {session.images_saved} ({save_rate:.1f}%)",
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Motion metric (REAL-TIME)
            motion_color = (0, 255, 0) if motion_detected else (0, 0, 255)
            motion_icon = "✓" if motion_detected else "✗"
            cv2.putText(display, f"{metric_label} {motion_icon}",
                       (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, motion_color, 2)
            
            # Method indicator
            method_text = f"Method: {args.motion_method.upper()}"
            cv2.putText(display, method_text, (10, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            
            # Countdown
            if not paused and not args.manual:
                time_to_next = args.interval - (current_time - last_capture)
                if time_to_next > 0:
                    cv2.putText(display, f"Next: {time_to_next:.1f}s",
                               (10, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            
            cv2.imshow("Data Factory Hybrid", display)
            
            # Auto-capture
            if should_capture:
                filepath = session.get_filepath()
                cv2.imwrite(str(filepath), frame)
                session.record_image_saved()
                last_capture = current_time
                print(f"📸 [{session.images_saved}] {filepath.name} ({metric_label})")
            
            # Input tastiera
            key = cv2.waitKey(30) & 0xFF
            
            if key == ord(' '):  # Cattura manuale
                filepath = session.get_filepath()
                cv2.imwrite(str(filepath), frame)
                session.record_image_saved()
                print(f"📸 [MANUAL {session.images_saved}] {filepath.name}")
            
            elif key == ord('p'):  # Pausa
                paused = not paused
                state = "⏸️ PAUSA" if paused else "▶️ RIPRESO"
                print(f"\n{state}\n")
                last_capture = current_time
            
            elif key == ord('q') or key == 27:  # Esci
                break
    
    cv2.destroyAllWindows()
    
    # Finalizza sessione
    metadata = session.finalize()
    
    # Report finale
    print("\n" + "=" * 70)
    print("✅ SESSIONE COMPLETATA")
    print("=" * 70)
    print(f"\n📊 Statistiche:")
    print(f"   Frame analizzati: {metadata['frames_analyzed']}")
    print(f"   Motion rilevato: {metadata['motion_detected_count']}")
    print(f"   Immagini salvate: {metadata['images_saved']}")
    print(f"   Save rate: {metadata['save_rate_percent']:.2f}%")
    print(f"   Durata: {metadata['duration_seconds']:.0f}s")
    print(f"   Metodo: {metadata['motion_detection']['method'].upper()}")
    print(f"   Soglia: {metadata['motion_detection']['threshold']}")
    print(f"\n📁 Directory: {session.session_dir}/")
    print(f"📄 Metadata: session_info.json")
    print("\n" + "=" * 70)
    print("📝 Prossimi passi:")
    print(f"   1. Verifica: ls {session.session_dir}/")
    print(f"   2. Upload: python upload_to_roboflow.py --session {session.session_id}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
