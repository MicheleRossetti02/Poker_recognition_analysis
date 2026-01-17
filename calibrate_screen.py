"""
Strumento di Calibrazione per Cattura Schermo
==============================================
Cattura l'intero schermo e ti permette di selezionare visivamente
l'area da catturare con il mouse.

USO:
1. Esegui: python calibrate_screen.py
2. Appare il tuo intero schermo
3. Clicca e trascina per selezionare l'area della finestra PokerStars
4. Premi ENTER per confermare o C per annullare
5. Le coordinate verranno stampate a schermo
"""

import cv2
import mss
import numpy as np

RETINA_SCALE = 2  # Cambia a 1 se non hai display Retina

def main():
    print("=" * 60)
    print("🎯 CALIBRAZIONE COORDINATE SCHERMO")
    print("=" * 60)
    
    print("\n📸 Cattura schermo intero...")
    
    with mss.mss() as sct:
        # Cattura tutto il monitor primario
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        frame = np.array(screenshot)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    # Ridimensiona per visualizzazione (i pixel Retina sono il doppio)
    display_scale = 1.0 / RETINA_SCALE
    display_frame = cv2.resize(frame, None, fx=display_scale, fy=display_scale)
    
    print(f"\n📐 Dimensioni schermo:")
    print(f"   Pixel fisici: {frame.shape[1]}x{frame.shape[0]}")
    print(f"   Punti logici: {display_frame.shape[1]}x{display_frame.shape[0]}")
    
    print("\n🖱️  ISTRUZIONI:")
    print("   1. Clicca e trascina per selezionare l'area di PokerStars")
    print("   2. Premi ENTER o SPAZIO per confermare")
    print("   3. Premi C per annullare")
    
    # Seleziona ROI
    cv2.namedWindow("Seleziona l'area di PokerStars", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Seleziona l'area di PokerStars", 
                     min(1600, display_frame.shape[1]), 
                     min(900, display_frame.shape[0]))
    
    roi = cv2.selectROI("Seleziona l'area di PokerStars", display_frame, fromCenter=False)
    cv2.destroyAllWindows()
    
    if roi[2] == 0 or roi[3] == 0:
        print("\n❌ Selezione annullata.")
        return
    
    # Le coordinate sono già in punti logici perché abbiamo ridimensionato
    left = int(roi[0])
    top = int(roi[1])
    width = int(roi[2])
    height = int(roi[3])
    
    print("\n" + "=" * 60)
    print("✅ COORDINATE SELEZIONATE")
    print("=" * 60)
    print(f"\n   CAPTURE_LEFT = {left}")
    print(f"   CAPTURE_TOP = {top}")
    print(f"   CAPTURE_WIDTH = {width}")
    print(f"   CAPTURE_HEIGHT = {height}")
    
    print("\n📋 Copia queste righe in capture_training_images.py:")
    print(f"""
# Coordinate calibrate
CAPTURE_TOP = {top}
CAPTURE_LEFT = {left}
CAPTURE_WIDTH = {width}
CAPTURE_HEIGHT = {height}
""")
    
    print("\n📋 E in main.py:")
    print(f"""
CAPTURE_CONFIG = {{
    "top": {top},
    "left": {left},
    "width": {width},
    "height": {height}
}}
""")
    
    # Salva anche un'immagine di test della regione selezionata
    print("\n🧪 Test cattura con le nuove coordinate...")
    
    test_monitor = {
        "top": top * RETINA_SCALE,
        "left": left * RETINA_SCALE,
        "width": width * RETINA_SCALE,
        "height": height * RETINA_SCALE,
    }
    
    with mss.mss() as sct:
        test_shot = sct.grab(test_monitor)
        test_frame = np.array(test_shot)
        test_frame = cv2.cvtColor(test_frame, cv2.COLOR_BGRA2BGR)
        cv2.imwrite("calibration_test.png", test_frame)
        print("   Immagine di test salvata: calibration_test.png")
    
    # Mostra preview finale
    preview = cv2.resize(test_frame, (width, height))
    cv2.imshow("Preview della regione selezionata (premi Q per chiudere)", preview)
    print("\n👀 Controlla la preview. Premi Q per chiudere.")
    
    while True:
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cv2.destroyAllWindows()
    print("\n✅ Calibrazione completata!")


if __name__ == "__main__":
    main()
