"""
Card Recognizer Module - PokerBrain
====================================
Modulo per il riconoscimento delle carte da poker usando YOLO.
Distingue tra Hole Cards (mano del giocatore) e Community Cards (board)
in base alla posizione sullo schermo.
"""

import cv2
import numpy as np
from ultralytics import YOLO
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# Soglia di confidenza minima per accettare una detection
CONFIDENCE_THRESHOLD = 0.5

# Soglia Y normalizzata per distinguere board (alto) da hand (basso)
# Le carte sopra questa soglia sono considerate "board"
# Le carte sotto questa soglia sono considerate "my_hand"
# Valore tra 0.0 (top) e 1.0 (bottom)
BOARD_Y_THRESHOLD = 0.6  # Carte con Y < 60% dello schermo = board

# Lista completa delle 52 carte (per riferimento e validazione)
CARD_CLASSES = [
    # Cuori (Hearts - h)
    "Ah", "2h", "3h", "4h", "5h", "6h", "7h", "8h", "9h", "Th", "Jh", "Qh", "Kh",
    # Quadri (Diamonds - d)
    "Ad", "2d", "3d", "4d", "5d", "6d", "7d", "8d", "9d", "Td", "Jd", "Qd", "Kd",
    # Fiori (Clubs - c)
    "Ac", "2c", "3c", "4c", "5c", "6c", "7c", "8c", "9c", "Tc", "Jc", "Qc", "Kc",
    # Picche (Spades - s)
    "As", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s", "Ts", "Js", "Qs", "Ks",
]


class GameStage(Enum):
    """Fasi del gioco in base al numero di carte sul board."""
    PREFLOP = "Preflop"
    FLOP = "Flop"
    TURN = "Turn"
    RIVER = "River"
    UNKNOWN = "Unknown"


@dataclass
class CardDetection:
    """Rappresenta una singola carta rilevata."""
    card: str  # Es: "Ah", "Kd"
    confidence: float
    box: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    center_x: int
    center_y: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "card": self.card,
            "confidence": round(self.confidence, 3),
            "box": list(self.box),
            "center": (self.center_x, self.center_y)
        }


class PokerBrain:
    """
    Classe principale per il riconoscimento delle carte da poker.
    
    Usa YOLO per rilevare le carte e le classifica in base alla posizione
    sullo schermo (hole cards vs community cards).
    
    Attributes:
        model: Modello YOLO caricato
        confidence_threshold: Soglia minima di confidenza
        board_y_threshold: Soglia Y per distinguere board da hand
    
    Example:
        >>> brain = PokerBrain(model_path="best.pt")
        >>> result = brain.analyze_frame(frame)
        >>> print(result["my_hand"])  # ["Ah", "Kd"]
        >>> print(result["board"])    # ["Js", "Tc", "2h"]
        >>> print(result["game_stage"])  # "Flop"
    """
    
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        board_y_threshold: float = BOARD_Y_THRESHOLD,
        verbose: bool = False
    ):
        """
        Inizializza il PokerBrain con il modello YOLO.
        
        Args:
            model_path: Percorso al modello YOLO (.pt). 
                       Usa "yolov8n.pt" per test (non addestrato per carte).
                       Usa "best.pt" o "poker_cards.pt" per modello addestrato.
            confidence_threshold: Soglia minima di confidenza (0.0-1.0)
            board_y_threshold: Soglia Y normalizzata per distinguere board/hand
            verbose: Se True, stampa log dettagliati
        """
        self.confidence_threshold = confidence_threshold
        self.board_y_threshold = board_y_threshold
        self.verbose = verbose
        
        print(f"🧠 Inizializzazione PokerBrain...")
        print(f"   Modello: {model_path}")
        print(f"   Confidenza minima: {confidence_threshold}")
        print(f"   Soglia Y board: {board_y_threshold}")
        
        try:
            self.model = YOLO(model_path)
            print(f"   ✅ Modello caricato con successo!")
            
            # Mostra le classi del modello (se disponibili)
            if hasattr(self.model, 'names') and self.model.names:
                num_classes = len(self.model.names)
                print(f"   Classi nel modello: {num_classes}")
                if self.verbose:
                    print(f"   Nomi classi: {list(self.model.names.values())[:10]}...")
        except Exception as e:
            print(f"   ❌ Errore nel caricamento del modello: {e}")
            raise
    
    def analyze_frame(
        self,
        frame: np.ndarray,
        draw_boxes: bool = False
    ) -> Dict[str, Any]:
        """
        Analizza un frame per rilevare e classificare le carte.
        
        Esegue l'inferenza YOLO, filtra per confidenza, e classifica
        le carte in base alla loro posizione Y sullo schermo.
        
        Args:
            frame: Immagine BGR (formato OpenCV)
            draw_boxes: Se True, disegna i bounding box sul frame
        
        Returns:
            Dizionario con:
            - my_hand: Lista delle carte nella mano del giocatore (es: ["Ah", "Kd"])
            - board: Lista delle community cards ordinate da sinistra a destra
            - game_stage: Fase del gioco (Preflop/Flop/Turn/River)
            - detections: Lista completa delle rilevazioni con dettagli
            - annotated_frame: Frame con box disegnati (solo se draw_boxes=True)
        """
        frame_height, frame_width = frame.shape[:2]
        
        # Esegui inferenza YOLO
        results = self.model(frame, verbose=False)
        
        # Lista per raccogliere tutte le detection valide
        all_detections: List[CardDetection] = []
        
        # Processa i risultati
        for result in results:
            boxes = result.boxes
            
            if boxes is None or len(boxes) == 0:
                continue
            
            for i, box in enumerate(boxes):
                # Estrai confidenza
                conf = float(box.conf[0])
                
                # Filtra per confidenza
                if conf < self.confidence_threshold:
                    continue
                
                # Estrai classe
                class_id = int(box.cls[0])
                class_name = self.model.names.get(class_id, f"class_{class_id}")
                
                # Estrai coordinate del bounding box
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                
                # Calcola il centro
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                
                detection = CardDetection(
                    card=class_name,
                    confidence=conf,
                    box=(x1, y1, x2, y2),
                    center_x=center_x,
                    center_y=center_y
                )
                
                all_detections.append(detection)
        
        # Classifica le carte in base alla posizione Y
        my_hand_detections: List[CardDetection] = []
        board_detections: List[CardDetection] = []
        
        y_threshold_pixels = int(frame_height * self.board_y_threshold)
        
        for det in all_detections:
            if det.center_y > y_threshold_pixels:
                # Carta nella parte bassa dello schermo = mia mano
                my_hand_detections.append(det)
            else:
                # Carta nella parte alta/centrale = board
                board_detections.append(det)
        
        # Ordina il board da sinistra a destra (per ordine di uscita)
        board_detections.sort(key=lambda d: d.center_x)
        
        # Ordina la mano da sinistra a destra
        my_hand_detections.sort(key=lambda d: d.center_x)
        
        # Estrai solo i nomi delle carte
        my_hand = [d.card for d in my_hand_detections]
        board = [d.card for d in board_detections]
        
        # Determina la fase del gioco
        game_stage = self._determine_game_stage(len(board))
        
        # Prepara il risultato
        result = {
            "my_hand": my_hand,
            "board": board,
            "game_stage": game_stage.value,
            "detections": [d.to_dict() for d in all_detections],
            "stats": {
                "total_cards_detected": len(all_detections),
                "hand_cards": len(my_hand),
                "board_cards": len(board),
                "frame_size": (frame_width, frame_height),
                "y_threshold_pixels": y_threshold_pixels
            }
        }
        
        # Disegna i bounding box se richiesto
        if draw_boxes:
            annotated_frame = self._draw_detections(
                frame.copy(), 
                my_hand_detections, 
                board_detections,
                y_threshold_pixels
            )
            result["annotated_frame"] = annotated_frame
        
        if self.verbose:
            print(f"\n📊 Analisi Frame:")
            print(f"   Carte rilevate: {len(all_detections)}")
            print(f"   Mia mano: {my_hand}")
            print(f"   Board: {board}")
            print(f"   Fase: {game_stage.value}")
        
        return result
    
    def _determine_game_stage(self, board_count: int) -> GameStage:
        """Determina la fase del gioco in base al numero di carte sul board."""
        if board_count == 0:
            return GameStage.PREFLOP
        elif board_count == 3:
            return GameStage.FLOP
        elif board_count == 4:
            return GameStage.TURN
        elif board_count == 5:
            return GameStage.RIVER
        else:
            return GameStage.UNKNOWN
    
    def _draw_detections(
        self,
        frame: np.ndarray,
        hand_detections: List[CardDetection],
        board_detections: List[CardDetection],
        y_threshold: int
    ) -> np.ndarray:
        """Disegna i bounding box sul frame con colori diversi per hand/board."""
        
        # Colori (BGR)
        COLOR_HAND = (0, 255, 0)    # Verde per la mano
        COLOR_BOARD = (255, 0, 0)   # Blu per il board
        COLOR_THRESHOLD = (0, 255, 255)  # Giallo per la linea soglia
        
        # Disegna la linea di soglia
        cv2.line(frame, (0, y_threshold), (frame.shape[1], y_threshold), 
                 COLOR_THRESHOLD, 2, cv2.LINE_AA)
        cv2.putText(frame, "Board Zone", (10, y_threshold - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_THRESHOLD, 2)
        cv2.putText(frame, "Hand Zone", (10, y_threshold + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_THRESHOLD, 2)
        
        # Disegna le carte della mano
        for det in hand_detections:
            x1, y1, x2, y2 = det.box
            cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_HAND, 2)
            label = f"{det.card} ({det.confidence:.2f})"
            cv2.putText(frame, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_HAND, 2)
        
        # Disegna le carte del board
        for i, det in enumerate(board_detections):
            x1, y1, x2, y2 = det.box
            cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_BOARD, 2)
            label = f"{det.card} ({det.confidence:.2f})"
            cv2.putText(frame, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_BOARD, 2)
            # Numero posizione sul board
            cv2.putText(frame, str(i + 1), (det.center_x - 5, det.center_y + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return frame
    
    def calculate_equity(
        self,
        my_hand: List[str],
        board: List[str]
    ) -> Dict[str, Any]:
        """
        Calcola l'equity della mano corrente.
        
        Args:
            my_hand: Lista delle carte in mano (es: ["Ah", "Kd"])
            board: Lista delle community cards (es: ["Js", "Tc", "2h"])
        
        Returns:
            Dizionario con le statistiche di equity
        
        TODO: Integrare libreria Treys per il calcolo dell'equity
        
        Per installare Treys:
            pip install treys
        
        Esempio di integrazione futura:
            from treys import Card, Evaluator, Deck
            
            evaluator = Evaluator()
            hand = [Card.new(c) for c in my_hand]
            board_cards = [Card.new(c) for c in board]
            
            # Monte Carlo simulation per equity
            wins = 0
            for _ in range(10000):
                # Simula carte rimanenti
                ...
        """
        # Placeholder - TODO: Implementare con Treys
        return {
            "status": "not_implemented",
            "message": "TODO: Integrare libreria Treys per calcolo equity",
            "my_hand": my_hand,
            "board": board,
            "equity_percent": None,
            "hand_rank": None,
            "hand_description": None
        }
    
    def get_model_info(self) -> Dict[str, Any]:
        """Restituisce informazioni sul modello caricato."""
        info = {
            "model_type": str(type(self.model)),
            "confidence_threshold": self.confidence_threshold,
            "board_y_threshold": self.board_y_threshold,
        }
        
        if hasattr(self.model, 'names') and self.model.names:
            info["num_classes"] = len(self.model.names)
            info["class_names"] = list(self.model.names.values())
        
        return info


# ============================================================================
# FUNZIONI DI UTILITY
# ============================================================================

def validate_card_notation(card: str) -> bool:
    """
    Valida la notazione di una carta.
    
    Args:
        card: Stringa rappresentante la carta (es: "Ah", "Kd")
    
    Returns:
        True se la notazione è valida
    """
    if len(card) != 2:
        return False
    
    rank, suit = card[0], card[1]
    valid_ranks = "A23456789TJQK"
    valid_suits = "hdcs"
    
    return rank in valid_ranks and suit in valid_suits


def convert_card_notation(card: str, to_format: str = "full") -> str:
    """
    Converte la notazione della carta in diversi formati.
    
    Args:
        card: Carta in formato breve (es: "Ah")
        to_format: "full" per nome completo, "unicode" per simboli
    
    Returns:
        Carta nel formato richiesto
    """
    if not validate_card_notation(card):
        return card
    
    rank, suit = card[0], card[1]
    
    rank_names = {
        "A": "Ace", "2": "Two", "3": "Three", "4": "Four", "5": "Five",
        "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine", "T": "Ten",
        "J": "Jack", "Q": "Queen", "K": "King"
    }
    
    suit_names = {"h": "Hearts", "d": "Diamonds", "c": "Clubs", "s": "Spades"}
    suit_unicode = {"h": "♥", "d": "♦", "c": "♣", "s": "♠"}
    
    if to_format == "full":
        return f"{rank_names.get(rank, rank)} of {suit_names.get(suit, suit)}"
    elif to_format == "unicode":
        return f"{rank}{suit_unicode.get(suit, suit)}"
    
    return card


# ============================================================================
# MAIN - Test e Demo
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("POKER BRAIN - Card Recognition Module Test")
    print("=" * 70)
    
    # Test base del caricamento modello
    print("\n🧪 Test caricamento modello...")
    
    try:
        # Usa yolov8n.pt per test (modello generico, non per carte)
        brain = PokerBrain(model_path="yolov8n.pt", verbose=True)
        print("\n✅ PokerBrain inizializzato con successo!")
        
        # Mostra info modello
        info = brain.get_model_info()
        print(f"\n📋 Info Modello:")
        for key, value in info.items():
            if key != "class_names":
                print(f"   {key}: {value}")
        
    except Exception as e:
        print(f"\n❌ Errore: {e}")
        print("\nAssicurati di aver installato ultralytics:")
        print("   pip install ultralytics")


# ============================================================================
# 📚 GUIDA AL TRAINING YOLOV8 PER RICONOSCIMENTO CARTE
# ============================================================================
"""
================================================================================
                    GUIDA COMPLETA AL TRAINING YOLOV8
                    PER RICONOSCIMENTO CARTE DA POKER
================================================================================

🎯 OBIETTIVO
------------
Addestrare YOLOv8 a riconoscere le 52 carte del mazzo, ognuna come classe separata.

📁 STRUTTURA CARTELLE
---------------------
Organizza il tuo dataset così:

poker_cards_dataset/
├── data.yaml                 # Configurazione del dataset
├── train/
│   ├── images/              # Immagini di training
│   │   ├── img_001.jpg
│   │   ├── img_002.jpg
│   │   └── ...
│   └── labels/              # Annotazioni (stesso nome, .txt)
│       ├── img_001.txt
│       ├── img_002.txt
│       └── ...
├── val/
│   ├── images/              # Immagini di validazione (10-20% del totale)
│   │   └── ...
│   └── labels/
│       └── ...
└── test/                    # Opzionale
    ├── images/
    └── labels/


📋 FILE data.yaml
-----------------
Crea questo file nella root del dataset:

```yaml
# poker_cards_dataset/data.yaml

path: /percorso/assoluto/a/poker_cards_dataset
train: train/images
val: val/images

# 52 classi - una per ogni carta
names:
  0: Ah
  1: 2h
  2: 3h
  3: 4h
  4: 5h
  5: 6h
  6: 7h
  7: 8h
  8: 9h
  9: Th
  10: Jh
  11: Qh
  12: Kh
  13: Ad
  14: 2d
  15: 3d
  16: 4d
  17: 5d
  18: 6d
  19: 7d
  20: 8d
  21: 9d
  22: Td
  23: Jd
  24: Qd
  25: Kd
  26: Ac
  27: 2c
  28: 3c
  29: 4c
  30: 5c
  31: 6c
  32: 7c
  33: 8c
  34: 9c
  35: Tc
  36: Jc
  37: Qc
  38: Kc
  39: As
  40: 2s
  41: 3s
  42: 4s
  43: 5s
  44: 6s
  45: 7s
  46: 8s
  47: 9s
  48: Ts
  49: Js
  50: Qs
  51: Ks
```


📝 FORMATO ANNOTAZIONI (Label .txt)
------------------------------------
YOLO usa il formato txt con una riga per oggetto:

    <class_id> <x_center> <y_center> <width> <height>

Dove:
- Tutti i valori sono NORMALIZZATI (0.0 - 1.0) rispetto alla dimensione immagine
- x_center, y_center: centro del bounding box
- width, height: dimensioni del bounding box

Esempio (img_001.txt):
---------------------
0 0.45 0.32 0.08 0.12
25 0.55 0.32 0.08 0.12
39 0.25 0.75 0.10 0.15

(Significa: Ah al centro-alto, Kd a destra del centro, As in basso a sinistra)


🏷️ STRUMENTI PER ETICHETTARE
-----------------------------
Usa uno di questi tool per creare le annotazioni:

1. **LabelImg** (gratuito, semplice)
   pip install labelImg
   labelImg

2. **CVAT** (online, potente)
   https://cvat.ai

3. **Roboflow** (online, con augmentation)
   https://roboflow.com

4. **Label Studio** (self-hosted, versatile)
   pip install label-studio
   label-studio start


💡 CONSIGLI PER IL DATASET
--------------------------
1. Almeno 100-200 immagini per carta (5200-10400 immagini totali)
   - Puoi iniziare con meno per un primo test

2. Varia le condizioni:
   - Diversi sfondi (tavolo verde, blu, rosso)
   - Diverse illuminazioni
   - Diverse angolazioni (leggere)
   - Diverse scale (carte grandi/piccole)

3. Includi situazioni reali:
   - Carte parzialmente sovrapposte
   - Carte in diverse posizioni sullo schermo
   - Screenshot da PokerStars, GGPoker, 888, etc.


🚀 COMANDI PER IL TRAINING
--------------------------

1. Installa ultralytics:
   pip install ultralytics

2. Avvia il training:
   
   # Training base (consigliato per iniziare)
   yolo detect train data=/percorso/a/data.yaml model=yolov8n.pt epochs=100 imgsz=640

   # Training con più epoche e batch size maggiore (se hai GPU potente)
   yolo detect train data=/percorso/a/data.yaml model=yolov8s.pt epochs=300 imgsz=640 batch=16

   # Training con data augmentation personalizzata
   yolo detect train data=/percorso/a/data.yaml model=yolov8n.pt epochs=200 imgsz=640 \
       augment=True \
       flipud=0.0 \          # Non capovolgere (le carte hanno orientamento)
       fliplr=0.0 \          # Non specchiare
       mosaic=0.5 \
       hsv_h=0.015 \
       hsv_s=0.4 \
       hsv_v=0.4

3. Il modello trainato sarà salvato in:
   runs/detect/train/weights/best.pt


📊 VALIDAZIONE
--------------
# Valida il modello
yolo detect val model=runs/detect/train/weights/best.pt data=/percorso/a/data.yaml

# Testa su immagini singole
yolo detect predict model=runs/detect/train/weights/best.pt source=/percorso/a/immagine.jpg


🔄 USO DEL MODELLO TRAINATO
---------------------------
Dopo il training, usa il modello così:

    brain = PokerBrain(model_path="runs/detect/train/weights/best.pt")
    result = brain.analyze_frame(frame)


📊 METRICHE DA MONITORARE
-------------------------
- mAP50: Mean Average Precision @ IoU 0.5 (punta ad almeno 0.9)
- mAP50-95: mAP media (punta ad almeno 0.7)
- Precision/Recall per classe


⚡ TRUCCHI PER VELOCIZZARE
--------------------------
1. Transfer learning: parti da un modello pre-addestrato (yolov8n.pt)
2. Usa GPU: molto più veloce di CPU
3. Inizia con poche classi (es. solo gli Assi) per testare il pipeline
4. Usa Roboflow per data augmentation automatica

================================================================================
"""
