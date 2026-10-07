from dataclasses import dataclass
import random

SUITS = ('S', 'H', 'D', 'C')
RANKS = ('8', '9', '10', 'J', 'Q', 'K', 'A')
SPECIALS = ('7H', '7S')
RANK_VALUE = {'8': 1, '9': 2, '10': 3, 'J': 4, 'Q': 5, 'K': 6, 'A': 7}
SUIT_SYMBOL = {'S': '♠', 'H': '♥', 'D': '♦', 'C': '♣'}

@dataclass(frozen=True)
class Card:
    id: str
    rank: str
    suit: str

    @property
    def is_special_seven(self):
        return self.id in SPECIALS

    @property
    def effective_suit(self):
        return 'TRUMP' if self.is_special_seven else self.suit

    @property
    def label(self):
        if self.is_special_seven:
            return f"7{SUIT_SYMBOL[self.suit]}"
        return f"{self.rank}{SUIT_SYMBOL[self.suit]}"

    def strength(self, trump):
        if self.id == '7H':
            return 1000
        if self.id == '7S':
            return 999
        if self.suit == trump:
            return 900 + RANK_VALUE[self.rank]
        return RANK_VALUE[self.rank]


def create_deck():
    cards = [Card(f'{r}{s}', r, s) for s in SUITS for r in RANKS]
    cards += [Card('7H', '7', 'H'), Card('7S', '7', 'S')]
    return cards


class Deck:
    def __init__(self):
        self.cards = create_deck()

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self, n):
        if n > len(self.cards):
            raise ValueError('Not enough cards')
        out, self.cards = self.cards[:n], self.cards[n:]
        return out
