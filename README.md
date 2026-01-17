# Poker Vision Assistant

Real-time poker card recognition system using YOLOv8 and computer vision for poker analysis.

## Features

- **Real-time Card Recognition**: YOLOv8-based detection of poker cards
- **Screen Capture**: Optimized for macOS Retina displays with MPS acceleration
- **OCR Game State**: Reads pot size and stack information
- **HUD Interface**: PyQt6 dashboard showing cards, equity, and game info
- **Training Pipeline**: Complete workflow for custom YOLO model training

## Project Structure

```
├── main.py                      # Main coordinator with GUI
├── card_recognizer.py           # YOLO card recognition module
├── screen_capture.py            # Screen capture for macOS
├── game_state_reader.py         # OCR for pot/stack reading
├── gui_dashboard.py             # PyQt6 HUD interface
├── train.py                     # YOLO training script
├── capture_training_images.py   # Tool to capture training data
├── calibrate_screen.py          # Interactive screen calibration
└── dataset/
    └── data.yaml                # YOLO dataset configuration
```

## Requirements

- macOS with Apple Silicon (M1/M2)
- Python 3.12+
- Screen recording permissions

## Installation

```bash
# Create virtual environment
python3.12 -m venv venv312
source venv312/bin/activate

# Install dependencies
pip install ultralytics roboflow pyqt6 mss opencv-python pytesseract
```

## Usage

### 1. Training the Model

```bash
# Capture training images
python capture_training_images.py

# Train YOLO model
python train.py
```

### 2. Running the HUD

```bash
python main.py
```

## Configuration

Edit coordinates in `main.py`:
- `CAPTURE_CONFIG`: Screen capture region
- `POT_REGION`: OCR area for pot
- `STACK_REGION`: OCR area for stack

## Model Training

The project uses YOLOv8 nano for fast inference:
- **Input**: 640x640 images
- **Classes**: 52 (all poker cards)
- **Device**: MPS (Apple Silicon Metal)
- **Epochs**: 100

Trained model saved as `best.pt` (~18MB).

## License

MIT
