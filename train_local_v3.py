
import ssl
import certifi
import os
import shutil
from ultralytics import YOLO

# Fix SSL for model download
ssl._create_default_https_context = ssl._create_unverified_context

def main():
    print("Initializing YOLOv11n training on MPS...")
    
    # Check for existing run to resume
    # Check specific deeply nested path where Ultralytics puts it
    last_pt = "runs/detect/runs/poker_v3/train_v11/weights/last.pt"
    
    data_path = os.path.abspath("data.yaml")
    
    resume_mode = False
    model_path = "yolo11n.pt"  # Default start model
    
    if os.path.exists(last_pt):
        print(f"✅ Found existing checkpoint at {last_pt}. Resuming...")
        model_path = last_pt
        resume_mode = True
    else:
        # Initial load with fallback
        try:
            # Check if we can load model object to verify download
            YOLO("yolo11n.pt") 
        except Exception:
            print("⚠️ YOLO11n not found or error, falling back to YOLOv8n")
            model_path = "yolov8n.pt"

    print(f"Training on dataset: {data_path}")
    # Load Model
    # If a previous run exists, we use its weights but start a NEW run to apply stable settings
    if os.path.exists(last_pt):
        print(f"⚠️ Recovering weights from crashed run: {last_pt}")
        model = YOLO(last_pt)
    else:
        model = YOLO(model_path)
    
    # Train (Stable Mode - No RAM Cache)
    results = model.train(
        data=data_path,
        epochs=50,                  
        imgsz=320,                  
        batch=-1,                   
        device='mps',
        # cache='ram',  <-- REMOVED to prevent OOM Crash
        plots=True,
        project='runs/poker_v3',
        name='train_v3_stable',      # New name
        save=True,
        save_period=1,
        exist_ok=True 
    )
    
    # Move weights
    # Try to find best.pt in the results save dir
    src = os.path.join(results.save_dir, "weights", "best.pt")
    dst = "POKER_GTO_BOT_V3/weights/best.pt"
    
    print(f"Training finished. Moving {src} -> {dst}")
    
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print("SUCCESS: Weights deployed to POKER_GTO_BOT_V3.")
    else:
        print(f"ERROR: Source weights not found at {src}")

if __name__ == "__main__":
    main()
