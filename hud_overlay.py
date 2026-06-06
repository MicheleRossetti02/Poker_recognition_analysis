"""
HUD Overlay - PyQt6 Implementation
Transparent overlay for displaying GTO suggestions in real-time
More stable on macOS than tkinter
"""

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
import sys

class GTOOverlay(QWidget):
    """Transparent overlay window using PyQt6"""
    
    def __init__(self, window_bounds=None):
        # Create QApplication if it doesn't exist
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        else:
            self.app = QApplication.instance()
        
        super().__init__()
        
        # Store window bounds
        self.window_bounds = window_bounds
        
        # Current suggestion data
        self.suggestion = {
            'text': 'Waiting...',
            'x': 100,
            'y': 100,
            'width': 200,
            'height': 100,
            'color': QColor(0, 255, 0, 180)  # Green with transparency
        }
        
        self.visible = True
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        # Window flags for transparent, always-on-top overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        
        # Make window transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # Set geometry based on window bounds
        if self.window_bounds:
            # Position on poker window
            self.setGeometry(
                self.window_bounds['x'],
                self.window_bounds['y'],
                self.window_bounds['width'],
                self.window_bounds['height']
            )
        else:
            # Fallback to fullscreen
            screen = self.app.primaryScreen().geometry()
            self.setGeometry(screen)
        
        # Show window
        self.show()
    
    def paintEvent(self, event):
        """Paint the overlay"""
        if not self.visible:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get suggestion data
        data = self.suggestion
        x, y, w, h = data['x'], data['y'], data['width'], data['height']
        color = data['color']
        text = data['text']

        if w <= 0 or h <= 0:
            return
        
        # Draw dashed rectangle around card area
        pen = QPen(color, 4, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(QRect(x, y, w, h))
        
        # Draw text background
        text_y = max(0, y - 50)
        text_h = 40
        
        painter.fillRect(QRect(x, text_y, w, text_h), color)
        
        # Draw text
        painter.setPen(QPen(QColor(0, 0, 0, 255)))  # Black text
        font = QFont('Arial', 16, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRect(x, text_y, w, text_h), Qt.AlignmentFlag.AlignCenter, text)
    
    def update_suggestion(self, text, x, y, width, height, color='green'):
        """
        Update the suggestion display
        
        Args:
            text: str - Suggestion text ('RAISE 3BB', 'FOLD', etc.)
            x, y: int - Position of hero card area
            width, height: int - Size of card area
            color: str - Border color ('green', 'red', 'yellow')
        """
        # Convert color string to QColor
        color_map = {
            'green': QColor(0, 255, 0, 180),
            'yellow': QColor(255, 255, 0, 180),
            'red': QColor(255, 0, 0, 180),
            'orange': QColor(255, 165, 0, 180)
        }
        
        x = max(0, int(x))
        y = max(0, int(y))
        width = max(40, int(width))
        height = max(30, int(height))

        # Clamp to current overlay geometry
        if self.width() > 0:
            x = min(x, max(0, self.width() - width))
        if self.height() > 0:
            y = min(y, max(0, self.height() - height))

        self.suggestion = {
            'text': text,
            'x': x,
            'y': y,
            'width': width,
            'height': height,
            'color': color_map.get(color, QColor(0, 255, 0, 180))
        }
        
        # Trigger repaint
        self.update()
    
    def hide_overlay(self):
        """Hide the overlay"""
        self.visible = False
        self.update()
    
    def show_overlay(self):
        """Show the overlay"""
        self.visible = True
        self.update()
    
    def reposition(self, window_bounds):
        """Reposition overlay to match window bounds"""
        if window_bounds:
            self.window_bounds = window_bounds
            self.setGeometry(
                window_bounds['x'],
                window_bounds['y'],
                window_bounds['width'],
                window_bounds['height']
            )
    
    def start(self):
        """Start the overlay (called from main thread)"""
        # Process events to show window
        self.app.processEvents()
    
    def stop(self):
        """Stop and close the overlay"""
        self.close()
        # Don't quit app as it might be used elsewhere

# Test
if __name__ == "__main__":
    import time
    
    print("Starting HUD Overlay Test...")
    print("You should see a transparent window with a green box.")
    print("Press Ctrl+C to exit.")
    
    hud = GTOOverlay()
    hud.start()
    
    try:
        # Simulate updates
        for i in range(100):
            hud.update_suggestion(
                f"RAISE {i%5+2}BB",
                100 + i*2,
                100,
                300,
                150,
                'green' if i%3 == 0 else ('yellow' if i%3 == 1 else 'red')
            )
            time.sleep(0.5)
            QApplication.processEvents()
    except KeyboardInterrupt:
        print("\nStopping HUD...")
        hud.stop()
