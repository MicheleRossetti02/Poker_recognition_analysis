"""
Screenshot Analyzer - Standalone GTO Analysis Tool
Analyze a poker screenshot and get GTO recommendations
"""

import cv2
import numpy as np
from ultralytics import YOLO
import argparse
from gto_engine import get_action, normalize_hand, get_hand_strength

# Config
MODEL_PATH = "POKER_GTO_BOT_V3/weights/best.pt"
CONF_THRESHOLD = 0.35

def analyze_screenshot(image_path):
    """
    Analyze a poker screenshot
    
    Args:
        image_path: Path to screenshot image
    
    Returns:
        dict: Analysis results
    """
    print("\n" + "="*70)
    print("🃏 POKER SCREENSHOT ANALYZER")
    print("="*70)
    print(f"\nLoading image: {image_path}")
    
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ Error: Could not load image from {image_path}")
        return None
    
    h, w = img.shape[:2]
    print(f"Image size: {w}x{h}")
    
    # Load model
    print(f"Loading model: {MODEL_PATH}")
    model = YOLO(MODEL_PATH)
    
    # Run inference
    print(f"Running detection (conf={CONF_THRESHOLD})...")
    results = model(img, conf=CONF_THRESHOLD, verbose=False)[0]
    
    # Parse detections
    dets = {n: [] for n in results.names.values()}
    for box in results.boxes:
        cls = int(box.cls[0])
        name = results.names[cls]
        bbox = box.xyxy[0].cpu().numpy()
        conf = float(box.conf[0])
        dets[name].append({'bbox': bbox, 'conf': conf})
    
    print(f"\n📊 Detected {len(results.boxes)} objects")
    
    # Detect cards
    all_cards = []
    hero_cards = []
    board_cards = []
    
    for box in results.boxes:
        cls = int(box.cls[0])
        name = results.names[cls]
        conf = float(box.conf[0])
        
        # Check if it's a card
        if len(name) == 2 or name in ['Tc', 'Th', 'Ts', 'Td']:
            bbox = box.xyxy[0].cpu().numpy()
            by = (bbox[1] + bbox[3]) / 2
            bx = (bbox[0] + bbox[2]) / 2
            
            card_info = {
                'name': name,
                'conf': conf,
                'x': bx,
                'y': by,
                'y_pct': (by / h) * 100
            }
            
            all_cards.append(card_info)
            
            # Hero cards (bottom 50%)
            if by > h * 0.5:
                hero_cards.append(card_info)
            # Board cards (center)
            elif abs(bx - w/2) < w*0.3 and abs(by - h/2) < h*0.3:
                board_cards.append(card_info)
    
    # Print results
    print(f"\n🔍 CARD DETECTION:")
    print(f"   Total cards: {len(all_cards)}")
    print(f"   Hero cards: {len(hero_cards)}")
    print(f"   Board cards: {len(board_cards)}")
    
    if all_cards:
        print(f"\n📋 ALL DETECTED CARDS:")
        for card in all_cards:
            marker = "✅ HERO" if card['y_pct'] > 50 else "🃏 BOARD"
            print(f"   {marker} {card['name']:4} conf={card['conf']:.2f} y={card['y']:.0f} ({card['y_pct']:.1f}%)")
    
    # Analyze hero hand
    if len(hero_cards) >= 2:
        # Sort by position and take first 2
        hero_cards_sorted = sorted(hero_cards, key=lambda c: c['x'])[:2]
        card1 = hero_cards_sorted[0]['name']
        card2 = hero_cards_sorted[1]['name']
        
        hero_hand = normalize_hand(card1, card2)
        hand_strength = get_hand_strength(hero_hand)
        
        print(f"\n👤 HERO HAND:")
        print(f"   Cards: {card1} {card2}")
        print(f"   Normalized: {hero_hand}")
        print(f"   Strength: {hand_strength}")
        
        # Get GTO recommendation (assume BTN, no action before us)
        positions = ['BTN', 'CO', 'MP', 'UTG', 'SB', 'BB']
        print(f"\n🎯 GTO RECOMMENDATIONS:\")
        for pos in positions:
            suggestion = get_action(pos, hero_hand, [])
            color = '🟢' if 'RAISE' in suggestion else ('🟡' if 'CALL' in suggestion else '🔴')
            print(f"   {color} {pos:6} → {suggestion}")
        
        return {
            'hero_hand': hero_hand,
            'hero_cards': [card1, card2],
            'board_cards': [c['name'] for c in board_cards],
            'all_cards': all_cards,
            'hand_strength': hand_strength
        }
    else:
        print(f"\n⚠️  Could not detect hero hand (found {len(hero_cards)} cards)")
        if len(hero_cards) == 1:
            print(f"   Detected: {hero_cards[0]['name']}")
        
        return {
            'hero_hand': None,
            'board_cards': [c['name'] for c in board_cards],
            'all_cards': all_cards
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze poker screenshot')
    parser.add_argument('image', help='Path to screenshot image')
    parser.add_argument('--conf', type=float, default=0.35, help='Confidence threshold')
    
    args = parser.parse_args()
    
    CONF_THRESHOLD = args.conf
    
    result = analyze_screenshot(args.image)
    
    print("\n" + "="*70)
    print("✅ Analysis complete!")
    print("="*70 + "\n")
