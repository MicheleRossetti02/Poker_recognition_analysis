"""
GUI Dashboard - Poker Vision HUD
=================================
Interfaccia grafica stile HUD per visualizzare carte, pot e probabilità.
Design scuro ottimizzato per uso su secondo monitor.
"""

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QPalette, QColor
import sys
from typing import Dict, Any, List


# ============================================================================
# STILI CSS
# ============================================================================

DARK_STYLE = """
QMainWindow {
    background-color: #1a1a2e;
}

QWidget {
    background-color: #1a1a2e;
    color: #eaeaea;
    font-family: 'SF Pro Display', 'Segoe UI', Arial;
}

QLabel {
    color: #eaeaea;
}

QFrame {
    background-color: #16213e;
    border-radius: 12px;
    border: 1px solid #0f3460;
}

.card-label {
    background-color: #0f3460;
    border-radius: 8px;
    padding: 10px;
    font-size: 24px;
    font-weight: bold;
    min-width: 60px;
    min-height: 80px;
}

.section-title {
    color: #e94560;
    font-size: 14px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 2px;
}

.equity-label {
    color: #00ff88;
    font-size: 72px;
    font-weight: bold;
}

.pot-value {
    color: #ffd700;
    font-size: 28px;
    font-weight: bold;
}

.action-label {
    color: #00d4ff;
    font-size: 18px;
}

.stage-label {
    color: #e94560;
    font-size: 16px;
    font-weight: bold;
}
"""

# Colori per i semi delle carte
SUIT_COLORS = {
    'h': '#ff4757',  # Cuori - Rosso
    'd': '#3498db',  # Quadri - Blu  
    'c': '#2ecc71',  # Fiori - Verde
    's': '#ecf0f1',  # Picche - Bianco
}


class CardWidget(QFrame):
    """Widget per visualizzare una singola carta."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(45, 65)
        self.setMaximumSize(55, 75)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.rank_label = QLabel("?")
        self.rank_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rank_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        
        self.suit_label = QLabel("")
        self.suit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.suit_label.setFont(QFont("Arial", 14))
        
        layout.addWidget(self.rank_label)
        layout.addWidget(self.suit_label)
        
        self.set_card(None)
    
    def set_card(self, card: str = None):
        """Imposta la carta da visualizzare (es: 'Ah', 'Kd')."""
        if card and len(card) >= 2:
            rank = card[0]
            suit = card[1].lower()
            
            # Simboli Unicode per i semi
            suit_symbols = {'h': '♥', 'd': '♦', 'c': '♣', 's': '♠'}
            suit_symbol = suit_symbols.get(suit, '?')
            
            # Colore del seme
            color = SUIT_COLORS.get(suit, '#ffffff')
            
            self.rank_label.setText(rank)
            self.rank_label.setStyleSheet(f"color: {color}; background: transparent;")
            
            self.suit_label.setText(suit_symbol)
            self.suit_label.setStyleSheet(f"color: {color}; background: transparent;")
            
            self.setStyleSheet("""
                QFrame {
                    background-color: #ffffff;
                    border-radius: 8px;
                    border: 2px solid #333;
                }
            """)
        else:
            # Carta vuota/placeholder
            self.rank_label.setText("?")
            self.rank_label.setStyleSheet("color: #555; background: transparent;")
            self.suit_label.setText("")
            self.setStyleSheet("""
                QFrame {
                    background-color: #2a2a4a;
                    border-radius: 8px;
                    border: 2px dashed #444;
                }
            """)


class SectionFrame(QFrame):
    """Frame con titolo per una sezione del dashboard."""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #16213e;
                border-radius: 12px;
                border: 1px solid #0f3460;
                padding: 10px;
            }
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 10, 15, 15)
        self.main_layout.setSpacing(10)
        
        # Titolo sezione
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.title_label.setStyleSheet("""
            color: #e94560;
            text-transform: uppercase;
            letter-spacing: 2px;
            background: transparent;
        """)
        self.main_layout.addWidget(self.title_label)
        
        # Container per il contenuto
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        self.main_layout.addWidget(self.content_widget)
    
    def add_widget(self, widget: QWidget):
        """Aggiunge un widget al contenuto della sezione."""
        self.content_layout.addWidget(widget)


class PokerDashboard(QMainWindow):
    """
    Dashboard principale per il Poker Vision Assistant.
    
    Visualizza:
    - Community Cards (Board)
    - Hero's Hole Cards
    - Win Probability (Equity)
    - Pot Size e Game Info
    """
    
    # Segnale per aggiornare i dati dal worker thread
    update_signal = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("♠ Poker Vision HUD ♠")
        self.setMinimumSize(320, 450)
        self.resize(350, 500)
        
        # Stile scuro
        self.setStyleSheet(DARK_STYLE)
        
        # Widget centrale
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # === SEZIONE BOARD (Community Cards) ===
        self.board_section = SectionFrame("Community Board")
        self.board_cards: List[CardWidget] = []
        for i in range(5):
            card = CardWidget()
            self.board_cards.append(card)
            self.board_section.add_widget(card)
        self.board_section.content_layout.addStretch()
        
        # Stage label
        self.stage_label = QLabel("Preflop")
        self.stage_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.stage_label.setStyleSheet("color: #e94560; background: transparent;")
        self.board_section.content_layout.addWidget(self.stage_label)
        
        main_layout.addWidget(self.board_section)
        
        # === SEZIONE CENTRALE (Hand + Equity) ===
        center_widget = QWidget()
        center_widget.setStyleSheet("background: transparent;")
        center_layout = QHBoxLayout(center_widget)
        center_layout.setSpacing(20)
        
        # My Hand
        self.hand_section = SectionFrame("My Hand")
        self.hand_cards: List[CardWidget] = []
        for i in range(2):
            card = CardWidget()
            self.hand_cards.append(card)
            self.hand_section.add_widget(card)
        self.hand_section.content_layout.addStretch()
        
        # Equity Display
        self.equity_section = SectionFrame("Win Probability")
        
        self.equity_label = QLabel("--")
        self.equity_label.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        self.equity_label.setStyleSheet("color: #00ff88; background: transparent;")
        self.equity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.equity_section.add_widget(self.equity_label)
        
        self.equity_suffix = QLabel("%")
        self.equity_suffix.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.equity_suffix.setStyleSheet("color: #00ff88; background: transparent;")
        self.equity_section.add_widget(self.equity_suffix)
        
        center_layout.addWidget(self.hand_section, 1)
        center_layout.addWidget(self.equity_section, 1)
        
        main_layout.addWidget(center_widget)
        
        # === SEZIONE GAME INFO ===
        self.info_section = SectionFrame("Game Info")
        
        # Pot Size
        pot_container = QWidget()
        pot_container.setStyleSheet("background: transparent;")
        pot_layout = QVBoxLayout(pot_container)
        pot_layout.setContentsMargins(0, 0, 0, 0)
        pot_layout.setSpacing(2)
        
        pot_title = QLabel("POT")
        pot_title.setFont(QFont("Arial", 10))
        pot_title.setStyleSheet("color: #888; background: transparent;")
        
        self.pot_label = QLabel("$0")
        self.pot_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.pot_label.setStyleSheet("color: #ffd700; background: transparent;")
        
        pot_layout.addWidget(pot_title)
        pot_layout.addWidget(self.pot_label)
        
        # Stack Size
        stack_container = QWidget()
        stack_container.setStyleSheet("background: transparent;")
        stack_layout = QVBoxLayout(stack_container)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(2)
        
        stack_title = QLabel("STACK")
        stack_title.setFont(QFont("Arial", 10))
        stack_title.setStyleSheet("color: #888; background: transparent;")
        
        self.stack_label = QLabel("$0")
        self.stack_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.stack_label.setStyleSheet("color: #00d4ff; background: transparent;")
        
        stack_layout.addWidget(stack_title)
        stack_layout.addWidget(self.stack_label)
        
        # Action Detected
        action_container = QWidget()
        action_container.setStyleSheet("background: transparent;")
        action_layout = QVBoxLayout(action_container)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(2)
        
        action_title = QLabel("LAST ACTION")
        action_title.setFont(QFont("Arial", 10))
        action_title.setStyleSheet("color: #888; background: transparent;")
        
        self.action_label = QLabel("Waiting...")
        self.action_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.action_label.setStyleSheet("color: #00d4ff; background: transparent;")
        
        action_layout.addWidget(action_title)
        action_layout.addWidget(self.action_label)
        
        self.info_section.add_widget(pot_container)
        self.info_section.add_widget(stack_container)
        self.info_section.add_widget(action_container)
        self.info_section.content_layout.addStretch()
        
        main_layout.addWidget(self.info_section)
        
        # === SEZIONE STRATEGY (Position + Hand Strength) ===
        self.strategy_section = SectionFrame("Strategy Info")
        
        # Position
        pos_container = QWidget()
        pos_container.setStyleSheet("background: transparent;")
        pos_layout = QVBoxLayout(pos_container)
        pos_layout.setContentsMargins(0, 0, 0, 0)
        pos_layout.setSpacing(2)
        
        pos_title = QLabel("POSITION")
        pos_title.setFont(QFont("Arial", 10))
        pos_title.setStyleSheet("color: #888; background: transparent;")
        
        self.pos_label = QLabel("Unknown")
        self.pos_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.pos_label.setStyleSheet("color: #00d4ff; background: transparent;")
        
        pos_layout.addWidget(pos_title)
        pos_layout.addWidget(self.pos_label)
        
        # Hand Strength
        hand_str_container = QWidget()
        hand_str_container.setStyleSheet("background: transparent;")
        hand_str_layout = QVBoxLayout(hand_str_container)
        hand_str_layout.setContentsMargins(0, 0, 0, 0)
        hand_str_layout.setSpacing(2)
        
        hand_str_title = QLabel("HAND")
        hand_str_title.setFont(QFont("Arial", 10))
        hand_str_title.setStyleSheet("color: #888; background: transparent;")
        
        self.hand_strength_label = QLabel("--")
        self.hand_strength_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.hand_strength_label.setStyleSheet("color: #ffd700; background: transparent;")
        
        hand_str_layout.addWidget(hand_str_title)
        hand_str_layout.addWidget(self.hand_strength_label)
        
        self.strategy_section.add_widget(pos_container)
        self.strategy_section.add_widget(hand_str_container)
        self.strategy_section.content_layout.addStretch()
        
        main_layout.addWidget(self.strategy_section)
        
        # Status bar
        self.status_label = QLabel("🔴 Waiting for data...")
        self.status_label.setStyleSheet("color: #666; font-size: 11px; background: transparent;")
        main_layout.addWidget(self.status_label)
        
        # Connetti segnale
        self.update_signal.connect(self.update_display)
    
    @pyqtSlot(dict)
    def update_display(self, data: Dict[str, Any]):
        """
        Aggiorna il display con i nuovi dati.
        
        Args:
            data: Dizionario con 'cards', 'pot_size', 'hero_stack', 
                  'action_detected', 'equity'
        """
        try:
            # Aggiorna Board
            cards_data = data.get("cards", {})
            board = cards_data.get("board", [])
            for i, card_widget in enumerate(self.board_cards):
                if i < len(board):
                    card_widget.set_card(board[i])
                else:
                    card_widget.set_card(None)
            
            # Aggiorna Stage
            stage = cards_data.get("game_stage", "Unknown")
            self.stage_label.setText(stage)
            
            # Aggiorna Hand
            my_hand = cards_data.get("my_hand", [])
            for i, card_widget in enumerate(self.hand_cards):
                if i < len(my_hand):
                    card_widget.set_card(my_hand[i])
                else:
                    card_widget.set_card(None)
            
            # Aggiorna Equity
            equity = data.get("equity")
            if equity is not None:
                self.equity_label.setText(f"{equity:.1f}")
                # Colore in base all'equity
                if equity >= 60:
                    color = "#00ff88"  # Verde
                elif equity >= 40:
                    color = "#ffd700"  # Giallo
                else:
                    color = "#ff4757"  # Rosso
                self.equity_label.setStyleSheet(f"color: {color}; background: transparent;")
                self.equity_suffix.setStyleSheet(f"color: {color}; background: transparent;")
            else:
                self.equity_label.setText("--")
            
            # Aggiorna Pot
            pot = data.get("pot_size", 0)
            self.pot_label.setText(f"${pot:,.0f}" if pot >= 1 else f"${pot:.2f}")
            
            # Aggiorna Stack
            stack = data.get("hero_stack", 0)
            self.stack_label.setText(f"${stack:,.0f}" if stack >= 1 else f"${stack:.2f}")
            
            # Aggiorna Action
            action = data.get("action_detected", "Unknown")
            self.action_label.setText(action)
            
            # Action colors
            action_colors = {
                "Bet/Raise": "#ff4757",
                "Call": "#ffd700",
                "Check": "#2ecc71",
                "New Hand": "#9b59b6",
                "No Action": "#666"
            }
            action_color = action_colors.get(action, "#00d4ff")
            self.action_label.setStyleSheet(f"color: {action_color}; background: transparent;")
            
            # Aggiorna Position
            hero_pos = data.get("hero_position", "Unknown")
            self.pos_label.setText(hero_pos)
            # Colore cyan per posizione
            self.pos_label.setStyleSheet("color: #00d4ff; background: transparent;")
            
            # Aggiorna Hand Strength
            hand_desc = data.get("hand_description", "--")
            self.hand_strength_label.setText(hand_desc)
            
            # Colore in base al rank
            hand_rank = data.get("hand_rank", 0)
            if hand_rank > 0:
                if hand_rank <= 1000:  # Top hands
                    color = "#ffd700"  # Gold
                elif hand_rank <= 3000:  # Medium
                    color = "#00d4ff"  # Cyan
                else:  # Weak
                    color = "#888"  # Gray
            else:
                color = "#666"  # Default
            self.hand_strength_label.setStyleSheet(f"color: {color}; background: transparent;")
            
            # Status
            self.status_label.setText("🟢 Connected - Processing...")
            self.status_label.setStyleSheet("color: #2ecc71; font-size: 11px; background: transparent;")
            
        except Exception as e:
            self.status_label.setText(f"⚠️ Error: {str(e)}")
            self.status_label.setStyleSheet("color: #ff4757; font-size: 11px; background: transparent;")
    
    def set_status(self, message: str, is_error: bool = False):
        """Imposta il messaggio di stato."""
        color = "#ff4757" if is_error else "#2ecc71"
        prefix = "🔴" if is_error else "🟢"
        self.status_label.setText(f"{prefix} {message}")
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px; background: transparent;")


# ============================================================================
# TEST STANDALONE
# ============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Test dashboard con dati fittizi
    dashboard = PokerDashboard()
    dashboard.show()
    
    # Simula dati
    test_data = {
        "cards": {
            "my_hand": ["Ah", "Kd"],
            "board": ["Js", "Tc", "2h"],
            "game_stage": "Flop"
        },
        "pot_size": 150.50,
        "hero_stack": 985.00,
        "action_detected": "Bet/Raise",
        "equity": 65.4
    }
    
    # Aggiorna dopo 1 secondo
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(1000, lambda: dashboard.update_display(test_data))
    
    sys.exit(app.exec())
