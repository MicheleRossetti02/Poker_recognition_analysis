from roboflow import Roboflow
import os
import shutil

# Initialize Roboflow
rf = Roboflow(api_key="CUhu9vmliKIKhDxLNMVU")
project = rf.workspace("pokergtobot").project("poker-gto-production")
version = project.version(3)

# Download model/dataset
print("Downloading dataset/model for Version 3...")
try:
    dataset = version.download("yolov8")
    print("Download complete.")
    
    # Check for weights/files
    # Note: version.download("yolov8") usually downloads the dataset in YOLOv8 format.
    # It often does NOT download 'best.pt' unless it was a custom training extraction.
    # However, sometimes Roboflow bundles weights if using certain exports.
    # We will look for .pt files in the downloaded directory.
    
    download_dir = dataset.location
    found_weights = False
    
    for root, dirs, files in os.walk(download_dir):
        for file in files:
            if file.endswith(".pt"):
                source = os.path.join(root, file)
                dest = "Poker_GTO_Brain_V3/weights/best.pt"
                print(f"Found weights file: {source}")
                shutil.copy2(source, dest)
                print(f"Copied to {dest}")
                found_weights = True
                break
        if found_weights:
            break
            
    if not found_weights:
        print("WARNING: No .pt file found in download. The download might be dataset only.")
        print("Required: Please place the trained 'best.pt' file into Poker_GTO_Brain_V3/weights/ manually")
        print("or ensure the Roboflow version includes model weights.")

except Exception as e:
    print(f"Error during download: {e}")
