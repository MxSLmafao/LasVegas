from typing import Tuple

def format_card(card: Tuple[str, str]) -> str:
    rank, suit = card
    return f"{rank}{suit}"

def get_card_value(rank: str) -> int:
    if rank in ['J', 'Q', 'K']:
        return 10
    elif rank == 'A':
        return 11
    else:
        return int(rank)
