import random
from typing import List, Tuple, Dict
from utils.card_utils import format_card
import logging

logger = logging.getLogger('discord')

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
        self.game_id = f"{player1_id}-{player2_id}-{random.randint(1000, 9999)}"
        logger.info(f"New game created: {self.game_id}")

    def _create_deck(self) -> List[Tuple[str, str]]:
        suits = ['♠️', '♥️', '♣️', '♦️']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        deck = [(rank, suit) for suit in suits for rank in ranks]
        random.shuffle(deck)
        return deck

    def deal_initial_cards(self):
        try:
            for _ in range(2):
                for player_id in [self.player1_id, self.player2_id]:
                    card = self.deck.pop()
                    self.hands[player_id].append(card)
                    self._calculate_score(player_id)
            logger.info(f"Game {self.game_id}: Initial cards dealt")
        except Exception as e:
            logger.error(f"Error dealing initial cards in game {self.game_id}: {str(e)}")
            raise

    def hit(self, player_id: int) -> Tuple[str, str]:
        if self.game_ended:
            logger.warning(f"Game {self.game_id}: Attempted hit on ended game")
            raise ValueError("Game has ended")

        if player_id not in [self.player1_id, self.player2_id]:
            logger.error(f"Game {self.game_id}: Invalid player ID {player_id}")
            raise ValueError("Invalid player ID")

        try:
            card = self.deck.pop()
            self.hands[player_id].append(card)
            self._calculate_score(player_id)
            logger.info(f"Game {self.game_id}: Player {player_id} hit, drew {format_card(card)}")
            return card
        except Exception as e:
            logger.error(f"Error in hit action for game {self.game_id}: {str(e)}")
            raise

    def _calculate_score(self, player_id: int):
        try:
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
            logger.debug(f"Game {self.game_id}: Player {player_id} score calculated: {score}")
        except Exception as e:
            logger.error(f"Error calculating score in game {self.game_id}: {str(e)}")
            raise

    def get_hand_display(self, player_id: int) -> str:
        try:
            return ' '.join([format_card(card) for card in self.hands[player_id]])
        except Exception as e:
            logger.error(f"Error getting hand display in game {self.game_id}: {str(e)}")
            raise

    def get_score(self, player_id: int) -> int:
        return self.scores.get(player_id, 0)

    def is_bust(self, player_id: int) -> bool:
        return self.scores.get(player_id, 0) > 21

    def determine_winner(self) -> int:
        score1 = self.scores[self.player1_id]
        score2 = self.scores[self.player2_id]

        if score1 > 21:
            logger.info(f"Game {self.game_id}: Player {self.player2_id} wins (Player {self.player1_id} bust)")
            return self.player2_id
        if score2 > 21:
            logger.info(f"Game {self.game_id}: Player {self.player1_id} wins (Player {self.player2_id} bust)")
            return self.player1_id

        if score1 > score2:
            logger.info(f"Game {self.game_id}: Player {self.player1_id} wins ({score1} vs {score2})")
            return self.player1_id
        elif score2 > score1:
            logger.info(f"Game {self.game_id}: Player {self.player2_id} wins ({score2} vs {score1})")
            return self.player2_id
        else:
            logger.info(f"Game {self.game_id}: Draw ({score1} vs {score2})")
            return 0  # Draw