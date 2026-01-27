#!/bin/bash
# Script per monitorare il completamento del training e procedere con auto-labeling

TRAINING_PID=$1
TRAINING_LOG="training_restart.log"

echo "🔍 Monitoraggio training PID: $TRAINING_PID"
echo "📝 Log file: $TRAINING_LOG"

# Aspetta il completamento del training
while kill -0 $TRAINING_PID 2>/dev/null; do
    sleep 30
    # Mostra progresso ogni 30 secondi
    tail -1 $TRAINING_LOG | grep "Epoch" || true
done

echo ""
echo "✅ Training completato!"
echo ""

# Verifica che best.pt esista
if [ -f "runs/detect/train2/weights/best.pt" ]; then
    echo "✅ Modello best.pt trovato"
    echo "📊 Dimensione: $(ls -lh runs/detect/train2/weights/best.pt | awk '{print $5}')"
else
    echo "❌ ERRORE: best.pt non trovato!"
    exit 1
fi

echo ""
echo "🚀 Avvio Auto-Labeling su organized_dataset_clean/..."
echo ""

# Conta le immagini da processare
IMG_COUNT=$(find organized_dataset_clean -type f \( -name "*.jpg" -o -name "*.png" \) | wc -l | tr -d ' ')
echo "📸 Immagini da processare: $IMG_COUNT"

# Esegui auto-labeling
source venv312/bin/activate
python auto_label_massive.py \
    --model runs/detect/train2/weights/best.pt \
    --source organized_dataset_clean \
    --conf 0.25 \
    --output labeled_batch

echo ""
echo "✅ Auto-Labeling completato!"
echo ""
echo "📤 Pronto per upload su Roboflow"
echo "   Comando: roboflow upload <project> labeled_batch/"
