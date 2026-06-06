
import cv2
import torch
import numpy as np
import mss
import time
import easyocr
import ssl
import certifi
from ultralytics import YOLO

# Fix SSL
ssl._create_default_https_context = ssl._create_unverified_context

# Config
MODEL_PATH = "POKER_GTO_BOT_V3/weights/best.pt"
CONF_THRESHOLD = 0.5
DEVICE = 'mps' if torch.backends.mps.is_available() else 'cpu'

# Config logic
STREET_MAP = {0: "Preflop", 3: "Flop", 4: "Turn", 5: "River"}

class PokerVision:
    def __init__(self):
        print(f"Initializing PokerVision V3 on {DEVICE}...")
        self.model = YOLO(MODEL_PATH)
        self.model.to(DEVICE)
        self.reader = easyocr.Reader(['en'], gpu=(DEVICE=='mps'))
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]
        
        # State
        self.players = {} # id -> {name, bb, status, pos, last_bb_check}
        self.game_state = {
            "street": "Preflop",
            "board_count": 0,
            "pot": 0 # Not implemented fully yet
        }
        
    def capture(self):
        sct_img = self.sct.grab(self.monitor)
        img = np.array(sct_img)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def parse_text(self, crop):
        try:
            res = self.reader.readtext(crop, detail=0)
            name, bb = "Unknown", 0.0
            for t in res:
                t_clean = t.replace('BB','').strip()
                try:
                    bb = float(t_clean)
                except:
                    if len(t)>2: name = t
            return name, bb
        except: return "Err", 0.0

    def process(self):
        frame = self.capture()
        results = self.model(frame, conf=CONF_THRESHOLD, verbose=False)[0]
        
        # 1. Process Detections
        # Map: class->list of boxes
        dets = {n: [] for n in results.names.values()}
        for box in results.boxes:
            cls = int(box.cls[0])
            name = results.names[cls]
            dets[name].append(box.xyxy[0].cpu().numpy())
            
        # 2. Street Recognition
        # Count cards (classes 0-51, assuming 52+ are UI)
        # Filter detections that are 'card' (name length 2 usually)
        # And are in center area (simple heuristic: dist from center < 30% width)
        h, w = frame.shape[:2]
        center = (w/2, h/2)
        
        board_cards = 0
        for box in results.boxes:
             cls = int(box.cls[0])
             name = results.names[cls]
             # Check if card (len 2)
             if len(name) == 2 and name not in ['rc','tc']: # tc is 10 of clubs but len 2. rc/tc might be special?
                 # Check pos
                 bx = (box.xyxy[0][0]+box.xyxy[0][2])/2
                 by = (box.xyxy[0][1]+box.xyxy[0][3])/2
                 # Center zone radius approx
                 if abs(bx-center[0]) < w*0.3 and abs(by-center[1]) < h*0.3:
                     board_cards += 1
        
        # Limit board cards to 5 max
        board_cards = min(5, board_cards)
        new_street = STREET_MAP.get(board_cards, "Unknown")
        
        # Detect Street Change
        street_changed = False
        if new_street != self.game_state['street']:
            print(f"--- STREET CHANGE: {self.game_state['street']} -> {new_street} ---")
            self.game_state['street'] = new_street
            street_changed = True

        # 3. Players
        # Parse player_info
        p_infos = dets.get('player_info', []) # name might be 'player_info' or 'player-info' check names
        # Actually user said "player_info"
        if not p_infos and 'player-info' in dets: p_infos = dets['player-info']

        # Sort clockwise
        def angle(b): return np.arctan2((b[1]+b[3])/2 - center[1], (b[0]+b[2])/2 - center[0])
        p_infos.sort(key=angle)
        
        dealer_btns = dets.get('dealer_btn', [])
        dealer_box = dealer_btns[0] if dealer_btns else None
        dealer_idx = -1
        
        current_data = []
        
        for idx, box in enumerate(p_infos):
            pid = f"P{idx+1}"
            
            # Dealer Check
            is_dealer = False
            if dealer_box is not None:
                # Dist check
                p_cent = ((box[0]+box[2])/2, (box[1]+box[3])/2)
                d_cent = ((dealer_box[0]+dealer_box[2])/2, (dealer_box[1]+dealer_box[3])/2)
                if ((p_cent[0]-d_cent[0])**2 + (p_cent[1]-d_cent[1])**2)**0.5 < 150:
                    is_dealer = True
                    dealer_idx = idx

            # Rival Active (In-Play vs Folded)
            # Check overlap/proximity with 'rivals_card' (class 52-56 region?)
            # User said "rivals_card".
            status = "Folded"
            rival_cards = dets.get('rivals_card', [])
            for rc in rival_cards:
                 r_cent = ((rc[0]+rc[2])/2, (rc[1]+rc[3])/2)
                 p_cent = ((box[0]+box[2])/2, (box[1]+box[3])/2)
                 if ((r_cent[0]-p_cent[0])**2 + (r_cent[1]-p_cent[1])**2)**0.5 < 200:
                     status = "Active"
                     break
            
            # OCR (every 60 frames or on init)
            # Simplified: Run every time for test (or use memory)
            # Memory check
            prev = self.players.get(pid, {'bb':0, 'name':'?'})
            
            # Only run OCR if unknown name or street changed (to get new stack)
            # "Il sistema deve memorizzare i BB al Flop... ricalcolare differenza"
            # So updating BB is crucial.
            # Run OCR:
            crop = frame[int(box[1]-5):int(box[3]+5), int(box[0]-5):int(box[2]+5)]
            name, bb_val = self.parse_text(crop)
            if name == "Unknown": name = prev['name']
            if bb_val == 0.0: bb_val = prev['bb']
            
            # Bet Sizing Logic
            # If street changed, calc diff
            if street_changed and prev['bb'] > 0:
                diff = prev['bb'] - bb_val
                if diff > 0.1: # Threshold
                    print(f"   >>> {name} BET: {diff:.1f} BB")

            current_data.append({
                'id': pid,
                'name': name,
                'bb': bb_val,
                'status': status,
                'is_dealer': is_dealer
            })

        # Assign Positions
        if dealer_idx != -1:
            n = len(current_data)
            for i, p in enumerate(current_data):
                off = (i - dealer_idx) % n
                if off == 0: p['pos'] = 'BTN'
                elif off == 1: p['pos'] = 'SB'
                elif off == 2: p['pos'] = 'BB'
                else: p['pos'] = f"Pos+{off}"
        else:
            for p in current_data: p['pos'] = '?'

        # Update Memory
        for p in current_data:
            self.players[p['id']] = p

        # Print
        print(f"\nStates ({self.game_state['street']} - {board_cards} Cards)")
        for p in current_data:
            print(f"{p['id']}: {p['name']} | {p['bb']}BB | {p['status']} | {p['pos']}")

    def run(self):
        print("Running V3 Logic...")
        while True:
            self.process()
            # time.sleep(0.5)

if __name__ == "__main__":
    PokerVision().run()
