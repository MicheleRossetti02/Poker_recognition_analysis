"""
Stats Manager - Opponent Statistics Tracking
=============================================
Gestisce il database SQLite per tracciare statistiche degli avversari:
- VPIP (Voluntarily Put money In Pot)
- PFR (Pre-Flop Raise)
- Mani osservate
- Total won

USO:
    from stats_manager import StatsManager
    
    stats = StatsManager()
    stats.update_player_action("Villain1", action_type="call", is_preflop=True)
    vpip = stats.get_player_vpip("Villain1")
"""

import sqlite3
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PlayerStats:
    """Statistiche di un giocatore."""
    nickname: str
    hands_observed: int
    vpip_count: int  # Volte che ha messo soldi nel pot volontariamente
    pfr_count: int   # Volte che ha raisato preflop
    total_won: float
    last_seen: str
    
    @property
    def vpip_percent(self) -> float:
        """VPIP = (vpip_count / hands_observed) * 100"""
        return (self.vpip_count / self.hands_observed * 100) if self.hands_observed > 0 else 0
    
    @property
    def pfr_percent(self) -> float:
        """PFR = (pfr_count / hands_observed) * 100"""
        return (self.pfr_count / self.hands_observed * 100) if self.hands_observed > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nickname": self.nickname,
            "hands_observed": self.hands_observed,
            "vpip": round(self.vpip_percent, 1),
            "pfr": round(self.pfr_percent, 1),
            "total_won": round(self.total_won, 2),
            "last_seen": self.last_seen
        }


class StatsManager:
    """
    Gestore statistiche avversari con database SQLite.
    
    Traccia:
    - VPIP: % volte che il giocatore mette soldi nel pot volontariamente (non BB)
    - PFR: % volte che il giocatore raisa preflop
    - Hands observed: Numero totale di mani osservate
    - Total won: Somma vincite/perdite
    
    Thread-safe per uso in VisionWorker.
    """
    
    def __init__(self, db_path: str = "poker_stats.db"):
        """
        Inizializza il manager con database SQLite.
        
        Args:
            db_path: Path al file database SQLite
        """
        self.db_path = Path(db_path)
        self._init_database()
    
    def _init_database(self):
        """Inizializza il database con schema necessario."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabella players
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                nickname TEXT PRIMARY KEY,
                hands_observed INTEGER DEFAULT 0,
                vpip_count INTEGER DEFAULT 0,
                pfr_count INTEGER DEFAULT 0,
                total_won REAL DEFAULT 0.0,
                last_seen TEXT
            )
        """)
        
        # Indici per performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_last_seen 
            ON players(last_seen DESC)
        """)
        
        conn.commit()
        conn.close()
    
    def update_player_action(
        self,
        nickname: str,
        action_type: str,
        is_preflop: bool = False,
        amount: float = 0.0
    ):
        """
        Aggiorna statistiche giocatore dopo un'azione.
        
        LOGICA VPIP:
        - Conta se il giocatore mette soldi volontariamente (call, bet, raise)
        - Non conta il big blind obbligatorio
        - Non conta i check o fold
        
        LOGICA PFR:
        - Conta solo raise/bet preflop (non call)
        - È un subset di VPIP
        
        Args:
            nickname: Nome giocatore
            action_type: 'call', 'bet', 'raise', 'check', 'fold', 'bb'
            is_preflop: Se l'azione è preflop
            amount: Importo azione (per tracking vincite)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Inizializza player se non esiste
        cursor.execute("""
            INSERT OR IGNORE INTO players (nickname, last_seen)
            VALUES (?, ?)
        """, (nickname, datetime.now().isoformat()))
        
        # Determina se conta per VPIP
        # VPIP = Volontariamente mette soldi (call, bet, raise, ma non BB)
        is_vpip_action = action_type.lower() in ['call', 'bet', 'raise']
        
        # Determina se conta per PFR
        # PFR = Raise/Bet preflop (più aggressivo di call)
        is_pfr_action = is_preflop and action_type.lower() in ['bet', 'raise']
        
        # Update statistiche
        vpip_increment = 1 if is_vpip_action else 0
        pfr_increment = 1 if is_pfr_action else 0
        
        cursor.execute("""
            UPDATE players
            SET vpip_count = vpip_count + ?,
                pfr_count = pfr_count + ?,
                last_seen = ?
            WHERE nickname = ?
        """, (vpip_increment, pfr_increment, datetime.now().isoformat(), nickname))
        
        conn.commit()
        conn.close()
    
    def increment_hands_observed(self, nickname: str):
        """
        Incrementa il contatore mani osservate.
        
        Chiamare all'inizio di ogni nuova mano per tutti i giocatori al tavolo.
        
        Args:
            nickname: Nome giocatore
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR IGNORE INTO players (nickname, last_seen)
            VALUES (?, ?)
        """, (nickname, datetime.now().isoformat()))
        
        cursor.execute("""
            UPDATE players
            SET hands_observed = hands_observed + 1,
                last_seen = ?
            WHERE nickname = ?
        """, (datetime.now().isoformat(), nickname))
        
        conn.commit()
        conn.close()
    
    def update_winnings(self, nickname: str, amount: float):
        """
        Aggiorna le vincite totali del giocatore.
        
        Args:
            nickname: Nome giocatore
            amount: Importo vinto (+) o perso (-)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE players
            SET total_won = total_won + ?,
                last_seen = ?
            WHERE nickname = ?
        """, (amount, datetime.now().isoformat(), nickname))
        
        conn.commit()
        conn.close()
    
    def get_player_stats(self, nickname: str) -> Optional[PlayerStats]:
        """
        Ottiene le statistiche di un giocatore.
        
        Args:
            nickname: Nome giocatore
        
        Returns:
            PlayerStats o None se non trovato
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT nickname, hands_observed, vpip_count, pfr_count, total_won, last_seen
            FROM players
            WHERE nickname = ?
        """, (nickname,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return PlayerStats(*row)
        return None
    
    def get_player_vpip(self, nickname: str) -> float:
        """Shortcut per ottenere solo VPIP %."""
        stats = self.get_player_stats(nickname)
        return stats.vpip_percent if stats else 0.0
    
    def get_player_pfr(self, nickname: str) -> float:
        """Shortcut per ottenere solo PFR %."""
        stats = self.get_player_stats(nickname)
        return stats.pfr_percent if stats else 0.0
    
    def get_all_active_players(self, min_hands: int = 10) -> List[PlayerStats]:
        """
        Ottiene tutti i giocatori con almeno min_hands osservate.
        
        Args:
            min_hands: Minimo mani per considerare stats affidabili
        
        Returns:
            Lista di PlayerStats ordinata per hands_observed
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT nickname, hands_observed, vpip_count, pfr_count, total_won, last_seen
            FROM players
            WHERE hands_observed >= ?
            ORDER BY hands_observed DESC
        """, (min_hands,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [PlayerStats(*row) for row in rows]
    
    def clear_all_stats(self):
        """Cancella tutte le statistiche (use with caution)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM players")
        conn.commit()
        conn.close()
    
    def export_stats(self) -> List[Dict[str, Any]]:
        """Esporta tutte le stats in formato dict per JSON."""
        players = self.get_all_active_players(min_hands=1)
        return [p.to_dict() for p in players]


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def classify_player_type(vpip: float, pfr: float) -> str:
    """
    Classifica il tipo di giocatore basato su VPIP/PFR.
    
    Classificazione standard:
    - TAG (Tight-Aggressive): VPIP 15-25%, PFR 12-20%
    - LAG (Loose-Aggressive): VPIP 25-40%, PFR 20-35%
    - NIT (Super Tight): VPIP <15%, PFR <12%
    - FISH (Loose-Passive): VPIP >35%, PFR <15%
    - MANIAC: VPIP >40%, PFR >35%
    
    Args:
        vpip: VPIP percentage
        pfr: PFR percentage
    
    Returns:
        Tipo giocatore come stringa
    """
    if vpip < 15:
        return "NIT (Very Tight)"
    elif vpip < 25 and pfr >= 12:
        return "TAG (Tight-Aggressive)"
    elif vpip < 40 and pfr >= 20:
        return "LAG (Loose-Aggressive)"
    elif vpip > 40 and pfr > 35:
        return "MANIAC (Hyper-Aggressive)"
    elif vpip > 35 and pfr < 15:
        return "FISH (Loose-Passive)"
    elif vpip >= 25:
        return "LAG/FISH (Loose)"
    else:
        return "Unknown"


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("STATS MANAGER - Test Suite")
    print("=" * 70)
    
    # Test database
    stats = StatsManager(db_path="test_poker_stats.db")
    
    print("\n🧪 Test 1: Tracking Player Actions")
    
    # Simula 100 mani per "TightPlayer"
    for i in range(100):
        stats.increment_hands_observed("TightPlayer")
        if i % 5 == 0:  # 20% VPIP
            stats.update_player_action("TightPlayer", "call", is_preflop=True)
        if i % 8 == 0:  # 12.5% PFR
            stats.update_player_action("TightPlayer", "raise", is_preflop=True)
    
    # Simula 100 mani per "LoosePlayer"
    for i in range(100):
        stats.increment_hands_observed("LoosePlayer")
        if i % 2 == 0:  # 50% VPIP
            stats.update_player_action("LoosePlayer", "call", is_preflop=True)
        if i % 4 == 0:  # 25% PFR
            stats.update_player_action("LoosePlayer", "raise", is_preflop=True)
    
    # Retrieve stats
    tight = stats.get_player_stats("TightPlayer")
    loose = stats.get_player_stats("LoosePlayer")
    
    print(f"\nTightPlayer:")
    print(f"  Hands: {tight.hands_observed}")
    print(f"  VPIP: {tight.vpip_percent:.1f}%")
    print(f"  PFR: {tight.pfr_percent:.1f}%")
    print(f"  Type: {classify_player_type(tight.vpip_percent, tight.pfr_percent)}")
    
    print(f"\nLoosePlayer:")
    print(f"  Hands: {loose.hands_observed}")
    print(f"  VPIP: {loose.vpip_percent:.1f}%")
    print(f"  PFR: {loose.pfr_percent:.1f}%")
    print(f"  Type: {classify_player_type(loose.vpip_percent, loose.pfr_percent)}")
    
    print("\n" + "=" * 70)
    print("✅ Stats Manager test completed!")
    
    # Cleanup
    import os
    if os.path.exists("test_poker_stats.db"):
        os.remove("test_poker_stats.db")
