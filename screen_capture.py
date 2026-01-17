"""
Screen Capture Module for Computer Vision
==========================================
Modulo per catturare porzioni dello schermo ad alta velocità su macOS con Apple Silicon.
Ottimizzato per display Retina.
"""

import cv2
import numpy as np
import mss
import time
from typing import Tuple, Optional


# ============================================================================
# CONFIGURAZIONE RETINA
# ============================================================================
# Su Mac con display Retina, le coordinate logiche devono essere moltiplicate
# per questo fattore per ottenere le coordinate fisiche in pixel.
# - Imposta a 2 per display Retina standard
# - Imposta a 1 per display non-Retina o se usi coordinate già in pixel fisici
RETINA_SCALE = 2


class ScreenRecorder:
    """
    Classe per catturare una porzione specifica dello schermo.
    
    Attributes:
        top (int): Coordinata Y superiore (in punti logici)
        left (int): Coordinata X sinistra (in punti logici)
        width (int): Larghezza dell'area da catturare (in punti logici)
        height (int): Altezza dell'area da catturare (in punti logici)
        scale (int): Fattore di scala Retina
    
    Example:
        >>> recorder = ScreenRecorder(top=100, left=200, width=800, height=600)
        >>> recorder.show_preview()  # Per verificare le coordinate
        >>> frame = recorder.grab_frame()  # Cattura un singolo frame
    """
    
    def __init__(
        self,
        top: int,
        left: int,
        width: int,
        height: int,
        scale: int = RETINA_SCALE
    ):
        """
        Inizializza il ScreenRecorder con le coordinate dell'area da catturare.
        
        Args:
            top: Coordinata Y superiore (punti logici, come vedi su schermo)
            left: Coordinata X sinistra (punti logici, come vedi su schermo)
            width: Larghezza dell'area (punti logici)
            height: Altezza dell'area (punti logici)
            scale: Fattore di scala Retina (default: RETINA_SCALE)
        """
        self.top = top
        self.left = left
        self.width = width
        self.height = height
        self.scale = scale
        
        # Calcola le coordinate reali in pixel per mss
        self._monitor = {
            "top": self.top * self.scale,
            "left": self.left * self.scale,
            "width": self.width * self.scale,
            "height": self.height * self.scale,
        }
        
        # Screen capturer (lazy initialization)
        self._sct: Optional[mss.mss] = None
    
    @property
    def sct(self) -> mss.mss:
        """Lazy initialization del screen capturer."""
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct
    
    def grab_frame(self, color_format: str = "BGR") -> np.ndarray:
        """
        Cattura un singolo frame dalla regione specificata.
        
        Args:
            color_format: Formato colore output ("BGR" per OpenCV, "RGB" per altri usi)
        
        Returns:
            np.ndarray: Frame catturato nel formato colore specificato
        """
        # Cattura lo screenshot (formato BGRA)
        screenshot = self.sct.grab(self._monitor)
        
        # Converti in numpy array
        frame = np.array(screenshot)
        
        # mss restituisce BGRA, convertiamo nel formato richiesto
        if color_format.upper() == "BGR":
            # Rimuovi il canale alpha: BGRA -> BGR
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        elif color_format.upper() == "RGB":
            # Converti: BGRA -> RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
        elif color_format.upper() == "GRAY":
            # Converti in scala di grigi
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        else:
            raise ValueError(f"Formato colore non supportato: {color_format}. Usa 'BGR', 'RGB', o 'GRAY'")
        
        return frame
    
    def show_preview(
        self,
        window_name: str = "Screen Capture Preview",
        max_fps: int = 30,
        show_fps: bool = True,
        resize_factor: float = 1.0
    ) -> None:
        """
        Apre una finestra OpenCV che mostra in tempo reale cosa sta catturando il grabber.
        Utile per allineare e verificare le coordinate.
        
        Args:
            window_name: Nome della finestra OpenCV
            max_fps: FPS massimi per la preview (per limitare uso CPU)
            show_fps: Se True, mostra gli FPS correnti sulla preview
            resize_factor: Fattore di ridimensionamento della preview (es. 0.5 per metà dimensione)
        
        Controls:
            - Premi 'q' o ESC per chiudere la preview
            - Premi 's' per salvare uno screenshot
        """
        print(f"╔{'═' * 50}╗")
        print(f"║ {'SCREEN CAPTURE PREVIEW':^48} ║")
        print(f"╠{'═' * 50}╣")
        print(f"║ Coordinate logiche: ({self.left}, {self.top})".ljust(51) + "║")
        print(f"║ Dimensioni logiche: {self.width}x{self.height}".ljust(51) + "║")
        print(f"║ Scala Retina: {self.scale}x".ljust(51) + "║")
        print(f"║ Pixel reali: {self.width * self.scale}x{self.height * self.scale}".ljust(51) + "║")
        print(f"╠{'═' * 50}╣")
        print(f"║ Controlli:".ljust(51) + "║")
        print(f"║   [Q/ESC] Chiudi preview".ljust(51) + "║")
        print(f"║   [S] Salva screenshot".ljust(51) + "║")
        print(f"╚{'═' * 50}╝")
        print()
        
        # Variabili per calcolo FPS
        fps_counter = 0
        fps_start_time = time.time()
        current_fps = 0.0
        
        # Tempo minimo tra frame per rispettare max_fps
        min_frame_time = 1.0 / max_fps
        
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        try:
            while True:
                frame_start = time.time()
                
                # Cattura frame
                frame = self.grab_frame(color_format="BGR")
                
                # Ridimensiona se richiesto
                if resize_factor != 1.0:
                    new_width = int(frame.shape[1] * resize_factor)
                    new_height = int(frame.shape[0] * resize_factor)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                # Calcola e mostra FPS
                fps_counter += 1
                elapsed = time.time() - fps_start_time
                if elapsed >= 1.0:
                    current_fps = fps_counter / elapsed
                    fps_counter = 0
                    fps_start_time = time.time()
                
                if show_fps:
                    fps_text = f"FPS: {current_fps:.1f}"
                    cv2.putText(
                        frame, fps_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
                    )
                    
                    # Mostra anche le coordinate
                    coord_text = f"Region: ({self.left}, {self.top}) {self.width}x{self.height}"
                    cv2.putText(
                        frame, coord_text, (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1
                    )
                
                # Mostra il frame
                cv2.imshow(window_name, frame)
                
                # Gestisci input tastiera
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:  # q o ESC
                    print("Preview chiusa.")
                    break
                elif key == ord('s'):
                    # Salva screenshot
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"screenshot_{timestamp}.png"
                    cv2.imwrite(filename, frame)
                    print(f"Screenshot salvato: {filename}")
                
                # Limita FPS
                frame_time = time.time() - frame_start
                if frame_time < min_frame_time:
                    time.sleep(min_frame_time - frame_time)
                    
        finally:
            cv2.destroyAllWindows()
            self.close()
    
    def get_capture_info(self) -> dict:
        """
        Restituisce informazioni sulla configurazione corrente.
        
        Returns:
            dict: Dizionario con tutte le informazioni di configurazione
        """
        return {
            "logical_coordinates": {
                "top": self.top,
                "left": self.left,
                "width": self.width,
                "height": self.height,
            },
            "physical_pixels": {
                "top": self._monitor["top"],
                "left": self._monitor["left"],
                "width": self._monitor["width"],
                "height": self._monitor["height"],
            },
            "retina_scale": self.scale,
            "output_resolution": f"{self._monitor['width']}x{self._monitor['height']}",
        }
    
    def benchmark(self, duration_seconds: float = 5.0) -> dict:
        """
        Esegue un benchmark per misurare le prestazioni di cattura.
        
        Args:
            duration_seconds: Durata del benchmark in secondi
        
        Returns:
            dict: Statistiche del benchmark (fps, tempo medio per frame, etc.)
        """
        print(f"Esecuzione benchmark per {duration_seconds} secondi...")
        
        frame_times = []
        start_time = time.time()
        
        while (time.time() - start_time) < duration_seconds:
            frame_start = time.time()
            _ = self.grab_frame()
            frame_times.append(time.time() - frame_start)
        
        total_frames = len(frame_times)
        total_time = sum(frame_times)
        avg_fps = total_frames / total_time if total_time > 0 else 0
        avg_frame_time = (total_time / total_frames * 1000) if total_frames > 0 else 0
        
        results = {
            "total_frames": total_frames,
            "total_time_seconds": round(total_time, 2),
            "average_fps": round(avg_fps, 1),
            "average_frame_time_ms": round(avg_frame_time, 2),
            "min_frame_time_ms": round(min(frame_times) * 1000, 2) if frame_times else 0,
            "max_frame_time_ms": round(max(frame_times) * 1000, 2) if frame_times else 0,
        }
        
        print(f"\n📊 Risultati Benchmark:")
        print(f"   Frames catturati: {results['total_frames']}")
        print(f"   FPS medio: {results['average_fps']}")
        print(f"   Tempo medio per frame: {results['average_frame_time_ms']} ms")
        print(f"   Range: {results['min_frame_time_ms']} - {results['max_frame_time_ms']} ms")
        
        return results
    
    def close(self) -> None:
        """Chiude il screen capturer e rilascia le risorse."""
        if self._sct is not None:
            self._sct.close()
            self._sct = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
    
    def __repr__(self) -> str:
        return (
            f"ScreenRecorder(top={self.top}, left={self.left}, "
            f"width={self.width}, height={self.height}, scale={self.scale})"
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def find_screen_region_interactive() -> Tuple[int, int, int, int]:
    """
    Utility interattiva per trovare le coordinate di una regione dello schermo.
    Cattura l'intero schermo e permette di selezionare una regione con il mouse.
    
    Returns:
        Tuple[int, int, int, int]: (left, top, width, height) in coordinate logiche
    """
    print("Cattura dell'intero schermo in corso...")
    print("Seleziona l'area di interesse con il mouse, poi premi ENTER o SPACE.")
    print("Premi 'c' per annullare.")
    
    with mss.mss() as sct:
        # Cattura l'intero schermo primario
        monitor = sct.monitors[1]  # Monitor primario
        screenshot = sct.grab(monitor)
        frame = np.array(screenshot)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    # Ridimensiona per la visualizzazione se troppo grande
    scale_display = 1.0
    max_display_width = 1920
    if frame.shape[1] > max_display_width:
        scale_display = max_display_width / frame.shape[1]
        frame = cv2.resize(frame, None, fx=scale_display, fy=scale_display)
    
    # Seleziona ROI
    roi = cv2.selectROI("Seleziona Region of Interest", frame, fromCenter=False)
    cv2.destroyAllWindows()
    
    if roi[2] == 0 or roi[3] == 0:
        print("Selezione annullata.")
        return (0, 0, 0, 0)
    
    # Converti le coordinate considerando il ridimensionamento e la scala Retina
    left = int(roi[0] / scale_display / RETINA_SCALE)
    top = int(roi[1] / scale_display / RETINA_SCALE)
    width = int(roi[2] / scale_display / RETINA_SCALE)
    height = int(roi[3] / scale_display / RETINA_SCALE)
    
    print(f"\n✅ Coordinate selezionate (logiche):")
    print(f"   top={top}, left={left}, width={width}, height={height}")
    print(f"\nUsa queste coordinate per creare il ScreenRecorder:")
    print(f"   recorder = ScreenRecorder(top={top}, left={left}, width={width}, height={height})")
    
    return (left, top, width, height)


# ============================================================================
# MAIN - Esempio d'uso
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SCREEN CAPTURE MODULE - Test")
    print("=" * 60)
    
    # Esempio: cattura un'area di 400x300 a partire da (100, 100)
    # Modifica queste coordinate in base alle tue esigenze
    TEST_TOP = 100
    TEST_LEFT = 100
    TEST_WIDTH = 400
    TEST_HEIGHT = 300
    
    print(f"\nCreazione ScreenRecorder...")
    print(f"  Coordinate logiche: top={TEST_TOP}, left={TEST_LEFT}")
    print(f"  Dimensioni logiche: {TEST_WIDTH}x{TEST_HEIGHT}")
    print(f"  Scala Retina: {RETINA_SCALE}x")
    
    # Crea il recorder
    recorder = ScreenRecorder(
        top=TEST_TOP,
        left=TEST_LEFT,
        width=TEST_WIDTH,
        height=TEST_HEIGHT
    )
    
    # Mostra info
    print(f"\n📋 Info configurazione:")
    info = recorder.get_capture_info()
    print(f"   Pixel reali: {info['output_resolution']}")
    
    # Esegui benchmark veloce
    print()
    recorder.benchmark(duration_seconds=3.0)
    
    # Avvia preview
    print("\n🖥️  Avvio preview... (premi 'q' per chiudere)")
    recorder.show_preview(show_fps=True, resize_factor=1.0)
    
    print("\nTest completato!")
