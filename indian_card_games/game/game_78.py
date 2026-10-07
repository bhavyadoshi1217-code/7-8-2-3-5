from .base_game import BaseGame, PlayerState, GameError
from .cards import Deck

class Game78(BaseGame):
    def __init__(self, players):
        if len(players) != 2:
            raise GameError('7–8 requires exactly 2 players')
        super().__init__(players)
        ids = list(players)
        self.targets = {ids[0]: 8, ids[1]: 7}
        for pid in ids:
            players[pid].target = self.targets[pid]
        self.hukum_selector = next(pid for pid in ids if self.targets[pid] == 8)
        self._table_slots = {pid: {} for pid in ids}
        self.deal()

    def deal(self):
        deck = Deck(); deck.shuffle()
        ids = list(self.players)
        for pid in ids:
            p = self.players[pid]
            p.hand = deck.deal(5)
            downs = deck.deal(5)
            ups = deck.deal(5)
            p.table_down = downs
            p.table_up = ups
            self._table_slots[pid] = {ups[i].id: i for i in range(5)}
        self.current_turn = self.hukum_selector

    def initial_hukum_suits(self):
        p = self.players[self.hukum_selector]
        return sorted({c.suit for c in p.hand})

    def fallback_cards(self):
        return list(enumerate(self.players[self.hukum_selector].table_down))

    def choose_hukum_first_five(self, suit):
        if suit not in self.initial_hukum_suits():
            raise GameError('Hukum must be selected from the first five cards')
        self.trump = suit
        self.current_turn = self.hukum_selector

    def choose_hukum_fallback(self, card_indices, suit):
        if len(card_indices) != 2:
            raise GameError('Select exactly two face-down cards')
        try:
            indices = [int(i) for i in card_indices]
        except Exception:
            raise GameError('Invalid face-down card selection')
        if len(set(indices)) != 2 or any(i < 0 or i >= 5 for i in indices):
            raise GameError('Invalid face-down card selection')
        cards = [self.players[self.hukum_selector].table_down[i] for i in indices]
        if any(c is None for c in cards):
            raise GameError('That hidden card has already been revealed')
        suits = {c.suit for c in cards}
        if suit not in suits:
            raise GameError('Hukum must be one of the two selected card suits')
        self.trump = suit
        self.current_turn = self.hukum_selector

    def _reveal_if_needed(self, p, card):
        # A face-up card occupies a slot. Reveal its paired face-down card.
        slot = self._table_slots[p.player_id].pop(card.id, None)
        if slot is None:
            return
        if slot < len(p.table_down):
            revealed = p.table_down[slot]
            if revealed:
                p.table_up.append(revealed)
                p.table_down[slot] = None
