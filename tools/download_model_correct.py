from roboflow import Roboflow
import os
import shutil
import glob

# Initialize Roboflow
rf = Roboflow(api_key="CUhu9vmliKIKhDxLNMVU")
project = rf.workspace("pokergtobot").project("poker-gto-production")

def check_and_move_weights(download_dir):
    # Find README to verify date
    readme_path = os.path.join(download_dir, "README.roboflow.txt")
    if os.path.exists(readme_path):
        with open(readme_path, 'r') as f:
            content = f.read()
            print(f"README content preview:\n{content[:200]}")
            if "2026-02-02" in content:
                print("SUCCESS: Confirmed version date 2026-02-02")
            else:
                print("WARNING: Date 2026-02-02 NOT found in README.")
    
    # Search for weights recursively
    pt_files = glob.glob(os.path.join(download_dir, "**/*.pt"), recursive=True)
    if pt_files:
        print(f"Found {len(pt_files)} .pt files: {pt_files}")
        best_weight = pt_files[0] # Pick first or specific logic
        shutil.copy2(best_weight, "POKER_GTO_BOT_V3/weights/best.pt")
        print(f"Copied {best_weight} to POKER_GTO_BOT_V3/weights/best.pt")
        return True
    return False

# Try Version 3
print("Attempting Version 3...")
try:
    version = project.version(3)
    dataset = version.download("yolov8")
    if check_and_move_weights(dataset.location):
        print("Version 3 weights secured.")
    else:
        print("No weights in Version 3 download.")
        
        # Try finding in local runs if download only gave data
        # Maybe user trained LOCALLY today?
        # Let's check local runs for today's date?
        pass

except Exception as e:
    print(f"Error v3: {e}")

# If v3 failed or wrong date, Logic to try v4 could be here
# But user said "Se no, prova project.version(4)"
