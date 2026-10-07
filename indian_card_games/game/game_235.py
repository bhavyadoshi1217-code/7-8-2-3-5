from .base_game import BaseGame, GameError
from .cards import Deck

class Game235(BaseGame):
    def __init__(self, players, targets=None):
        if len(players) != 3:
            raise GameError('2–3–5 requires exactly 3 players')
        super().__init__(players)
        ids = list(players)
        self.targets = targets or {ids[0]: 5, ids[1]: 3, ids[2]: 2}
        if set(self.targets.values()) != {2, 3, 5}:
            raise GameError('Targets must be 2, 3 and 5')
        for pid, target in self.targets.items():
            players[pid].target = target
        self.hukum_selector = next(pid for pid in ids if self.targets[pid] == 5)
        self.deal()

    def deal(self):
        deck = Deck(); deck.shuffle()
        for pid in self.players:
            self.players[pid].hand = deck.deal(10)
        self.current_turn = self.hukum_selector

    def initial_hukum_suits(self):
        p = self.players[self.hukum_selector]
        return sorted({c.suit for c in p.hand[:5]})

    def fallback_cards(self):
        return self.players[self.hukum_selector].hand[5:10]

    def choose_hukum_first_five(self, suit):
        if suit not in self.initial_hukum_suits():
            raise GameError('Hukum must be selected from the first five cards')
        self.trump = suit
        self.current_turn = self.hukum_selector

    def choose_hukum_fallback(self, card_ids, suit):
        if len(card_ids) != 2:
            raise GameError('Select exactly two cards from the next five')
        cards = {c.id: c for c in self.fallback_cards()}
        if any(cid not in cards for cid in card_ids):
            raise GameError('Invalid fallback selection')
        suits = {cards[cid].suit for cid in card_ids}
        if suit not in suits:
            raise GameError('Hukum must be one of the two selected card suits')
        self.trump = suit
        self.current_turn = self.hukum_selector

    @staticmethod
    def rotate_targets(targets):
        return {pid: {5: 2, 3: 5, 2: 3}[target] for pid, target in targets.items()}
