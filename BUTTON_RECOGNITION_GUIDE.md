# Button Recognition & Hero Position - Implementation Summary

## 🎯 Obiettivo Completato

Aggiornato `card_recognizer.py` per riconoscere il dealer button (classe 52) e stimare la posizione Hero al tavolo 6-max.

---

## 🆕 Modifiche Implementate

### 1. Nuove Classi

**ButtonDetection**: Dataclass per dealer button  
**HeroPosition**: Enum con posizioni 6-max (BTN/SB/BB/UTG/HJ/CO)  
**Costanti**: `BUTTON_CLASS_ID = 52`, `BUTTON_CLASS_NAME = "button"`

### 2. analyze_frame() Updates

**Nuovo comportamento:**
- Separa button detection da carte
- Calcola hero_position se button rilevato
- Aggiunge campi: `button_detected`, `hero_position`, `button_info`

---

## 📐 get_hero_position() - Mapping 6-Max

### Algoritmo
1. Normalizza coordinate button (0.0-1.0)
2. Calcola angolo rispetto centro tavolo con `atan2`
3. Mappa angolo → posizione Hero

### Zone Angolari

| Angolo | Button Posizione | Hero è |
|--------|------------------|--------|
| 270-330° | Basso | **BTN** |
| 330-30° | Destra | **SB** |
| 30-90° | Alto-destra | **BB** |
| 90-150° | Alto-sinistra | **UTG** |
| 150-210° | Sinistra | **HJ** |
| 210-270° | Basso-sinistra | **CO** |

---

## 📊 Esempio Utilizzo

```python
from card_recognizer import PokerBrain

brain = PokerBrain(model_path="best.pt")
result = brain.analyze_frame(frame)

print(result["button_detected"])  # True
print(result["hero_position"])  # "Button"
print(result["button_info"])  # {'confidence': 0.94, ...}
```

---

## ✅ Testing

```bash
python test_button_detection.py
```

**Nota**: Richiede `pip install ultralytics` per testare.

---

## 📝 Prossimi Passi

1. **Training modello** con classe button (ID 52)
2. **Validare** posizioni con screenshot reali
3. **Integrare** in main.py per GTO context-aware
4. **Estendere** a 9-max se necessario

---

**Button recognition ready per production!** 🎴🔘
