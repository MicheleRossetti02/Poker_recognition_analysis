# Roboflow Annotation Guide - Poker Vision Assistant

**Guida tecnica per annotare immagini su Roboflow per il training YOLOv8**

---

## 📋 Classi del Dataset

Il dataset contiene **53 classi totali**:
- **Classi 0-51**: Le 52 carte da poker (notazione: `As`, `Kh`, `9d`, etc.)
- **Classe 52**: Dealer Button (`button`)

---

## 🎯 Best Practices Generali YOLOv8

### Principi Fondamentali

1. **Tight Bounding Box** - Il box deve essere il più aderente possibile all'oggetto
2. **Consistenza** - Annota ogni istanza della stessa classe nello stesso modo
3. **Visibilità Minima** - Annota solo se almeno il 30-40% dell'oggetto è visibile
4. **Overlap** - I box possono sovrapporsi (YOLOv8 gestisce bene le occlusioni)

### Regole per Bounding Box

✅ **FARE:**
- Box aderente ai bordi dell'oggetto
- Includere leggere ombre se fanno parte dell'oggetto
- Annotare oggetti parzialmente occlusi (se riconoscibili)
- Mantenere proporzioni corrette (non troppo larghi o stretti)

❌ **NON FARE:**
- Lasciare spazio vuoto significativo attorno all'oggetto
- Includere background o tavolo verde
- Annotare oggetti irriconoscibili o confusi
- Creare box troppo piccoli che tagliano l'oggetto

---

## 🃏 Annotazione Carte da Poker

### Regola Generale
**Il bounding box deve includere SOLO la carta, dal bordo superiore sinistro al bordo inferiore destro.**

### Cosa Includere
✅ Tutta la carta (bordo bianco incluso)  
✅ Leggera ombra se attaccata alla carta  
✅ Carte parzialmente sovrapposte (annota entrambe)

### Cosa Escludere
❌ Tavolo verde attorno  
❌ Riflessi sul tavolo  
❌ Ombre proiettate sul tavolo lontane dalla carta

### Esempi Visivi

#### ✅ CORRETTO - Tight Box
```
┌──────────┐
│  ♠️ A    │  ← Box aderente ai bordi
│          │
│     ♠️   │
│          │
│      A ♠️│
└──────────┘
```

#### ❌ SBAGLIATO - Troppo Spazio
```
┌────────────────┐
│                │  ← Troppo spazio verde
│   ┌────────┐   │
│   │   ♠️ A  │   │
│   │    ♠️   │   │
│   └────────┘   │
│                │
└────────────────┘
```

### Casi Speciali

**Carte Sovrapposte (Board):**
- Annota OGNI carta visibile
- Va bene se i box si sovrappongono leggermente
- Se una carta è occlusa >70%, considera di non annotarla

**Hole Cards (Mano Hero):**
- Annota entrambe le carte separatamente
- Anche se molto vicine, crea 2 box distinti

---

## 🔘 Annotazione Dealer Button

### Regola Principale
**Il bounding box deve includere SOLO il disco del dealer, SENZA il bordo del tavolo.**

### Cosa Includere
✅ Il disco circolare bianco/grigio con la "D"  
✅ L'ombra immediata del disco (se visibile)  
✅ Eventuale bordo 3D del disco stesso

### Cosa Escludere
❌ Il feltro verde del tavolo attorno  
❌ Ombre proiettate sul tavolo lontane dal button  
❌ Carte o chips vicine al button

### Dettagli Tecnici

**Forma del Box:**
- Il button è **circolare**, ma il bounding box sarà **quadrato** (YOLO usa box rettangolari)
- Il box deve essere il **minimo quadrato** che contiene tutto il disco

**Dimensioni Tipiche:**
- Il button su PokerStars ha dimensioni abbastanza consistenti
- Solitamente **30-40 pixel** di lato (dipende dalla risoluzione)

### Esempi Visivi

#### ✅ CORRETTO - Solo Disco
```
Tavolo verde
    ┌────┐
    │ D  │  ← Box tight sul disco
    └────┘
Tavolo verde
```

#### ❌ SBAGLIATO - Include Troppo Tavolo
```
Tavolo verde
  ┌────────┐
  │        │
  │  ┌──┐  │  ← Troppo spazio verde
  │  │D │  │
  │  └──┘  │
  │        │
  └────────┘
```

### Posizioni del Button

Il dealer button può apparire in diverse posizioni attorno al tavolo:
- **Annotalo SEMPRE**, indipendentemente dalla posizione
- Utile per identificare la posizione relativa (GTO dipende da questo!)
- Se il button è parzialmente fuori schermo ma la "D" è visibile, annotalo comunque

---

## 🎨 Workflow Annotazione su Roboflow

### Step-by-Step

1. **Upload Immagini**
   - Vai su https://app.roboflow.com
   - Workspace: `pokergtobot` → Project: `poker-gto`
   - Upload batch da `dataset/raw/session_*/`

2. **Annotazione**
   - Click "Annotate" su immagine
   - Seleziona tool "Bounding Box" (non polygon)
   - Per ogni carta/button:
     - Click e drag per creare box
     - Seleziona classe corretta dal dropdown
     - Assicurati box sia tight

3. **Controllo Qualità**
   - Rivedi 2-3 immagini già annotate
   - Verifica consistenza dimensioni box
   - Controlla che nessuna carta sia stata saltata

4. **Salvataggio**
   - Click "Save" dopo ogni immagine
   - Roboflow salva automaticamente ogni modifica

---

## 📊 Metriche di Qualità

### Target Annotazione

**Per Immagine Media (Flop):**
- 2 Hole cards (Hero)
- 3 Community cards (Board)
- 1 Dealer button
- **Totale: 6 annotations**

**Qualità Accettabile:**
- Box precision: >95% (box aderente)
- Recall: 100% (tutte le carte annotate)
- Class accuracy: 100% (classe corretta)

### Auto-Controllo

Fai queste domande per ogni immagine:

✓ Tutte le carte visibili sono annotate?  
✓ I box sono tight senza spazio vuoto?  
✓ La classe di ogni carta è corretta?  
✓ Il button è annotato (se visibile)?  
✓ Non ho incluso tavolo verde nei box?

---

## 🚀 Tips per Velocità

1. **Hotkeys Roboflow**
   - `1-9`: Seleziona classe rapida
   - `Enter`: Salva e vai alla prossima
   - `Ctrl+Z`: Undo ultimo box

2. **Pattern Recognition**
   - Annota sempre nello stesso ordine (es: hole → board → button)
   - Usa zoom per carte piccole
   - Salta immagini troppo sfocate/inutilizzabili

3. **Batch Consistency**
   - Annota 10-20 immagini simili consecutivamente
   - Mantieni la stessa mentalità di tight/loose boxing

---

## 🎯 Checklist Finale

Prima di versionare il dataset, verifica:

- [ ] Tutte le immagini hanno almeno 1 annotazione
- [ ] Le carte sono annotate con classe corretta
- [ ] Il button è annotato quando visibile
- [ ] Nessun box include eccessivo background verde
- [ ] Carte occluse >70% non sono annotate
- [ ] Sample check: 10 immagini random sono corrette

---

## 📚 Riferimenti

- **YOLO Annotation Guidelines**: https://docs.ultralytics.com/datasets/detect/
- **Roboflow Docs**: https://docs.roboflow.com/annotate

---

**Buon lavoro con le annotazioni! Ricorda: consistenza e precisione sono fondamentali per un modello accurato.** 🎴🤖
