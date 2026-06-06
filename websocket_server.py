"""
WebSocket Server for Real-Time Game State Broadcasting
Sends poker game state to connected dashboard clients
"""

import asyncio
import json
import websockets
import threading
from datetime import datetime

class GameStateWebSocket:
    """
    WebSocket server that broadcasts game state to connected clients
    """
    
    def __init__(self, host='0.0.0.0', port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.server = None
        self.loop = None
        self.enabled = True
        self.startup_error = None
        self.started_event = threading.Event()
        
    async def register(self, websocket):
        """Register a new client"""
        self.clients.add(websocket)
        print(f"📡 WebSocket client connected. Total clients: {len(self.clients)}")
        
    async def unregister(self, websocket):
        """Unregister a disconnected client"""
        self.clients.discard(websocket)
        print(f"📡 WebSocket client disconnected. Total clients: {len(self.clients)}")
        
    async def handler(self, websocket):
        """Handle WebSocket connection"""
        await self.register(websocket)
        try:
            # Keep connection alive
            async for message in websocket:
                # Echo any received messages (for ping/pong)
                await websocket.send(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)
    
    async def broadcast(self, message):
        """Broadcast message to all connected clients"""
        if self.clients:
            # Create JSON string once
            json_message = json.dumps(message)
            # Send to all clients concurrently
            await asyncio.gather(
                *[client.send(json_message) for client in self.clients],
                return_exceptions=True
            )
    
    def broadcast_sync(self, message):
        """Synchronous broadcast (call from main thread)"""
        if self.enabled and self.loop and self.clients:
            # Schedule broadcast in the event loop
            asyncio.run_coroutine_threadsafe(
                self.broadcast(message),
                self.loop
            )
    
    async def start_server(self):
        """Start WebSocket server"""
        self.server = await websockets.serve(
            self.handler,
            self.host,
            self.port
        )
        print(f"📡 WebSocket server started on ws://{self.host}:{self.port}")
        
    def run_in_thread(self):
        """Run WebSocket server in a separate thread"""
        def run_server():
            # Create new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                # Start server
                self.loop.run_until_complete(self.start_server())
                self.enabled = True
                self.started_event.set()
                # Run event loop
                self.loop.run_forever()
            except Exception as e:
                self.enabled = False
                self.startup_error = e
                self.started_event.set()
                print(f"⚠️  WebSocket disabled: {e}")
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        print("📡 WebSocket server thread started")
        
        # Give server time to start
        import time
        self.started_event.wait(timeout=1.0)

        if self.startup_error:
            return None
        return thread


def create_game_state_message(poker_vision):
    """
    Create game state message from PokerVisionPro instance
    
    Args:
        poker_vision: PokerVisionPro instance
        
    Returns:
        dict: JSON-serializable game state
    """
    # Get current players
    current_players = [p for p in poker_vision.players.values() if p.status != "Folded"]
    
    hero_cards = list(getattr(poker_vision, 'hero_cards', []) or [])
    pot_value = float(poker_vision.game_state.get('pot', 0.0))

    message = {
        "timestamp": datetime.now().isoformat(),
        "hand_id": poker_vision.hand_id,
        "street": poker_vision.game_state.get('street', 'Preflop'),
        "pot": pot_value,
        
        # Hero info
        "hero": {
            "name": next((p.name for p in current_players if p.position == poker_vision.hero_position), "Unknown"),
            "position": poker_vision.hero_position or "Unknown",
            "stack": next((p.bb_current for p in current_players if p.position == poker_vision.hero_position), 0),
            "cards": hero_cards,
            "hand": poker_vision.hero_hand or "Unknown"
        },
        
        # Board cards
        "board": poker_vision.game_state.get('board_cards', []),
        
        # All players
        "players": [
            {
                "name": p.name,
                "position": p.position,
                "stack": p.bb_current,
                "status": p.status,
                "last_action": p.detected_action or "Waiting",
                "is_dealer": p.is_dealer
            }
            for p in current_players
        ],
        
        # GTO suggestion (if available)
        "gto_suggestion": {
            "action": "Calculating..." if not hasattr(poker_vision, 'last_gto_suggestion') else poker_vision.last_gto_suggestion,
            "color": "yellow",
            "reasoning": ""
        },
        
        # Stats
        "stats": {
            "high_bet": poker_vision.high_bet_current_street,
            "raises_count": poker_vision.raises_count,
            "board_count": len(poker_vision.game_state.get('board_cards', []))
        }
    }
    
    return message


# Test
if __name__ == "__main__":
    import time
    
    ws_server = GameStateWebSocket()
    ws_server.run_in_thread()
    
    print("\nWebSocket server running. Press Ctrl+C to stop.\n")
    
    # Simulate game state broadcasts
    try:
        for i in range(10):
            test_message = {
                "timestamp": datetime.now().isoformat(),
                "hand_id": i,
                "street": "Flop",
                "hero": {
                    "name": "MicheleR02",
                    "position": "BTN",
                    "cards": ["As", "Kh"],
                    "hand": "AKo"
                },
                "board": ["Qc", "9h", "2d"],
                "gto_suggestion": {
                    "action": "RAISE 3BB",
                    "color": "green"
                }
            }
            
            ws_server.broadcast_sync(test_message)
            print(f"Broadcasted message {i}")
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\nStopping...")
