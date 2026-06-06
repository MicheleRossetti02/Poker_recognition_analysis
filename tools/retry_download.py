from roboflow import Roboflow
import os
import shutil
import glob

rf = Roboflow(api_key="CUhu9vmliKIKhDxLNMVU")
project = rf.workspace("pokergtobot").project("poker-gto-production")
version = project.version(3)

print("Attempting 'yolov8-pytorch' download for Version 3...")
try:
    dataset = version.download("yolov8-pytorch")
    print("Download complete.")
    
    pt_files = glob.glob(os.path.join(dataset.location, "**/*.pt"), recursive=True)
    if pt_files:
        print(f"Found {len(pt_files)} .pt files: {pt_files}")
        best = pt_files[0]
        shutil.copy2(best, "POKER_GTO_BOT_V3/weights/best.pt")
        print(f"Weights secured at POKER_GTO_BOT_V3/weights/best.pt")
    else:
        print("Still no .pt files found.")

except Exception as e:
    print(f"Error: {e}")
