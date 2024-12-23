import random
from typing import List, Tuple, Dict
from utils.card_utils import format_card

class BlackjackGame:
    def __init__(self, player1_id: int, player2_id: int, wager: float):
        self.deck = self._create_deck()
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.wager = wager
        self.hands: Dict[int, List[Tuple[str, str]]] = {
            player1_id: [],
            player2_id: []
        }
        self.scores: Dict[int, int] = {
            player1_id: 0,
            player2_id: 0
        }
        self.current_turn = player1_id
        self.game_ended = False
        
    def _create_deck(self) -> List[Tuple[str, str]]:
        suits = ['♠️', '♥️', '♣️', '♦️']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        deck = [(rank, suit) for suit in suits for rank in ranks]
        random.shuffle(deck)
        return deck
    
    def deal_initial_cards(self):
        for _ in range(2):
            for player_id in [self.player1_id, self.player2_id]:
                card = self.deck.pop()
                self.hands[player_id].append(card)
                self._calculate_score(player_id)
    
    def hit(self, player_id: int) -> Tuple[str, str]:
        card = self.deck.pop()
        self.hands[player_id].append(card)
        self._calculate_score(player_id)
        return card
    
    def _calculate_score(self, player_id: int):
        hand = self.hands[player_id]
        score = 0
        aces = 0
        
        for rank, _ in hand:
            if rank in ['J', 'Q', 'K']:
                score += 10
            elif rank == 'A':
                aces += 1
                score += 11
            else:
                score += int(rank)
        
        while score > 21 and aces:
            score -= 10
            aces -= 1
            
        self.scores[player_id] = score
        
    def get_hand_display(self, player_id: int) -> str:
        return ' '.join([format_card(card) for card in self.hands[player_id]])
    
    def get_score(self, player_id: int) -> int:
        return self.scores[player_id]
    
    def is_bust(self, player_id: int) -> bool:
        return self.scores[player_id] > 21
    
    def determine_winner(self) -> int:
        score1 = self.scores[self.player1_id]
        score2 = self.scores[self.player2_id]
        
        if score1 > 21:
            return self.player2_id
        if score2 > 21:
            return self.player1_id
        
        if score1 > score2:
            return self.player1_id
        elif score2 > score1:
            return self.player2_id
        else:
            return 0  # Draw
