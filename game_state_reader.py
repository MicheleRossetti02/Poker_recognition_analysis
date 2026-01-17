"""
Game State Reader Module - OCR for Poker Tables
=================================================
Modulo per leggere pot size, stack dei giocatori e altre informazioni
numeriche dal tavolo da poker usando EasyOCR.
"""

import cv2
import numpy as np
import easyocr
import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# Lingue per OCR (inglese per numeri/simboli standard)
OCR_LANGUAGES = ['en']

# Abilita GPU/MPS su Mac Silicon (True per performance migliori)
USE_GPU = True


class ActionType(Enum):
    """Tipi di azione rilevabili dal cambiamento del pot."""
    NO_ACTION = "No Action"
    CHECK = "Check"
    BET_RAISE = "Bet/Raise"
    CALL = "Call"
    NEW_HAND = "New Hand"
    UNKNOWN = "Unknown"


@dataclass
class RegionConfig:
    """Configurazione per una regione dello schermo da leggere con OCR."""
    top: int
    left: int
    width: int
    height: int
    name: str = "region"
    scale: int = 2  # Moltiplicatore Retina
    
    def get_crop_coords(self) -> Tuple[int, int, int, int]:
        """Restituisce le coordinate di crop in pixel reali."""
        return (
            self.left * self.scale,
            self.top * self.scale,
            (self.left + self.width) * self.scale,
            (self.top + self.height) * self.scale
        )


@dataclass
class GameState:
    """Stato corrente del gioco rilevato."""
    pot_size: float = 0.0
    hero_stack: float = 0.0
    action_detected: str = ActionType.NO_ACTION.value
    pot_changed: bool = False
    raw_pot_text: str = ""
    raw_stack_text: str = ""
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pot_size": self.pot_size,
            "hero_stack": self.hero_stack,
            "action_detected": self.action_detected,
            "pot_changed": self.pot_changed,
            "ocr_confidence": round(self.confidence, 2)
        }


class TableReader:
    """
    Classe per leggere informazioni numeriche dal tavolo da poker usando OCR.
    
    Legge pot size, stack dei giocatori, e rileva le azioni in base
    al cambiamento del pot.
    
    Attributes:
        pot_region: Regione dello schermo dove si trova il pot
        stack_region: Regione dello schermo dove si trova lo stack dell'hero
        previous_pot: Valore del pot precedente per rilevare azioni
    
    Example:
        >>> reader = TableReader(
        ...     pot_region=RegionConfig(top=200, left=400, width=100, height=30),
        ...     stack_region=RegionConfig(top=500, left=350, width=80, height=25)
        ... )
        >>> state = reader.read_game_state(frame)
        >>> print(f"Pot: ${state.pot_size}, Action: {state.action_detected}")
    """
    
    def __init__(
        self,
        pot_region: Optional[RegionConfig] = None,
        stack_region: Optional[RegionConfig] = None,
        languages: List[str] = OCR_LANGUAGES,
        use_gpu: bool = USE_GPU,
        verbose: bool = False
    ):
        """
        Inizializza il TableReader con le regioni configurate.
        
        Args:
            pot_region: Configurazione regione pot (o None per disabilitare)
            stack_region: Configurazione regione stack hero (o None per disabilitare)
            languages: Lingue per EasyOCR
            use_gpu: Se True, usa GPU/MPS per accelerazione
            verbose: Se True, stampa log dettagliati
        """
        self.pot_region = pot_region
        self.stack_region = stack_region
        self.verbose = verbose
        
        # Stato precedente per rilevare cambiamenti
        self._previous_pot: float = 0.0
        self._previous_stack: float = 0.0
        
        print(f"📖 Inizializzazione TableReader (OCR)...")
        print(f"   GPU/MPS: {'Abilitato' if use_gpu else 'Disabilitato'}")
        
        # Inizializza EasyOCR
        try:
            self.reader = easyocr.Reader(
                languages,
                gpu=use_gpu,
                verbose=False
            )
            print(f"   ✅ EasyOCR caricato con successo!")
        except Exception as e:
            print(f"   ❌ Errore caricamento EasyOCR: {e}")
            raise
        
        if pot_region:
            print(f"   Regione Pot: ({pot_region.left}, {pot_region.top}) {pot_region.width}x{pot_region.height}")
        if stack_region:
            print(f"   Regione Stack: ({stack_region.left}, {stack_region.top}) {stack_region.width}x{stack_region.height}")
    
    def read_pot_size(self, frame: np.ndarray) -> Tuple[float, str, float]:
        """
        Legge il valore del pot dall'area configurata.
        
        Args:
            frame: Frame BGR completo (formato OpenCV)
        
        Returns:
            Tuple (valore_numerico, testo_grezzo, confidenza)
        """
        if self.pot_region is None:
            return 0.0, "", 0.0
        
        return self._read_number_from_region(frame, self.pot_region)
    
    def read_hero_stack(self, frame: np.ndarray) -> Tuple[float, str, float]:
        """
        Legge lo stack dell'Hero dall'area configurata.
        
        Args:
            frame: Frame BGR completo (formato OpenCV)
        
        Returns:
            Tuple (valore_numerico, testo_grezzo, confidenza)
        """
        if self.stack_region is None:
            return 0.0, "", 0.0
        
        return self._read_number_from_region(frame, self.stack_region)
    
    def _read_number_from_region(
        self,
        frame: np.ndarray,
        region: RegionConfig
    ) -> Tuple[float, str, float]:
        """
        Legge un numero da una regione specifica dello schermo.
        
        Args:
            frame: Frame BGR completo
            region: Configurazione della regione
        
        Returns:
            Tuple (valore_numerico, testo_grezzo, confidenza)
        """
        # Crop della regione
        x1, y1, x2, y2 = region.get_crop_coords()
        
        # Verifica che le coordinate siano valide
        h, w = frame.shape[:2]
        x1 = max(0, min(x1, w))
        x2 = max(0, min(x2, w))
        y1 = max(0, min(y1, h))
        y2 = max(0, min(y2, h))
        
        if x2 <= x1 or y2 <= y1:
            return 0.0, "", 0.0
        
        cropped = frame[y1:y2, x1:x2]
        
        # Preprocessing per migliorare OCR
        processed = self._preprocess_for_ocr(cropped)
        
        # Esegui OCR
        try:
            results = self.reader.readtext(processed, detail=1)
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️ Errore OCR: {e}")
            return 0.0, "", 0.0
        
        if not results:
            return 0.0, "", 0.0
        
        # Combina tutti i testi rilevati
        raw_text = " ".join([r[1] for r in results])
        avg_confidence = sum(r[2] for r in results) / len(results)
        
        # Estrai il numero
        numeric_value = self._extract_number(raw_text)
        
        if self.verbose:
            print(f"   OCR {region.name}: '{raw_text}' -> {numeric_value} (conf: {avg_confidence:.2f})")
        
        return numeric_value, raw_text, avg_confidence
    
    def _preprocess_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocessa l'immagine per migliorare l'accuratezza OCR.
        
        Args:
            image: Immagine BGR
        
        Returns:
            Immagine preprocessata in scala di grigi
        """
        # Converti in scala di grigi
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Upscale 2x per numeri piccoli
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        # Aumenta il contrasto con CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        
        # Threshold adattivo per binarizzare
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        # Inverti se lo sfondo è scuro (numeri chiari su sfondo scuro)
        # Controlla la luminosità media
        if np.mean(gray) < 127:
            binary = cv2.bitwise_not(binary)
        
        return binary
    
    def _extract_number(self, text: str) -> float:
        """
        Estrae un valore numerico da una stringa OCR.
        
        Gestisce formati comuni:
        - "$1,234.56" -> 1234.56
        - "1.5k" -> 1500
        - "€ 100" -> 100
        - "BB 25" -> 25
        
        Args:
            text: Testo grezzo da OCR
        
        Returns:
            Valore numerico estratto
        """
        if not text:
            return 0.0
        
        # Rimuovi caratteri non numerici tranne punto, virgola, k/K/m/M
        cleaned = text.upper().strip()
        
        # Rimuovi simboli di valuta e spazi
        cleaned = re.sub(r'[$€£¥BB\s]', '', cleaned)
        
        # Gestisci notazione k/m (1.5k = 1500)
        multiplier = 1.0
        if 'K' in cleaned:
            multiplier = 1000.0
            cleaned = cleaned.replace('K', '')
        elif 'M' in cleaned:
            multiplier = 1000000.0
            cleaned = cleaned.replace('M', '')
        
        # Rimuovi virgole usate come separatori migliaia
        cleaned = cleaned.replace(',', '')
        
        # Estrai il primo numero valido
        match = re.search(r'[\d.]+', cleaned)
        if match:
            try:
                value = float(match.group()) * multiplier
                return round(value, 2)
            except ValueError:
                pass
        
        return 0.0
    
    def read_game_state(self, frame: np.ndarray) -> GameState:
        """
        Legge lo stato completo del gioco dal frame.
        
        Args:
            frame: Frame BGR completo
        
        Returns:
            GameState con pot, stack, e azione rilevata
        """
        state = GameState()
        
        # Leggi pot
        pot_value, pot_text, pot_conf = self.read_pot_size(frame)
        state.pot_size = pot_value
        state.raw_pot_text = pot_text
        
        # Leggi stack hero
        stack_value, stack_text, stack_conf = self.read_hero_stack(frame)
        state.hero_stack = stack_value
        state.raw_stack_text = stack_text
        
        # Confidenza media
        if pot_conf > 0 or stack_conf > 0:
            state.confidence = (pot_conf + stack_conf) / 2 if stack_conf > 0 else pot_conf
        
        # Rileva azione basata sul cambiamento del pot
        action, pot_changed = self._detect_action(pot_value)
        state.action_detected = action.value
        state.pot_changed = pot_changed
        
        # Aggiorna stato precedente
        self._previous_pot = pot_value
        self._previous_stack = stack_value
        
        if self.verbose:
            print(f"\n🎮 Game State:")
            print(f"   Pot: ${state.pot_size} (prev: ${self._previous_pot})")
            print(f"   Stack: ${state.hero_stack}")
            print(f"   Action: {state.action_detected}")
        
        return state
    
    def _detect_action(self, current_pot: float) -> Tuple[ActionType, bool]:
        """
        Rileva l'azione in base al cambiamento del pot.
        
        Logica:
        - Pot aumentato significativamente: Bet/Raise
        - Pot leggermente aumentato: Call
        - Pot invariato: Check/No Action
        - Pot diminuito drasticamente: Nuova mano
        
        Args:
            current_pot: Valore corrente del pot
        
        Returns:
            Tuple (ActionType, pot_changed)
        """
        prev_pot = self._previous_pot
        
        # Prima lettura - nessun riferimento
        if prev_pot == 0 and current_pot > 0:
            return ActionType.NO_ACTION, False
        
        # Calcola la differenza
        diff = current_pot - prev_pot
        
        # Pot invariato
        if abs(diff) < 0.01:
            return ActionType.CHECK, False
        
        # Pot aumentato
        if diff > 0:
            # Se l'aumento è significativo (> 20% del pot precedente), è un raise
            if prev_pot > 0 and diff > prev_pot * 0.2:
                return ActionType.BET_RAISE, True
            else:
                return ActionType.CALL, True
        
        # Pot diminuito significativamente = nuova mano
        if current_pot < prev_pot * 0.5:
            return ActionType.NEW_HAND, True
        
        return ActionType.UNKNOWN, True
    
    def reset_state(self) -> None:
        """Resetta lo stato precedente (per nuova mano o sessione)."""
        self._previous_pot = 0.0
        self._previous_stack = 0.0
        if self.verbose:
            print("   🔄 Stato resettato")
    
    def calibrate_region(
        self,
        frame: np.ndarray,
        region: RegionConfig,
        window_name: str = "Calibration"
    ) -> None:
        """
        Mostra visivamente la regione per calibrazione.
        Utile per verificare che le coordinate siano corrette.
        
        Args:
            frame: Frame BGR completo
            region: Regione da visualizzare
            window_name: Nome della finestra
        """
        display = frame.copy()
        x1, y1, x2, y2 = region.get_crop_coords()
        
        # Disegna rettangolo
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(display, region.name, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Leggi il valore
        value, text, conf = self._read_number_from_region(frame, region)
        info = f"OCR: '{text}' -> {value} (conf: {conf:.2f})"
        cv2.putText(display, info, (x1, y2 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        
        # Mostra crop ingrandito
        cropped = frame[y1:y2, x1:x2]
        if cropped.size > 0:
            h, w = cropped.shape[:2]
            scale = max(1, 200 // max(h, w))
            enlarged = cv2.resize(cropped, (w * scale, h * scale))
            
            # Posiziona in alto a sinistra
            display[10:10 + enlarged.shape[0], 10:10 + enlarged.shape[1]] = enlarged
        
        cv2.imshow(window_name, display)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


# ============================================================================
# FUNZIONE COMBINATA: Cards + OCR
# ============================================================================

def combine_vision_data(
    cards_result: Dict[str, Any],
    game_state: GameState
) -> Dict[str, Any]:
    """
    Combina i risultati di YOLO (carte) con OCR (pot/stack).
    
    Args:
        cards_result: Output da PokerBrain.analyze_frame()
        game_state: Output da TableReader.read_game_state()
    
    Returns:
        Dizionario JSON combinato
    """
    return {
        "cards": {
            "my_hand": cards_result.get("my_hand", []),
            "board": cards_result.get("board", []),
            "game_stage": cards_result.get("game_stage", "Unknown")
        },
        "pot_size": game_state.pot_size,
        "hero_stack": game_state.hero_stack,
        "action_detected": game_state.action_detected,
        "pot_changed": game_state.pot_changed,
        "ocr_confidence": round(game_state.confidence, 2)
    }


# ============================================================================
# MAIN - Test e Demo
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("TABLE READER - OCR Module Test")
    print("=" * 70)
    
    # Test caricamento EasyOCR
    print("\n🧪 Test caricamento EasyOCR...")
    
    try:
        # Crea reader senza regioni (solo test caricamento)
        reader = TableReader(verbose=True)
        print("\n✅ TableReader inizializzato con successo!")
        
        # Test estrazione numeri
        print("\n📝 Test estrazione numeri:")
        test_cases = [
            "$1,234.56",
            "€ 100",
            "1.5k",
            "BB 25",
            "Pot: 500",
            "$2.5M"
        ]
        for text in test_cases:
            result = reader._extract_number(text)
            print(f"   '{text}' -> {result}")
        
    except Exception as e:
        print(f"\n❌ Errore: {e}")
        print("\nInstalla EasyOCR con:")
        print("   pip install easyocr")


# ============================================================================
# 📚 GUIDA TEST OCR SU POKERSTARS
# ============================================================================
"""
================================================================================
                    GUIDA TEST OCR SU POKERSTARS
================================================================================

🎯 COME TESTARE L'OCR

1. Cattura uno screenshot del tavolo:
   
   from screen_capture import ScreenRecorder
   recorder = ScreenRecorder(top=100, left=100, width=800, height=600)
   frame = recorder.grab_frame()
   cv2.imwrite("poker_table.png", frame)

2. Identifica le coordinate del pot e stack:
   - Apri l'immagine con un editor (Preview su Mac)
   - Annota le coordinate (dividi per 2 se Retina)
   
3. Configura il TableReader:
   
   from game_state_reader import TableReader, RegionConfig
   
   pot_region = RegionConfig(
       top=180,      # Coordinata Y del pot
       left=350,     # Coordinata X del pot
       width=100,    # Larghezza area
       height=25,    # Altezza area
       name="Pot",
       scale=2       # 2 per Retina
   )
   
   stack_region = RegionConfig(
       top=450,
       left=300,
       width=80,
       height=20,
       name="Hero Stack",
       scale=2
   )
   
   reader = TableReader(
       pot_region=pot_region,
       stack_region=stack_region,
       verbose=True
   )

4. Testa con calibrazione visuale:
   
   import cv2
   frame = cv2.imread("poker_table.png")
   reader.calibrate_region(frame, pot_region, "Pot Calibration")

5. Leggi lo stato del gioco:
   
   state = reader.read_game_state(frame)
   print(f"Pot: ${state.pot_size}")
   print(f"Stack: ${state.hero_stack}")
   print(f"Action: {state.action_detected}")


🔧 TROUBLESHOOTING NUMERI PICCOLI

Se l'OCR non legge bene i numeri piccoli di PokerStars:

1. Aumenta la regione di crop:
   - Includi un po' di margine attorno al numero
   
2. Modifica il preprocessing:
   - L'upscaling 2x è già attivo
   - Prova a cambiare la soglia del CLAHE
   
3. Usa lo sfondo giusto:
   - PokerStars ha numeri chiari su sfondo scuro
   - Il codice inverte automaticamente se necessario

4. Controlla la scala Retina:
   - Assicurati che scale=2 sia corretto per il tuo display


📊 OUTPUT ESEMPIO

{
    "cards": {
        "my_hand": ["Ah", "Kd"],
        "board": ["Js", "Tc", "2h"],
        "game_stage": "Flop"
    },
    "pot_size": 150.50,
    "hero_stack": 1000.00,
    "action_detected": "Bet/Raise",
    "pot_changed": true,
    "ocr_confidence": 0.85
}

================================================================================
"""
