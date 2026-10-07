from dataclasses import dataclass, field
from .cards import Card

@dataclass
class PlayerState:
    player_id: str
    name: str
    target: int = 0
    tricks: int = 0
    hand: list = field(default_factory=list)
    table_up: list = field(default_factory=list)
    table_down: list = field(default_factory=list)
    shortfall: int = 0
    pending_compensation: int = 0

class GameError(Exception):
    pass

class BaseGame:
    def __init__(self, players):
        self.players = players
        self.trump = None
        self.current_turn = None
        self.trick = []
        self.trick_history = []
        self.started = False
        self.complete = False
        self.round_no = 1

    def get_player(self, pid):
        try:
            return self.players[pid]
        except KeyError:
            raise GameError('Unknown player')

    def card_by_id(self, pid, card_id):
        p = self.get_player(pid)
        for c in p.hand + p.table_up:
            if c.id == card_id:
                return c
        raise GameError('Card is not available to this player')

    def trick_suit(self, card):
        # A normal card of the declared trump suit and either special 7 are
        # all treated as TRUMP when Hukum is being followed.
        return 'TRUMP' if card.is_special_seven or card.suit == self.trump else card.suit

    def lead_effective_suit(self):
        if not self.trick:
            return None
        return self.trick_suit(self.trick[0][1])

    def has_effective_suit(self, p, suit):
        return any(self.trick_suit(c) == suit for c in p.hand + p.table_up)

    def legal_cards(self, pid):
        p = self.get_player(pid)
        cards = p.hand + p.table_up
        if not self.trick:
            return cards
        lead = self.lead_effective_suit()
        matching = [c for c in cards if self.trick_suit(c) == lead]
        return matching if matching else cards

    def play_card(self, pid, card_id):
        if self.complete:
            raise GameError('Game is complete')
        if self.current_turn != pid:
            raise GameError('It is not your turn')
        p = self.get_player(pid)
        legal = {c.id for c in self.legal_cards(pid)}
        if card_id not in legal:
            raise GameError('You must follow suit when possible')
        card = self.card_by_id(pid, card_id)
        if card in p.hand:
            p.hand.remove(card)
        else:
            p.table_up.remove(card)
            idx = p.table_up.index(card) if card in p.table_up else None
            # Find corresponding hidden card by the original table slot.
            # table_up/table_down remain aligned by slot; remove played slot.
            # The UI sends the card id, so locate it from a saved mapping.
        self.trick.append((pid, card))
        self._reveal_if_needed(p, card)
        if len(self.trick) == len(self.players):
            winner = self.resolve_trick()
            return {'trick_complete': True, 'winner': winner}
        self.current_turn = self.next_player(pid)
        return {'trick_complete': False}

    def _reveal_if_needed(self, p, card):
        # Base game has no table cards. Game78 overrides this.
        return

    def next_player(self, pid):
        ids = list(self.players.keys())
        i = ids.index(pid)
        return ids[(i + 1) % len(ids)]

    def resolve_trick(self):
        lead = self.trick[0][1].effective_suit
        winner_pid, winner_card = self.trick[0]
        for pid, card in self.trick[1:]:
            if card.effective_suit == 'TRUMP' and winner_card.effective_suit != 'TRUMP':
                winner_pid, winner_card = pid, card
            elif card.effective_suit == winner_card.effective_suit and card.strength(self.trump) > winner_card.strength(self.trump):
                winner_pid, winner_card = pid, card
            elif card.effective_suit == lead and winner_card.effective_suit == lead and card.strength(self.trump) > winner_card.strength(self.trump):
                winner_pid, winner_card = pid, card
        self.players[winner_pid].tricks += 1
        self.trick_history.append({'cards': [(p, c.id) for p, c in self.trick], 'winner': winner_pid})
        self.trick = []
        self.current_turn = winner_pid
        if all(not p.hand and not p.table_up for p in self.players.values()):
            self.complete = True
        return winner_pid

    def choose_trump_from_cards(self, pid, card_ids):
        if self.trump is not None:
            raise GameError('Hukum already selected')
        p = self.get_player(pid)
        if len(card_ids) not in (1, 2):
            raise GameError('Select one eligible suit, or two cards for the fallback selection')
        pool = p.hand + p.table_up + p.table_down
        selected = [next((c for c in pool if c.id == cid), None) for cid in card_ids]
        if any(c is None for c in selected):
            raise GameError('Invalid Hukum selection')
        suits = {c.suit for c in selected}
        if len(card_ids) == 2 and len(suits) == 0:
            raise GameError('No eligible suit')
        # For the first-five choice, caller supplies a single card/suit marker.
        self.trump = next(iter(suits))
        self.current_turn = pid
