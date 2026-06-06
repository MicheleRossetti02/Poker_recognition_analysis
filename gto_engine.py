"""
GTO Engine - Simplified ABC Poker Strategy
Provides position-based preflop recommendations
"""

# Simplified Preflop Ranges (ABC Strategy)
# Hand notation: suited = 's', offsuit = 'o', pairs have no suffix
PREFLOP_RANGES = {
    'BTN': {
        'OPEN_RAISE': [
            # Premium
            'AA', 'KK', 'QQ', 'JJ', 'TT', '99',
            'AKs', 'AQs', 'AJs', 'ATs', 'AKo', 'AQo',
            # Broadway
            'KQs', 'KJs', 'KTs', 'QJs', 'QTs', 'JTs',
            # Suited connectors
            '88', '77', '66', '55', '98s', '87s', '76s',
            # More offsuit broadway
            'AJo', 'ATo', 'KQo', 'KJo'
        ],
        '3BET': [
            'AA', 'KK', 'QQ', 'JJ', 'TT',
            'AKs', 'AQs', 'AKo'
        ],
        'CALL_3BET': [
            'AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88',
            'AKs', 'AQs', 'AJs', 'AKo', 'AQo',
            'KQs', 'QJs'
        ]
    },
    'SB': {
        'OPEN_RAISE': [
            'AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77',
            'AKs', 'AQs', 'AJs', 'ATs', 'AKo', 'AQo', 'AJo',
            'KQs', 'KJs', 'KTs', 'QJs', 'JTs'
        ],
        '3BET': [
            'AA', 'KK', 'QQ', 'JJ',
            'AKs', 'AKo'
        ],
        'CALL_3BET': [
            'AA', 'KK', 'QQ', 'JJ', 'TT', '99',
            'AKs', 'AQs', 'AKo', 'KQs'
        ]
    },
    'BB': {
        'OPEN_RAISE': [
            'AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88',
            'AKs', 'AQs', 'AJs', 'ATs', 'AKo', 'AQo',
            'KQs', 'KJs', 'QJs'
        ],
        '3BET': [
            'AA', 'KK', 'QQ', 'JJ', 'TT',
            'AKs', 'AKo'
        ],
        'CALL_RAISE': [
            'AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77', '66', '55',
            'AKs', 'AQs', 'AJs', 'ATs', 'AKo', 'AQo', 'AJo',
            'KQs', 'KJs', 'KTs', 'QJs', 'QTs', 'JTs', '98s'
        ]
    },
    'UTG': {
        'OPEN_RAISE': [
            'AA', 'KK', 'QQ', 'JJ', 'TT', '99',
            'AKs', 'AQs', 'AJs', 'AKo', 'AQo',
            'KQs'
        ],
        '3BET': [
            'AA', 'KK', 'QQ',
            'AKs', 'AKo'
        ],
        'CALL_3BET': [
            'AA', 'KK', 'QQ', 'JJ', 'TT',
            'AKs', 'AKo'
        ]
    },
    'MP': {
        'OPEN_RAISE': [
            'AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88',
            'AKs', 'AQs', 'AJs', 'ATs', 'AKo', 'AQo',
            'KQs', 'KJs', 'QJs'
        ],
        '3BET': [
            'AA', 'KK', 'QQ', 'JJ',
            'AKs', 'AKo'
        ],
        'CALL_3BET': [
            'AA', 'KK', 'QQ', 'JJ', 'TT', '99',
            'AKs', 'AQs', 'AKo'
        ]
    },
    'CO': {
        'OPEN_RAISE': [
            'AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88', '77',
            'AKs', 'AQs', 'AJs', 'ATs', 'AKo', 'AQo', 'AJo',
            'KQs', 'KJs', 'KTs', 'QJs', 'JTs',
            '66', '55', '98s', '87s'
        ],
        '3BET': [
            'AA', 'KK', 'QQ', 'JJ', 'TT',
            'AKs', 'AKo'
        ],
        'CALL_3BET': [
            'AA', 'KK', 'QQ', 'JJ', 'TT', '99', '88',
            'AKs', 'AQs', 'AJs', 'AKo', 'AQo',
            'KQs'
        ]
    }
}

def normalize_hand(card1, card2):
    """
    Convert hero cards to standard notation (e.g., 'AKs', 'AKo', 'AA')
    card1, card2 are strings like 'As', 'Kh', etc.
    """
    ranks = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10, '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2}
    rank_reverse = {v: k for k, v in ranks.items()}
    
    if len(card1) < 2 or len(card2) < 2:
        return None
    
    r1, s1 = card1[0], card1[1]
    r2, s2 = card2[0], card2[1]
    
    if r1 not in ranks or r2 not in ranks:
        return None
    
    # Normalize to higher rank first
    if ranks[r1] < ranks[r2]:
        r1, r2 = r2, r1
        s1, s2 = s2, s1
    
    # Pair
    if r1 == r2:
        return f"{r1}{r2}"
    
    # Suited or offsuit
    suffix = 's' if s1 == s2 else 'o'
    return f"{r1}{r2}{suffix}"

def get_action(position, hero_hand, opponent_actions):
    """
    Get GTO recommendation based on position, hand, and opponent actions
    
    Args:
        position: str - 'BTN', 'SB', 'BB', 'UTG', 'MP', 'CO'
        hero_hand: str - normalized hand notation ('AKs', 'QQ', etc.)
        opponent_actions: list - ['FOLD', 'CALL', 'RAISE'] from opponents before hero
    
    Returns:
        str - 'FOLD', 'CALL', 'RAISE 3BB', etc.
    """
    if not hero_hand or position not in PREFLOP_RANGES:
        return 'FOLD (Unknown)'
    
    ranges = PREFLOP_RANGES[position]
    
    # No action before us - check if we should open
    if not opponent_actions or all(a == 'FOLD' for a in opponent_actions):
        if hero_hand in ranges['OPEN_RAISE']:
            return 'RAISE 3BB'
        return 'FOLD'
    
    # Facing a raise
    if 'RAISE' in opponent_actions:
        # Check for 3bet
        if hero_hand in ranges.get('3BET', []):
            return 'RAISE 9BB (3BET)'
        # Check for call
        if hero_hand in ranges.get('CALL_3BET', ranges.get('CALL_RAISE', [])):
            return 'CALL'
        return 'FOLD'
    
    # Facing limpers (just calls)
    if 'CALL' in opponent_actions:
        if hero_hand in ranges['OPEN_RAISE']:
            return 'RAISE 4BB'
        return 'FOLD'
    
    return 'FOLD (No Range)'

def get_hand_strength(hand):
    """Return simple hand strength category for display"""
    premium = ['AA', 'KK', 'QQ', 'AKs', 'AKo']
    strong = ['JJ', 'TT', 'AQs', 'AJs', 'AQo', 'KQs']
    
    if hand in premium:
        return '🔥 PREMIUM'
    elif hand in strong:
        return '💪 STRONG'
    else:
        return '✋ PLAYABLE'

# Testing
if __name__ == "__main__":
    # Test cases
    test_cases = [
        ('BTN', 'AKs', [], 'RAISE 3BB'),
        ('UTG', '72o', [], 'FOLD'),
        ('BB', 'QQ', ['RAISE'], 'RAISE 9BB (3BET)'),
        ('SB', '88', ['FOLD', 'FOLD', 'RAISE'], 'CALL'),
    ]
    
    print("GTO Engine Test Cases:")
    for pos, hand, actions, expected in test_cases:
        result = get_action(pos, hand, actions)
        status = '✅' if expected in result else '❌'
        print(f"{status} {pos} - {hand} vs {actions} → {result}")
