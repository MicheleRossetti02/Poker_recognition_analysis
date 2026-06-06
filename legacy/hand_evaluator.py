"""
Hand Evaluator Module - Poker Hand Evaluation with Treys
==========================================================
Wrapper per la libreria Treys che fornisce:
- Mapping da formato YOLO ("Ah", "Kd") a formato Treys
- Valutazione hand rank e descrizione leggibile
- Calcolo percentile della mano

USO:
    from hand_evaluator import HandEvaluator
    
    evaluator = HandEvaluator()
    result = evaluator.evaluate_hand(["Ah", "Kd"], ["Qs", "Jc", "Tc"])
    print(result["description"])  # "Straight"
    print(result["rank"])  # 1609
"""

from typing import List, Dict, Any, Optional
from treys import Card, Evaluator


class HandEvaluator:
    """
    Valutatore di mani poker usando libreria Treys.
    
    Fornisce mapping da YOLO format a Treys e valutazione mani complete.
    """
    
    def __init__(self):
        """Inizializza il valutatore Treys."""
        self.evaluator = Evaluator()
    
    @staticmethod
    def to_treys_format(card_list: List[str]) -> List[int]:
        """
        Converte lista di carte YOLO format a Treys format.
        
        YOLO Format: "Ah", "Kd", "Qs", etc.
        - Rank: A, K, Q, J, T, 9-2
        - Suit: h (hearts), d (diamonds), c (clubs), s (spades)
        
        Treys Format: Integer representation
        
        Args:
            card_list: Lista di stringhe formato YOLO
        
        Returns:
            Lista di interi formato Treys
        
        Raises:
            ValueError: Se carta non valida
        
        Example:
            >>> HandEvaluator.to_treys_format(["Ah", "Kd"])
            [268440797, 134253349]
        """
        treys_cards = []
        
        for card_str in card_list:
            if not card_str or len(card_str) != 2:
                raise ValueError(f"Invalid card format: '{card_str}' (expected 2 chars like 'Ah')")
            
            # Valida rank e suit
            rank = card_str[0].upper()
            suit = card_str[1].lower()
            
            valid_ranks = "A23456789TJQK"
            valid_suits = "hdcs"
            
            if rank not in valid_ranks:
                raise ValueError(f"Invalid rank: '{rank}' in card '{card_str}'")
            if suit not in valid_suits:
                raise ValueError(f"Invalid suit: '{suit}' in card '{card_str}'")
            
            # Converti a Treys
            try:
                treys_card = Card.new(card_str)
                treys_cards.append(treys_card)
            except Exception as e:
                raise ValueError(f"Failed to convert card '{card_str}': {e}")
        
        return treys_cards
    
    def evaluate_hand(
        self,
        hole_cards: List[str],
        board: List[str]
    ) -> Dict[str, Any]:
        """
        Valuta una mano poker completa.
        
        Args:
            hole_cards: Lista 2 carte in mano (YOLO format)
            board: Lista 0-5 carte sul board (YOLO format)
        
        Returns:
            Dizionario con:
            - rank: Numeric rank (1 = Royal Flush, 7462 = High Card worst)
            - description: Descrizione leggibile ("Pair of Aces", "Flush", etc.)
            - hand_class: Categoria mano ("Royal Flush", "Straight", etc.)
            - percentile: Percentile della mano (0-100, 100 = migliore)
            - valid: Se la valutazione è valida
        
        Example:
            >>> evaluator.evaluate_hand(["Ah", "Kh"], ["Qh", "Jh", "Th"])
            {
                "rank": 1,
                "description": "Royal Flush",
                "hand_class": "Royal Flush",
                "percentile": 100.0,
                "valid": True
            }
        """
        # Validazione input
        if len(hole_cards) != 2:
            return self._invalid_result(f"Expected 2 hole cards, got {len(hole_cards)}")
        
        if len(board) not in [0, 3, 4, 5]:
            return self._invalid_result(f"Board must have 0, 3, 4, or 5 cards, got {len(board)}")
        
        # Non possiamo valutare senza board (preflop)
        if len(board) == 0:
            return {
                "rank": 0,
                "description": "Preflop - No board yet",
                "hand_class": "Preflop",
                "percentile": 0.0,
                "valid": False
            }
        
        # Converti a Treys format
        try:
            treys_hand = self.to_treys_format(hole_cards)
            treys_board = self.to_treys_format(board)
        except ValueError as e:
            return self._invalid_result(str(e))
        
        # Valuta la mano
        try:
            rank = self.evaluator.evaluate(treys_board, treys_hand)
            hand_class = self.evaluator.get_rank_class(rank)
            class_string = self.evaluator.class_to_string(hand_class)
            
            # Calcola percentile (1 = best, 7462 = worst)
            percentile = 100.0 * (1 - (rank - 1) / 7461)
            
            # Descrizione dettagliata
            description = self._get_detailed_description(
                treys_board + treys_hand,
                class_string,
                rank
            )
            
            return {
                "rank": rank,
                "description": description,
                "hand_class": class_string,
                "percentile": round(percentile, 1),
                "valid": True
            }
        
        except Exception as e:
            return self._invalid_result(f"Evaluation error: {e}")
    
    def _get_detailed_description(
        self,
        all_cards: List[int],
        hand_class: str,
        rank: int
    ) -> str:
        """
        Genera descrizione dettagliata della mano.
        
        Args:
            all_cards: Tutte le carte (board + hand) in formato Treys
            hand_class: Classe della mano ("Straight", "Flush", etc.)
            rank: Rank numerico
        
        Returns:
            Descrizione leggibile
        """
        # Per Royal Flush e Straight Flush, specifica
        if hand_class == "Straight Flush":
            if rank == 1:
                return "Royal Flush"
            return "Straight Flush"
        
        # Per altre mani, usa la classe base
        # Treys fornisce già descrizioni buone
        return hand_class
    
    def _invalid_result(self, error_msg: str) -> Dict[str, Any]:
        """Restituisce risultato invalido con messaggio errore."""
        return {
            "rank": 0,
            "description": f"Invalid: {error_msg}",
            "hand_class": "Invalid",
            "percentile": 0.0,
            "valid": False,
            "error": error_msg
        }
    
    def compare_hands(
        self,
        hand1_hole: List[str],
        hand2_hole: List[str],
        board: List[str]
    ) -> Dict[str, Any]:
        """
        Confronta due mani sullo stesso board.
        
        Args:
            hand1_hole: Prima mano (2 carte)
            hand2_hole: Seconda mano (2 carte)
            board: Board comune (3-5 carte)
        
        Returns:
            Dizionario con winner e dettagli
        """
        eval1 = self.evaluate_hand(hand1_hole, board)
        eval2 = self.evaluate_hand(hand2_hole, board)
        
        if not eval1["valid"] or not eval2["valid"]:
            return {"error": "Invalid hands for comparison"}
        
        # Rank più basso = mano migliore (1 = Royal Flush)
        if eval1["rank"] < eval2["rank"]:
            winner = "hand1"
        elif eval1["rank"] > eval2["rank"]:
            winner = "hand2"
        else:
            winner = "tie"
        
        return {
            "winner": winner,
            "hand1": eval1,
            "hand2": eval2
        }


# ============================================================================
# TESTING & DEMO
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("HAND EVALUATOR - Treys Integration Test")
    print("=" * 70)
    
    evaluator = HandEvaluator()
    
    # Test cases
    test_cases = [
        {
            "name": "Royal Flush",
            "hole": ["Ah", "Kh"],
            "board": ["Qh", "Jh", "Th"]
        },
        {
            "name": "Pair of Aces",
            "hole": ["Ah", "Ad"],
            "board": ["Ks", "Qc", "Jd"]
        },
        {
            "name": "Flush",
            "hole": ["Ah", "9h"],
            "board": ["Kh", "7h", "3h"]
        },
        {
            "name": "High Card",
            "hole": ["Ah", "Kd"],
            "board": ["9s", "7c", "3h"]
        },
        {
            "name": "Full House",
            "hole": ["Ah", "As"],
            "board": ["Ac", "Kh", "Kd"]
        }
    ]
    
    print("\n🧪 Testing Hand Evaluation:\n")
    for test in test_cases:
        result = evaluator.evaluate_hand(test["hole"], test["board"])
        print(f"Test: {test['name']}")
        print(f"  Hole: {test['hole']}")
        print(f"  Board: {test['board']}")
        print(f"  Result: {result['description']}")
        print(f"  Rank: {result['rank']} (Percentile: {result['percentile']}%)")
        print(f"  Valid: {result['valid']}\n")
    
    print("=" * 70)
