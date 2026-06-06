"""
Cattura Immagini per Training YOLO
===================================
Script semplice per catturare screenshot di PokerStars da annotare.

USO:
1. Avvia PokerStars e posiziona la finestra
2. Esegui: python capture_training_images.py
3. Premi SPAZIO per catturare uno screenshot
4. Premi Q per uscire

Le immagini vengono salvate in dataset/train/images/
"""

import cv2
import mss
import numpy as np
import time
import os
from datetime import datetime

# ============================================================================
# CONFIGURAZIONE - MODIFICA QUESTE COORDINATE
# ============================================================================
# Coordinate logiche della finestra PokerStars (calibrate)
CAPTURE_TOP = 19       # Y superiore
CAPTURE_LEFT = 4       # X sinistra
CAPTURE_WIDTH = 476    # Larghezza
CAPTURE_HEIGHT = 338   # Altezza
RETINA_SCALE = 2       # 2 per display Retina, 1 per display normali

# Directory di output
OUTPUT_DIR = "dataset/train/images"


def request_screen_permission():
    """Prova a catturare uno screenshot per richiedere i permessi."""
    print("🔐 Verifica permessi registrazione schermo...")
    try:
        with mss.mss() as sct:
            # Cattura un pixel per attivare la richiesta permessi
            test_region = {"top": 0, "left": 0, "width": 10, "height": 10}
            sct.grab(test_region)
            print("✅ Permessi OK!")
            return True
    except Exception as e:
        print(f"❌ Errore: {e}")
        print("\n⚠️  DEVI CONCEDERE I PERMESSI PER LA REGISTRAZIONE SCHERMO")
        print("   1. Vai in: Impostazioni di Sistema → Privacy e Sicurezza → Registrazione Schermo")
        print("   2. Aggiungi Terminal (o l'app da cui esegui Python)")
        print("   3. Abilita il toggle")
        print("   4. Riavvia il terminale e riprova")
        return False


def main():
    print("=" * 60)
    print("📸 CATTURA IMMAGINI PER TRAINING YOLO")
    print("=" * 60)
    
    # Verifica permessi
    if not request_screen_permission():
        return
    
    # Crea directory output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Configurazione cattura
    monitor = {
        "top": CAPTURE_TOP * RETINA_SCALE,
        "left": CAPTURE_LEFT * RETINA_SCALE,
        "width": CAPTURE_WIDTH * RETINA_SCALE,
        "height": CAPTURE_HEIGHT * RETINA_SCALE,
    }
    
    print(f"\n📍 Configurazione:")
    print(f"   Coordinate: ({CAPTURE_LEFT}, {CAPTURE_TOP})")
    print(f"   Dimensioni: {CAPTURE_WIDTH}x{CAPTURE_HEIGHT}")
    print(f"   Scala Retina: {RETINA_SCALE}x")
    print(f"   Output: {OUTPUT_DIR}/")
    
    print("\n🎮 Controlli:")
    print("   [SPAZIO] = Cattura screenshot")
    print("   [C] = Calibra (vedi coordinate correnti)")
    print("   [Q] / [ESC] = Esci")
    
    print("\n▶️ Avvio preview... Posiziona PokerStars nella zona di cattura!")
    
    image_count = 0
    
    with mss.mss() as sct:
        cv2.namedWindow("Preview - Premi SPAZIO per catturare", cv2.WINDOW_NORMAL)
        
        while True:
            # Cattura frame
            screenshot = sct.grab(monitor)
            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            # Ridimensiona per visualizzazione
            display_frame = cv2.resize(frame, (CAPTURE_WIDTH, CAPTURE_HEIGHT))
            
            # Aggiungi info
            cv2.putText(display_frame, f"Immagini salvate: {image_count}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_frame, "SPAZIO=Cattura | Q=Esci", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Disegna box guida per le carte (centro schermo, area board)
            h, w = display_frame.shape[:2]
            board_y = int(h * 0.35)
            cv2.line(display_frame, (0, board_y), (w, board_y), (0, 255, 255), 1)
            cv2.putText(display_frame, "Board zone (sopra)", 
                       (10, board_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
            
            hand_y = int(h * 0.7)
            cv2.line(display_frame, (0, hand_y), (w, hand_y), (0, 255, 0), 1)
            cv2.putText(display_frame, "Hand zone (sotto)", 
                       (10, hand_y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            
            cv2.imshow("Preview - Premi SPAZIO per catturare", display_frame)
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord(' '):  # Spazio
                # Salva immagine
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"poker_{timestamp}.jpg"
                filepath = os.path.join(OUTPUT_DIR, filename)
                cv2.imwrite(filepath, frame)
                image_count += 1
                print(f"✅ Salvato: {filename} (totale: {image_count})")
            
            elif key == ord('c'):  # Calibra
                print(f"\n📍 Coordinate attuali:")
                print(f"   CAPTURE_TOP = {CAPTURE_TOP}")
                print(f"   CAPTURE_LEFT = {CAPTURE_LEFT}")
                print(f"   CAPTURE_WIDTH = {CAPTURE_WIDTH}")
                print(f"   CAPTURE_HEIGHT = {CAPTURE_HEIGHT}")
            
            elif key == ord('q') or key == 27:  # Q o ESC
                break
    
    cv2.destroyAllWindows()
    print(f"\n🏁 Finito! Catturate {image_count} immagini.")
    print(f"   Salvate in: {OUTPUT_DIR}/")
    print("\n📝 Prossimo passo: Annota le immagini con LabelImg o Roboflow")
    print("   Comando: pip install labelImg && labelImg")


if __name__ == "__main__":
    main()
