import random
from typing import Dict, List, Optional
import logging
from decimal import Decimal

logger = logging.getLogger('discord')

class RouletteGame:
    def __init__(self, initiator_id: int):
        self.table_id = f"roulette-{random.randint(1000, 9999)}"
        self.initiator_id = initiator_id
        self.players: List[int] = [initiator_id]
        self.game_started = False
        self.player_choices: Dict[int, int] = {}  # player_id: pocket_number
        self.player_bets: Dict[int, Decimal] = {}  # player_id: bet_amount
        self.winning_number: Optional[int] = None
        logger.info(f"New roulette table created: {self.table_id}")
    
    def add_player(self, player_id: int) -> bool:
        if player_id in self.players or self.game_started:
            return False
        self.players.append(player_id)
        logger.info(f"Player {player_id} joined table {self.table_id}")
        return True
    
    def start_game(self, initiator_id: int) -> bool:
        if initiator_id != self.initiator_id or len(self.players) < 2 or self.game_started:
            return False
        self.game_started = True
        logger.info(f"Roulette game started on table {self.table_id}")
        return True
    
    def set_player_choice(self, player_id: int, pocket: int) -> bool:
        if not self.game_started or player_id not in self.players or pocket < 1 or pocket > 36:
            return False
        self.player_choices[player_id] = pocket
        logger.info(f"Player {player_id} chose pocket {pocket} on table {self.table_id}")
        return True
    
    def set_player_bet(self, player_id: int, amount: Decimal) -> bool:
        if not self.game_started or player_id not in self.players or player_id not in self.player_choices:
            return False
        self.player_bets[player_id] = amount
        logger.info(f"Player {player_id} bet ${amount} on table {self.table_id}")
        return True
    
    def is_ready_to_spin(self) -> bool:
        return (self.game_started and 
                len(self.player_choices) == len(self.players) and 
                len(self.player_bets) == len(self.players))
    
    def spin(self) -> int:
        if not self.is_ready_to_spin():
            raise ValueError("Not all players have placed their bets")
        self.winning_number = random.randint(1, 36)
        logger.info(f"Roulette spin result on table {self.table_id}: {self.winning_number}")
        return self.winning_number
    
    def get_color(self, number: int) -> str:
        if number < 1 or number > 36:
            raise ValueError("Invalid pocket number")
        # Alternating red and black
        return "red" if number % 2 == 1 else "black"
    
    def get_winners(self) -> Dict[int, Decimal]:
        if self.winning_number is None:
            raise ValueError("Wheel hasn't been spun yet")
        
        winners: Dict[int, Decimal] = {}
        for player_id, choice in self.player_choices.items():
            if choice == self.winning_number:
                # Winner gets 35x their bet (36x including their original bet)
                winners[player_id] = self.player_bets[player_id] * Decimal('35')
        
        return winners
