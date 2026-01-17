#!/usr/bin/env python3
"""
Script per testare il modello YOLO di riconoscimento carte da poker.
Può testare su:
1. Immagini singole
2. Una cartella di immagini
3. Screenshot live dello schermo
"""

import argparse
from pathlib import Path
from ultralytics import YOLO
import cv2


def test_on_images(model_path: str, image_source: str, conf_threshold: float = 0.25):
    """Testa il modello su immagini."""
    
    # Carica il modello
    print(f"📦 Caricando modello: {model_path}")
    model = YOLO(model_path)
    
    source_path = Path(image_source)
    
    if source_path.is_file():
        # Singola immagine
        images = [source_path]
    elif source_path.is_dir():
        # Cartella di immagini
        images = list(source_path.glob("*.jpg")) + \
                 list(source_path.glob("*.jpeg")) + \
                 list(source_path.glob("*.png"))
    else:
        print(f"❌ Percorso non valido: {image_source}")
        return
    
    print(f"🖼️  Trovate {len(images)} immagini da testare\n")
    
    for img_path in images:
        print(f"--- Testando: {img_path.name} ---")
        
        # Esegui predizione
        results = model.predict(
            source=str(img_path),
            conf=conf_threshold,
            device="mps",  # Apple Silicon
            verbose=False
        )
        
        # Analizza risultati
        for result in results:
            boxes = result.boxes
            if len(boxes) == 0:
                print("  ⚠️  Nessuna carta rilevata")
            else:
                print(f"  ✅ Rilevate {len(boxes)} carte:")
                for box in boxes:
                    cls_id = int(box.cls[0])
                    cls_name = model.names[cls_id]
                    conf = float(box.conf[0])
                    print(f"      - {cls_name}: {conf:.1%}")
        
        # Salva immagine con annotazioni
        output_dir = Path("test_results")
        output_dir.mkdir(exist_ok=True)
        
        annotated = results[0].plot()
        output_path = output_dir / f"pred_{img_path.name}"
        cv2.imwrite(str(output_path), annotated)
        print(f"  💾 Salvata: {output_path}\n")
    
    print(f"✅ Test completato! Risultati salvati in: test_results/")


def test_live_screen(model_path: str, conf_threshold: float = 0.25):
    """Testa il modello con screenshot live dello schermo."""
    import mss
    import numpy as np
    
    print(f"📦 Caricando modello: {model_path}")
    model = YOLO(model_path)
    
    print("🎥 Modalità LIVE - Premi 'q' per uscire, 's' per screenshot")
    print("   Posiziona la finestra del poker e premi un tasto...\n")
    
    with mss.mss() as sct:
        # Coordinate calibrate dalla finestra PokerStars
        # (da capture_training_images.py)
        RETINA_SCALE = 2  # Per display Retina
        monitor = {
            "top": 19 * RETINA_SCALE,       # CAPTURE_TOP
            "left": 4 * RETINA_SCALE,       # CAPTURE_LEFT
            "width": 476 * RETINA_SCALE,    # CAPTURE_WIDTH
            "height": 338 * RETINA_SCALE    # CAPTURE_HEIGHT
        }
        
        while True:
            # Cattura schermo
            screenshot = sct.grab(monitor)
            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            # Ridimensiona per visualizzazione
            scale = 0.5
            display_frame = cv2.resize(frame, None, fx=scale, fy=scale)
            
            # Predizione
            results = model.predict(
                source=frame,
                conf=conf_threshold,
                device="mps",
                verbose=False
            )
            
            # Annota frame
            annotated = results[0].plot()
            annotated = cv2.resize(annotated, None, fx=scale, fy=scale)
            
            # Mostra info
            boxes = results[0].boxes
            cards = [model.names[int(b.cls[0])] for b in boxes]
            info_text = f"Carte: {', '.join(cards) if cards else 'Nessuna'}"
            cv2.putText(annotated, info_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow("Test Modello Poker (q=esci, s=salva)", annotated)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                # Salva screenshot con annotazioni
                output_dir = Path("test_results")
                output_dir.mkdir(exist_ok=True)
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = output_dir / f"live_{timestamp}.png"
                cv2.imwrite(str(output_path), results[0].plot())
                print(f"💾 Screenshot salvato: {output_path}")
    
    cv2.destroyAllWindows()
    print("👋 Test live terminato")


def main():
    parser = argparse.ArgumentParser(description="Test modello YOLO poker cards")
    parser.add_argument(
        "--model", "-m",
        default="runs/poker_cards/train/weights/best.pt",
        help="Percorso del modello (default: runs/poker_cards/train/weights/best.pt)"
    )
    parser.add_argument(
        "--source", "-s",
        help="Immagine o cartella da testare (ometti per modalità live)"
    )
    parser.add_argument(
        "--conf", "-c",
        type=float,
        default=0.25,
        help="Soglia di confidenza (default: 0.25)"
    )
    parser.add_argument(
        "--live", "-l",
        action="store_true",
        help="Modalità live screen capture"
    )
    
    args = parser.parse_args()
    
    if args.live or args.source is None:
        test_live_screen(args.model, args.conf)
    else:
        test_on_images(args.model, args.source, args.conf)


if __name__ == "__main__":
    main()
