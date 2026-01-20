# Quick Reference - Dealer Button Annotation

## 🔘 Regola d'Oro

> **Annota SOLO il disco del dealer, NON il feltro verde circostante**

---

## ✅ CORRETTO

![Dealer Button Annotation Guide](/Users/michelerossetti/.gemini/antigravity/brain/3096cbdd-d81a-41fe-a9b9-6f17ef4a9286/dealer_button_annotation_1768652936920.png)

**Box tight sul disco:**
- Includi tutto il disco bianco/grigio con la "D"
- Box aderente ai bordi del disco
- Minimo spazio verde visibile
- Forma: quadrato che contiene perfettamente il cerchio

---

## 📏 Specifiche Tecniche

### Cosa Includere
✅ Il disco circolare (bianco/grigio)  
✅ La lettera "D" centrale  
✅ Eventuale bordo 3D del disco  
✅ Ombra immediata del disco (se attaccata)

### Cosa Escludere
❌ Feltro verde del tavolo  
❌ Ombre proiettate sul tavolo  
❌ Carte o chips vicine  
❌ Spazio vuoto attorno al disco

---

## 🎯 Dimensioni Tipiche

- **PokerStars Standard**: 30-40 pixel di lato
- **Forma Box**: Quadrato (YOLO richiede box rettangolari)
- **Toleranza**: ±2-3 pixel di margine OK

---

## 🔍 Best Practice YOLOv8

1. **Tight Bounding** - Il più aderente possibile
2. **Consistenza** - Stesso metodo per tutte le immagini
3. **Visibilità** - Annota solo se la "D" è leggibile
4. **Posizione** - Non importa dove sia sul tavolo, annotalo sempre

---

## ⚡ Quick Tips

- Usa zoom su Roboflow per precisione
- Se il button è parzialmente occluso ma riconoscibile: annotalo
- Se il button è sfocato ma la forma è chiara: annotalo
- Se vedi solo un pezzo \u003c40% del disco: **NON** annotarlo

---

## 🎓 Perché è Importante?

Il dealer button determina la **posizione relativa** dei giocatori, fondamentale per:
- Calcolo GTO ranges
- Identificazione positions (BTN, SB, BB, UTG, etc.)
- Decision making context-aware

**Annotazioni precise = Modello accurato = Migliori decision GTO** 🎯

---

Tieni questo come riferimento durante l'annotazione su Roboflow!
