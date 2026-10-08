"""Server-authoritative engine for 7-8 and 2-3-5 (30-card deck)."""
import random

SUITS = "♠♥♦♣"
RANKS = ["8", "9", "10", "J", "Q", "K", "A"]
RV = {r: i for i, r in enumerate(RANKS)}
SPECIAL = ["7♥", "7♠"]
ROT_235 = {5: 2, 3: 5, 2: 3}


def rotate_78_targets(targets):
    """Alternate the 8-trick and 7-trick roles after every 7-8 game."""
    players = list(targets)
    if len(players) != 2:
        raise ValueError("7-8 requires exactly two players")
    return {players[0]: targets[players[1]], players[1]: targets[players[0]]}


def create_deck():
    return [r + s for s in SUITS for r in RANKS] + SPECIAL


def suit(c): return c[-1]
def rank(c): return c[:-1]


def effective_suit(c, hukum=None):
    if c in SPECIAL:
        return "HUKUM"
    return "HUKUM" if hukum and suit(c) == hukum else suit(c)


def strength(c, hukum, lead):
    if c == "7♥": return 100
    if c == "7♠": return 99
    e = effective_suit(c, hukum)
    if e == "HUKUM": return 50 + RV[rank(c)]
    return 10 + RV[rank(c)] if e == lead else 0


def legal_plays(playable, lead_card, hukum):
    if lead_card is None:
        return list(playable)
    lead = effective_suit(lead_card, hukum)
    following = [c for c in playable if effective_suit(c, hukum) == lead]
    return following or list(playable)


def trick_winner(plays, hukum):
    lead = effective_suit(plays[0][1], hukum)
    return max(plays, key=lambda p: strength(p[1], hukum, lead))[0]


def calculate_shortfall(target, actual):
    return max(0, target - actual)


def rotate_235_targets(targets):
    return {p: ROT_235[v] for p, v in targets.items()}


class Game:
    """A game with a private, staged Hukum-reveal phase."""

    def __init__(self, kind, pids, targets, carry=None):
        self.kind = kind
        self.pids = list(pids)
        self.targets = dict(targets)
        self.carry = carry or {p: 0 for p in pids}

        deck = create_deck()
        random.shuffle(deck)
        n = 15 if kind == "78" else 10
        self.total = n
        self.hand, self.up, self.down = {}, {}, {}
        # The player with the highest target is the Hukum selector. In 2-3-5
        # that player receives only the first five initially; the other two
        # players receive their full ten before the selector previews the final
        # five.
        self.sel = max(self.pids, key=lambda p: self.targets[p])

        for i, p in enumerate(self.pids):
            cards = deck[i * n:(i + 1) * n]
            if kind == "78":
                # First 5 are in hand. Next 5 are face-down table cards.
                # Final 5 are the face-up cards, but remain hidden until the
                # Hukum selector has peeked at exactly two of them.
                self.hand[p] = cards[:5]
                self.down[p] = cards[5:10]
                self.up[p] = cards[10:15]
            else:
                # In 2-3-5, the selector receives 5 first; the other two
                # players receive their full 10 before the selector is given
                # access to the remaining 5. Those final 5 stay hidden from
                # the selector until the preview/selection step.
                if p == self.sel:
                    self.hand[p] = cards[:5]
                    self.down[p] = cards[5:10]
                else:
                    self.hand[p] = cards
                    self.down[p] = []
                self.up[p] = []

        self.won = {p: 0 for p in self.pids}
        self.hukum = None
        self.trick = []
        self.last = None
        self.turn = self.sel
        self.phase = "hukum"
        self.peeked = None
        self.revealed = False
        self.played = 0

    def playable(self, p):
        return self.hand[p] + ([c for c in self.up[p] if c] if self.revealed else [])

    def legal(self, p):
        lead = self.trick[0][1] if self.trick else None
        return legal_plays(self.playable(p), lead, self.hukum)

    def peek_pool(self, p):
        # The selector may inspect two of the five cards that will later be
        # added to their hand (235), or two of the five face-up table cards (78).
        return self.down[p] if self.kind == "235" else self.up[p]

    def peek(self, p, idxs):
        pool = self.peek_pool(p)
        if p != self.sel or self.phase != "hukum":
            return None
        if len(set(idxs)) != 2 or not all(isinstance(i, int) and 0 <= i < 5 for i in idxs):
            return None
        cards = [pool[i] for i in idxs]
        self.peeked = {"idxs": list(idxs), "cards": cards}
        if self.kind == "78":
            # After the selector has seen their chosen two, all five face-up
            # cards are revealed on the table.
            self.revealed = True
        return cards

    def _finish_setup_after_peek(self):
        if self.kind == "235":
            # All five remaining cards now join the selector's hand. The two
            # selected cards were the only ones deliberately inspected first.
            self.hand[self.sel].extend(self.down[self.sel])
            self.down[self.sel] = []
            self.revealed = True
        else:
            # The five face-up cards are now revealed on the table to everyone.
            self.revealed = True

    def set_hukum(self, p, h, idxs=None):
        if p != self.sel or self.phase != "hukum":
            return "Not allowed"

        if idxs is None:
            eligible = sorted({suit(c) for c in self.hand[p][:5]})
        else:
            cards = self.peek(p, idxs)
            if cards is None:
                return "Select exactly two of the five additional cards first"
            eligible = sorted({suit(c) for c in cards})

        if not eligible or h not in eligible:
            return "Suit not eligible"

        self.hukum = h
        # Once Hukum is chosen, the remaining cards are dealt/revealed.
        # If the selector first inspected two cards, those two were the
        # permitted preview; the complete five-card group now becomes usable.
        self._finish_setup_after_peek()
        self.peeked = None
        self.phase = "play"
        return None

    def play(self, p, card):
        if self.phase != "play" or self.turn != p:
            return "Not your turn"
        if card not in self.legal(p):
            return "Illegal card (follow suit)"

        if card in self.hand[p]:
            self.hand[p].remove(card)
        else:
            if not self.revealed:
                return "Table cards are not revealed yet"
            i = self.up[p].index(card)
            self.up[p][i] = self.down[p][i]
            self.down[p][i] = None

        self.trick.append((p, card))
        if len(self.trick) == len(self.pids):
            winner = trick_winner(self.trick, self.hukum)
            self.won[winner] += 1
            self.last = {"winner": winner, "plays": list(self.trick)}
            self.trick = []
            self.turn = winner
            self.played += 1
            if self.played == self.total:
                self.phase = "done"
        else:
            self.turn = self.pids[(self.pids.index(p) + 1) % len(self.pids)]
        return None

    def results(self):
        return {
            p: {
                "target": self.targets[p],
                "won": self.won[p],
                "shortfall": calculate_shortfall(self.targets[p], self.won[p]),
            }
            for p in self.pids
        }

    def next_game(self):
        results = self.results()
        targets = rotate_235_targets(self.targets) if self.kind == "235" else rotate_78_targets(self.targets)
        return Game(
            self.kind,
            self.pids,
            targets,
            {p: results[p]["shortfall"] for p in self.pids},
        )

    def view(self, me):
        # Only the current player gets private cards. During Hukum setup,
        # only the selector receives the two cards they explicitly peeked.
        public_up = self.up if self.revealed else {p: [None] * len(self.up[p]) for p in self.pids}
        v = {
            "kind": self.kind,
            "phase": self.phase,
            "hukum": self.hukum,
            "turn": self.turn,
            "sel": self.sel,
            "targets": self.targets,
            "won": self.won,
            "carry": self.carry,
            "trick": self.trick,
            "last": self.last,
            "hand": list(self.hand[me]),
            "n": {p: len(self.hand[p]) for p in self.pids},
            "up": public_up,
            "down": {p: [c is not None for c in self.down[p]] for p in self.pids},
            "legal": self.legal(me) if self.phase == "play" and self.turn == me else [],
            "setup_revealed": self.revealed,
        }

        if self.phase == "hukum" and me == self.sel:
            v["elig"] = sorted({suit(c) for c in self.hand[me][:5]})
            v["additional_count"] = 5
            v["peeked"] = self.peeked
            v["additional_cards"] = list(self.peeked["cards"]) if self.peeked else []
            # The browser must never receive the other three hidden cards.
            v["additional_hidden"] = True

        if self.phase == "done":
            v["result"] = self.results()
        return v
