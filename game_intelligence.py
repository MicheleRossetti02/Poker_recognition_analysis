"""
Table Detection & Pot Odds - Game Intelligence Utilities
=========================================================
Modulo con utility per:
1. Auto-detection 6-max vs 9-max
2. Calcolo Pot Odds e Expected Value (EV)
3. Decision Matrix per call/fold/raise
"""

import math
from typing import Tuple, Optional, Dict, Any
from enum import Enum


class TableType(Enum):
    """Tipo di tavolo poker."""
    SIX_MAX = "6-max"
    NINE_MAX = "9-max"
    HEADS_UP = "Heads-Up"
    UNKNOWN = "Unknown"


class PokerDecision(Enum):
    """Decisione consigliata."""
    FOLD = "Fold"
    CALL = "Call"
    RAISE = "Raise"
    ALL_IN = "All-In"


# ============================================================================
# TABLE SIZE DETECTION
# ============================================================================

def detect_table_type(button_detected_zones: Dict[str, bool]) -> TableType:
    """
    Rileva automaticamente il tipo di tavolo basandosi su "sensing zones".
    
    LOGICA:
    - 6-max ha 6 posizioni: BTN, SB, BB, UTG, HJ, CO
    - 9-max ha 9 posizioni: BTN, SB, BB, UTG, UTG+1, UTG+2, HJ, CO, MP
    
    Sensing Zones (coordinate approssimative dove ci sono i giocatori):
    - Zone 1-6: Sempre presenti in 6-max
    - Zone 7-9: Presenti solo in 9-max
    
    Args:
        button_detected_zones: Dict con zone_id -> bool (es: {"zone_1": True})
    
    Returns:
        TableType enum
    
    Example:
        >>> zones = {"zone_1": True, "zone_2": True, "zone_6": True, "zone_7": False}
        >>> detect_table_type(zones)
        TableType.SIX_MAX
    """
    # Conta zone attive
    active_zones = sum(1 for active in button_detected_zones.values() if active)
    
    if active_zones <= 2:
        return TableType.HEADS_UP
    elif active_zones <= 6:
        return TableType.SIX_MAX
    elif active_zones <= 9:
        return TableType.NINE_MAX
    else:
        return TableType.UNKNOWN


def get_sensing_zones_6max() -> Dict[str, Tuple[int, int]]:
    """
    Restituisce le coordinate delle "sensing zones" per 6-max.
    
    Queste sono posizioni approssimative dove ci si aspetta di trovare
    giocatori in un tavolo 6-max. Usa per rilevare presenza/assenza giocatori.
    
    Returns:
        Dict con zone_id -> (x_normalized, y_normalized) tra 0.0-1.0
    
    Note:
        Coordinate normalizzate rispetto alle dimensioni del frame.
        Adatta in base al tuo layout PokerStars.
    """
    return {
        "BTN": (0.50, 0.75),  # Basso centro (Hero tipicamente)
        "SB": (0.75, 0.55),   # Destra medio
        "BB": (0.75, 0.30),   # Destra alto
        "UTG": (0.35, 0.20),  # Sinistra alto
        "HJ": (0.15, 0.45),   # Sinistra medio
        "CO": (0.30, 0.70),   # Sinistra basso
    }


def get_sensing_zones_9max() -> Dict[str, Tuple[int, int]]:
    """
    Restituisce le sensing zones per 9-max.
    
    Returns:
        Dict con zone_id -> (x_normalized, y_normalized)
    """
    return {
        "BTN": (0.50, 0.80),
        "SB": (0.70, 0.65),
        "BB": (0.85, 0.45),
        "UTG": (0.85, 0.25),
        "UTG1": (0.70, 0.10),
        "UTG2": (0.50, 0.05),
        "MP": (0.30, 0.10),
        "HJ": (0.15, 0.25),
        "CO": (0.15, 0.45),
    }


# ============================================================================
# POT ODDS CALCULATION
# ============================================================================

def calculate_pot_odds(pot_size: float, amount_to_call: float) -> float:
    """
    Calcola le pot odds.
    
    POT ODDS = amount_to_call / (pot + amount_to_call)
    
    Esempio:
    - Pot: $100
    - To call: $50
    - Pot odds = 50 / (100 + 50) = 0.33 = 33%
    
    Significa che devi vincere almeno 33% delle volte per fare call profitable.
    
    Args:
        pot_size: Dimensione corrente del pot
        amount_to_call: Importo da chiamare
    
    Returns:
        Pot odds come percentuale (0-100)
    """
    if amount_to_call <= 0:
        return 0.0
    
    total_pot = pot_size + amount_to_call
    pot_odds = (amount_to_call / total_pot) * 100
    
    return pot_odds


def calculate_expected_value(
    equity: float,
    pot_size: float,
    amount_to_call: float,
    amount_to_win: Optional[float] = None
) -> float:
    """
    Calcola l'Expected Value (EV) di una call.
    
    EV = (equity * amount_to_win) - ((1 - equity) * amount_to_call)
    
    Se EV > 0 → Call profitable
    Se EV < 0 → Fold profitable
    
    Args:
        equity: Win probability come percentuale (0-100)
        pot_size: Dimensione pot corrente
        amount_to_call: Importo da chiamare
        amount_to_win: Importo totale vincibile (default: pot + call)
    
    Returns:
        Expected value in $ (positivo = profitable)
    
    Example:
        >>> calculate_expected_value(equity=60, pot_size=100, amount_to_call=50)
        15.0  # +$15 EV → profitable call
    """
    if amount_to_win is None:
        amount_to_win = pot_size + amount_to_call
    
    # Converti equity a decimal
    equity_decimal = equity / 100.0
    
    # EV = (win_prob * win_amount) - (lose_prob * lose_amount)
    ev = (equity_decimal * amount_to_win) - ((1 - equity_decimal) * amount_to_call)
    
    return ev


def get_decision_matrix(
    equity: float,
    pot_odds: float,
    hand_rank: int,
    hero_position: str,
    aggressive_factor: float = 1.0
) -> Dict[str, Any]:
    """
    Decision matrix intelligente per suggerire azione ottimale.
    
    LOGICA:
    1. Confronta equity con pot odds
    2. Considera hand strength (rank)
    3. Aggiusta per posizione (BTN più aggressivo)
    4. Applica aggressive_factor per stile gioco
    
    Args:
        equity: Win probability % (da Treys)
        pot_odds: Pot odds % necessarie
        hand_rank: Rank mano Treys (1=best, 7462=worst)
        hero_position: Posizione corrente (BTN, SB, etc.)
        aggressive_factor: Moltiplicatore aggressività (0.5=passive, 1.5=aggressive)
    
    Returns:
        Dict con:
        - decision: PokerDecision
        - reason: Motivazione
        - confidence: Confidenza decisione 0-100%
        - ev: Expected value se disponibile
    """
    # Margine di sicurezza (equity deve essere X% sopra pot odds)
    SAFETY_MARGIN = 5.0 * aggressive_factor
    
    # Classification hand strength
    if hand_rank == 0:
        hand_strength = "Unknown"
    elif hand_rank <= 1000:
        hand_strength = "Strong"
    elif hand_rank <= 3000:
        hand_strength = "Medium"
    else:
        hand_strength = "Weak"
    
    # Position bonus (BTN/CO più aggressivi)
    position_bonus = 0.0
    if hero_position in ["Button", "Cutoff"]:
        position_bonus = 3.0 * aggressive_factor
    elif hero_position in ["Hijack"]:
        position_bonus = 2.0 * aggressive_factor
    
    # Adjusted equity con position
    adjusted_equity = equity + position_bonus
    
    # Decision logic
    if adjusted_equity > (pot_odds + SAFETY_MARGIN):
        # Equity superiore a pot odds → profitable
        if hand_strength == "Strong" and hero_position in ["Button", "Cutoff"]:
            # Mano forte in posizione → considera raise
            decision = PokerDecision.RAISE
            reason = f"Strong hand ({hand_rank}), good equity ({equity:.1f}% > {pot_odds:.1f}% pot odds)"
            confidence = min(95, equity) 
        else:
            decision = PokerDecision.CALL
            reason = f"Equity {equity:.1f}% > {pot_odds:.1f}% pot odds (+{SAFETY_MARGIN:.1f}% margin)"
            confidence = min(90, equity + 10)
    
    elif adjusted_equity > pot_odds:
        # Marginal call (equity vicina a pot odds)
        if hand_strength in ["Strong", "Medium"]:
            decision = PokerDecision.CALL
            reason = f"Marginal but {hand_strength.lower()} hand, equity {equity:.1f}% ≈ {pot_odds:.1f}% pot odds"
            confidence = 60
        else:
            decision = PokerDecision.FOLD
            reason = f"Weak hand, equity {equity:.1f}% barely above {pot_odds:.1f}% pot odds"
            confidence = 55
    
    else:
        # Equity inferiore a pot odds → fold
        decision = PokerDecision.FOLD
        reason = f"Equity {equity:.1f}% < {pot_odds:.1f}% pot odds (unprofitable)"
        confidence = min(95, 100 - equity)
    
    return {
        "decision": decision.value,
        "reason": reason,
        "confidence": round(confidence, 1),
        "hand_strength": hand_strength,
        "adjusted_equity": round(adjusted_equity, 1),
        "pot_odds_required": round(pot_odds, 1)
    }


#============================================================================
# POT ODDS HELPER
# ============================================================================

def get_pot_odds_ratio(pot_odds_percent: float) -> str:
    """
    Converte pot odds % in ratio leggibile.
    
    Args:
        pot_odds_percent: Pot odds come percentuale
    
    Returns:
        Ratio come stringa (es: "2:1", "3:1")
    
    Example:
        >>> get_pot_odds_ratio(33.3)
        "2:1"
    """
    if pot_odds_percent <=0:
        return "N/A"
    
    # odds_against = (100 - pot_odds) / pot_odds
    odds_against = (100 / pot_odds_percent) - 1
    
    # Arrotonda a ratio intero più vicino
    ratio = round(odds_against)
    
    return f"{ratio}:1"


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("TABLE DETECTION & POT ODDS - Test Suite")
    print("=" * 70)
    
    # Test 1: Table Detection
    print("\n🧪 Test 1: Table Type Detection")
    zones_6max = {f"zone_{i}": (i <= 6) for i in range(1, 10)}
    zones_9max = {f"zone_{i}": True for i in range(1, 10)}
    
    print(f"  6-max zones → {detect_table_type(zones_6max)}")
    print(f"  9-max zones → {detect_table_type(zones_9max)}")
    
    # Test 2: Pot Odds
    print("\n🧪 Test 2: Pot Odds Calculation")
    pot = 100
    to_call = 50
    pot_odds = calculate_pot_odds(pot, to_call)
    print(f"  Pot: ${pot}, To call: ${to_call}")
    print(f"  Pot odds: {pot_odds:.1f}% ({get_pot_odds_ratio(pot_odds)})")
    
    # Test 3: Expected Value
    print("\n🧪 Test 3: Expected Value")
    equity_good = 60
    equity_bad = 25
    
    ev_good = calculate_expected_value(equity_good, pot, to_call)
    ev_bad = calculate_expected_value(equity_bad, pot, to_call)
    
    print(f"  Good equity ({equity_good}%): EV = ${ev_good:.2f} → {'CALL' if ev_good > 0 else 'FOLD'}")
    print(f"  Bad equity ({equity_bad}%): EV = ${ev_bad:.2f} → {'CALL' if ev_bad > 0 else 'FOLD'}")
    
    # Test 4: Decision Matrix
    print("\n🧪 Test 4: Decision Matrix")
    decision1 = get_decision_matrix(
        equity=65,
        pot_odds=33.3,
        hand_rank=500,
        hero_position="Button",
        aggressive_factor=1.0
    )
    print(f"  Strong hand on BTN:")
    print(f"    Decision: {decision1['decision']}")
    print(f"    Reason: {decision1['reason']}")
    print(f"    Confidence: {decision1['confidence']}%")
    
    decision2 = get_decision_matrix(
        equity=28,
        pot_odds=33.3,
        hand_rank=5000,
        hero_position="Big Blind",
        aggressive_factor=1.0
    )
    print(f"\n  Weak hand OOP:")
    print(f"    Decision: {decision2['decision']}")
    print(f"    Reason: {decision2['reason']}")
    print(f"    Confidence: {decision2['confidence']}%")
    
    print("\n" + "=" * 70)
    print("✅ All tests completed!")
