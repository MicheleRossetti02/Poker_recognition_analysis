#!/usr/bin/env python3
"""
Fast Image Capture for YOLO Training
=====================================
Cattura automatica di immagini ogni N secondi.
Perfetto per catturare molte immagini mentre giochi a poker!

USO:
1. Avvia PokerStars e posiziona la finestra
2. Esegui: python fast_capture.py
3. Le immagini vengono catturate automaticamente ogni 2 secondi
4. Premi Q per fermare

OPZIONI:
  --interval 1.5    Intervallo in secondi (default: 2)
  --output folder   Cartella di output (default: new_training_images)
  --manual          Modalità manuale (solo con SPAZIO)
"""

import cv2
import mss
import numpy as np
import time
import os
import argparse
from datetime import datetime

# ============================================================================
# COORDINATE CALIBRATE - dalla finestra PokerStars
# ============================================================================
CAPTURE_TOP = 19
CAPTURE_LEFT = 4
CAPTURE_WIDTH = 476
CAPTURE_HEIGHT = 338
RETINA_SCALE = 2


def main():
    parser = argparse.ArgumentParser(description="Fast capture per training YOLO")
    parser.add_argument("--interval", "-i", type=float, default=2.0,
                        help="Intervallo tra catture in secondi (default: 2)")
    parser.add_argument("--output", "-o", default="new_training_images",
                        help="Cartella di output (default: new_training_images)")
    parser.add_argument("--manual", "-m", action="store_true",
                        help="Modalità manuale (cattura solo con SPAZIO)")
    args = parser.parse_args()
    
    # Crea cartella output
    os.makedirs(args.output, exist_ok=True)
    
    # Configurazione monitor
    monitor = {
        "top": CAPTURE_TOP * RETINA_SCALE,
        "left": CAPTURE_LEFT * RETINA_SCALE,
        "width": CAPTURE_WIDTH * RETINA_SCALE,
        "height": CAPTURE_HEIGHT * RETINA_SCALE,
    }
    
    print("=" * 60)
    print("🚀 FAST CAPTURE - Cattura Veloce per Training")
    print("=" * 60)
    print(f"\n📁 Output: {args.output}/")
    
    if args.manual:
        print("🎮 Modalità: MANUALE (premi SPAZIO per catturare)")
    else:
        print(f"⏱️  Modalità: AUTOMATICA (ogni {args.interval} secondi)")
    
    print("\n🎮 Controlli:")
    print("   [SPAZIO] = Cattura manuale")
    print("   [P] = Pausa/Riprendi auto-capture") 
    print("   [Q] = Esci")
    print("\n" + "=" * 60)
    print("▶️  Posiziona PokerStars e inizia a giocare!")
    print("=" * 60 + "\n")
    
    image_count = 0
    last_capture = 0
    paused = args.manual  # Se manuale, inizia in pausa
    
    with mss.mss() as sct:
        cv2.namedWindow("Fast Capture", cv2.WINDOW_NORMAL)
        
        while True:
            current_time = time.time()
            
            # Cattura frame
            screenshot = sct.grab(monitor)
            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            # Auto-capture
            should_capture = False
            if not paused and not args.manual:
                if current_time - last_capture >= args.interval:
                    should_capture = True
            
            # Prepara display
            display = cv2.resize(frame, (CAPTURE_WIDTH, CAPTURE_HEIGHT))
            
            # Info overlay
            status = "⏸️ PAUSA" if paused else f"🔴 REC ({args.interval}s)"
            if args.manual:
                status = "📸 MANUALE"
            
            cv2.putText(display, f"Salvate: {image_count}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(display, status,
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # Countdown per prossima cattura
            if not paused and not args.manual:
                time_to_next = args.interval - (current_time - last_capture)
                if time_to_next > 0:
                    cv2.putText(display, f"Next: {time_to_next:.1f}s",
                               (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow("Fast Capture", display)
            
            # Cattura automatica
            if should_capture:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                filename = f"poker_{timestamp}.jpg"
                filepath = os.path.join(args.output, filename)
                cv2.imwrite(filepath, frame)
                image_count += 1
                last_capture = current_time
                print(f"📸 [{image_count}] {filename}")
            
            # Input tastiera
            key = cv2.waitKey(30) & 0xFF
            
            if key == ord(' '):  # Spazio = cattura manuale
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                filename = f"poker_{timestamp}.jpg"
                filepath = os.path.join(args.output, filename)
                cv2.imwrite(filepath, frame)
                image_count += 1
                print(f"📸 [MANUAL {image_count}] {filename}")
            
            elif key == ord('p'):  # P = pausa
                paused = not paused
                state = "⏸️ PAUSA" if paused else "▶️ RIPRESO"
                print(f"\n{state}\n")
                last_capture = current_time  # Reset timer
            
            elif key == ord('q') or key == 27:  # Q o ESC
                break
    
    cv2.destroyAllWindows()
    
    print("\n" + "=" * 60)
    print(f"✅ COMPLETATO! Catturate {image_count} immagini")
    print(f"📁 Salvate in: {args.output}/")
    print("=" * 60)
    print("\n📝 Prossimi passi:")
    print("   1. Carica le immagini su Roboflow per annotarle")
    print("   2. Scarica il dataset aggiornato")
    print("   3. Ri-esegui il training")


if __name__ == "__main__":
    main()
