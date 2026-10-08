"""Server-authoritative engine for 7-8 and 2-3-5."""
import random

SUITS = "♠♥♦♣"
RANKS = ["8", "9", "10", "J", "Q", "K", "A"]
RV = {r: i for i, r in enumerate(RANKS)}
SPECIAL = ["7♥", "7♠"]
ROT_235 = {5: 2, 3: 5, 2: 3}


def create_deck():
    return [r + s for s in SUITS for r in RANKS] + SPECIAL


def suit(c):
    return c[-1]


def rank(c):
    return c[:-1]


def effective_suit(c, hukum=None):
    if c in SPECIAL:
        return "HUKUM"
    return "HUKUM" if hukum and suit(c) == hukum else suit(c)


def strength(c, hukum, lead):
    if c == "7♥":
        return 100
    if c == "7♠":
        return 99
    e = effective_suit(c, hukum)
    if e == "HUKUM":
        return 50 + RV[rank(c)]
    return 10 + RV[rank(c)] if e == lead else 0


def legal_plays(playable, lead_card, hukum):
    if lead_card is None:
        return list(playable)
    lead = effective_suit(lead_card, hukum)
    follow = [c for c in playable if effective_suit(c, hukum) == lead]
    return follow or list(playable)


def trick_winner(plays, hukum):
    lead = effective_suit(plays[0][1], hukum)
    return max(plays, key=lambda p: strength(p[1], hukum, lead))[0]


def calculate_shortfall(target, actual):
    return max(0, target - actual)


def rotate_targets(kind, targets):
    if kind == "235":
        return {p: ROT_235[v] for p, v in targets.items()}
    # 7-8 alternates 8/7 every completed game.
    return {p: (7 if v == 8 else 8) for p, v in targets.items()}


def eligible_ordinary_suits(cards):
    """Special 7s are Hukum, but are NOT ordinary Hearts/Spades for Hukum preview."""
    return sorted({suit(c) for c in cards if c not in SPECIAL})


class Game:
    def __init__(self, kind, pids, targets, carry=None):
        self.kind = kind
        self.pids = list(pids)
        self.targets = dict(targets)
        self.carry = dict(carry or {p: 0 for p in pids})
        deck = create_deck()
        random.shuffle(deck)
        n = 15 if kind == "78" else 10
        self.total = n
        self.hand, self.up, self.down = {}, {}, {}
        for i, p in enumerate(self.pids):
            cards = deck[i * n:(i + 1) * n]
            if kind == "78":
                self.hand[p] = cards[:5]
                self.down[p] = cards[5:10]
                self.up[p] = cards[10:15]
            else:
                self.hand[p] = cards
                self.down[p] = []
                self.up[p] = []
        self.won = {p: 0 for p in self.pids}
        self.hukum = None
        self.trick = []
        self.last = None
        self.sel = max(self.pids, key=lambda p: self.targets[p])
        self.turn = self.sel
        self.phase = "hukum"
        self.played = 0

        # Preview state is server-side; client never receives hidden cards.
        self.peeked_idxs = None
        self.peeked_suits = None

        # Compensation state.  Each obligation is settled at the start of the
        # following game, after cards have been dealt.
        self.obligations = self._copy_obligations(carry)
        self.settlement = None
        self.trick_claims = {}

    @staticmethod
    def _copy_obligations(carry):
        # Backward-compatible with old rooms that only stored numeric carry.
        if not carry:
            return {}
        if all(isinstance(v, int) for v in carry.values()):
            return {}
        return {p: [dict(x) for x in obs] for p, obs in carry.items() if obs}

    def playable(self, p):
        return self.hand[p] + [c for c in self.up[p] if c]

    def legal(self, p):
        return legal_plays(self.playable(p), self.trick[0][1] if self.trick else None, self.hukum)

    def next_five(self, p):
        return self.hand[p][5:] if self.kind == "235" else self.down[p]

    def peek(self, p, idxs):
        nf = self.next_five(p)
        if p != self.sel or self.phase != "hukum":
            return None
        if len(idxs) != 2 or len(set(idxs)) != 2:
            return None
        if not all(isinstance(i, int) and 0 <= i < len(nf) for i in idxs):
            return None
        self.peeked_idxs = tuple(sorted(idxs))
        self.peeked_suits = eligible_ordinary_suits([nf[i] for i in self.peeked_idxs])
        return list(self.peeked_suits)

    def set_hukum(self, p, h, idxs=None):
        if p != self.sel or self.phase != "hukum":
            return "Not allowed"
        if h not in SUITS:
            return "Invalid Hukum"

        if idxs is not None:
            # Once two cards have been inspected, Hukum MUST come only from those cards.
            if self.peeked_idxs is None or tuple(sorted(idxs)) != self.peeked_idxs:
                return "You must use the two inspected cards"
            elig = self.peeked_suits or []
        else:
            # Immediate selection from first five is allowed.
            elig = eligible_ordinary_suits(self.hand[p][:5])

        if h not in elig:
            return "Hukum must be one of the eligible suits from your selection"
        self.hukum = h
        if self.obligations:
            self._start_next_obligation()
        else:
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
            if card not in self.up[p]:
                return "Card is no longer available"
            i = self.up[p].index(card)
            self.up[p][i] = self.down[p][i]
            self.down[p][i] = None
        self.trick.append((p, card))
        if len(self.trick) == len(self.pids):
            actual_winner = trick_winner(self.trick, self.hukum)
            # A previous-game "transfer tricks" settlement creates a real claim.
            # Until the claim is exhausted, each completed trick is credited to
            # the creditor instead of the player who would otherwise win it.
            w = actual_winner
            claim_holders = [p for p, n in self.trick_claims.items() if n > 0]
            if claim_holders:
                w = claim_holders[0]
                self.trick_claims[w] -= 1
            self.won[w] += 1
            self.last = {"winner": w, "actual_winner": actual_winner, "plays": list(self.trick)}
            self.trick = []
            self.turn = w
            self.played += 1
            if self.played == self.total:
                self._prepare_settlement()
        else:
            self.turn = self.pids[(self.pids.index(p) + 1) % len(self.pids)]
        return None

    def results(self):
        return {
            p: {
                "target": self.targets[p],
                "won": self.won[p],
                "shortfall": calculate_shortfall(self.targets[p], self.won[p]),
                "surplus": max(0, self.won[p] - self.targets[p]),
            }
            for p in self.pids
        }

    def _prepare_settlement(self):
        """Create shortfall obligations; they are settled in the next deal."""
        r = self.results()
        creditors = [[p, r[p]["surplus"]] for p in self.pids if r[p]["surplus"]]
        debtors = [[p, r[p]["shortfall"]] for p in self.pids if r[p]["shortfall"]]
        self.obligations = {p: [] for p in self.pids}
        ci = 0
        for debtor, amount in debtors:
            while amount > 0 and ci < len(creditors):
                creditor, available = creditors[ci]
                take = min(amount, available)
                self.obligations[debtor].append({"creditor": creditor, "amount": take})
                amount -= take
                creditors[ci][1] -= take
                if creditors[ci][1] == 0:
                    ci += 1
        self.phase = "done" if not any(self.obligations.values()) else "done_settlement_pending"

    def _start_next_obligation(self):
        for debtor in self.pids:
            if self.obligations.get(debtor):
                ob = self.obligations[debtor][0]
                self.settlement = {
                    "debtor": debtor, "creditor": ob["creditor"],
                    "amount": ob["amount"], "remaining": ob["amount"],
                    "mode": None, "selected": None, "exchange_step": None,
                }
                self.phase = "settlement_choice"
                return
        self.settlement = None
        self.phase = "play"

    def choose_settlement(self, p, mode):
        if self.phase != "settlement_choice" or not self.settlement:
            return "No settlement is pending"
        if p != self.settlement["debtor"]:
            return "The player with the shortfall must choose the settlement"
        if mode not in ("tricks", "cards"):
            return "Choose tricks or cards"
        self.settlement["mode"] = mode
        if mode == "tricks":
            # The creditor receives a claim for these actual tricks in this game.
            c = self.settlement["creditor"]
            self.trick_claims[c] = self.trick_claims.get(c, 0) + self.settlement["amount"]
            self._complete_current_obligation()
        else:
            self.settlement["exchange_step"] = "select_source"
            self.phase = "settlement_select_source"
        return None

    def select_exchange_source(self, p, source, index):
        if self.phase != "settlement_select_source" or not self.settlement:
            return "No card exchange is pending"
        creditor = self.settlement["creditor"]
        debtor = self.settlement["debtor"]
        if p != creditor:
            return "The winning player selects the card from the losing player's cards"
        if source not in ("hand", "down"):
            return "Invalid source"
        cards = self.hand[debtor] if source == "hand" else [c for c in self.down[debtor] if c]
        if not isinstance(index, int) or index < 0 or index >= len(cards):
            return "Invalid card selection"
        selected = cards[index]
        self.settlement["selected"] = {"source": source, "index": index, "card": selected}
        # If the winner blindly selected a special 7 from the loser, the winner
        # must return a Hukum card. Otherwise the winner may choose any hand card.
        self.phase = "settlement_give_hukum" if selected in SPECIAL else "settlement_select_return"
        return None

    def select_return_card(self, p, index):
        if self.phase != "settlement_select_return" or not self.settlement:
            return "No return card is pending"
        if p != self.settlement["creditor"]:
            return "The winning player gives the return card from their hand"
        if not isinstance(index, int) or index < 0 or index >= len(self.hand[p]):
            return "Invalid return card"
        return self._finish_one_card_exchange(self.hand[p][index], recipient_gives=True)

    def give_hukum(self, p, index):
        if self.phase != "settlement_give_hukum" or not self.settlement:
            return "No compulsory Hukum exchange is pending"
        if p != self.settlement["creditor"]:
            return "The winning player who received the 7 must give Hukum"
        if not isinstance(index, int) or index < 0 or index >= len(self.hand[p]):
            return "Invalid Hukum card"
        c = self.hand[p][index]
        if effective_suit(c, self.hukum) != "HUKUM":
            return "Because you selected a 7, you must return a Hukum card"
        return self._finish_one_card_exchange(c, recipient_gives=True)

    def _remove_selected_from_debtor(self):
        debtor = self.settlement["debtor"]
        selected = self.settlement["selected"]
        card = selected["card"]
        if selected["source"] == "hand":
            self.hand[debtor].remove(card)
        else:
            live = [c for c in self.down[debtor] if c]
            actual = live[selected["index"]]
            self.down[debtor][self.down[debtor].index(actual)] = None
        return card

    def _finish_one_card_exchange(self, return_card, recipient_gives=False):
        debtor = self.settlement["debtor"]
        creditor = self.settlement["creditor"]
        selected_card = self._remove_selected_from_debtor()
        if return_card not in self.hand[creditor]:
            return "Return card is no longer available"
        self.hand[creditor].remove(return_card)
        self.hand[debtor].append(return_card)
        self.hand[creditor].append(selected_card)
        self.settlement["remaining"] -= 1
        self.settlement["selected"] = None
        if self.settlement["remaining"] <= 0:
            self._complete_current_obligation()
        else:
            self.settlement["exchange_step"] = "select_source"
            self.phase = "settlement_select_source"
        return None

    def _complete_current_obligation(self):
        debtor = self.settlement["debtor"]
        if self.obligations.get(debtor):
            self.obligations[debtor].pop(0)
        self.settlement = None
        self._start_next_obligation()

    def next_game(self):
        if self.phase not in ("done", "done_settlement_pending"):
            return None
        t = rotate_targets(self.kind, self.targets)
        # Pass obligations into the new deal; numeric carry is retained only for display.
        g = Game(self.kind, self.pids, t, self.obligations)
        g.phase = "hukum"
        return g

    def view(self, me):
        pending_carry = {p: sum(o.get("amount", 0) for o in self.obligations.get(p, [])) for p in self.pids}
        v = dict(
            kind=self.kind, phase=self.phase, hukum=self.hukum, turn=self.turn,
            sel=self.sel, targets=self.targets, won=self.won, carry=pending_carry,
            trick=self.trick, last=self.last, hand=self.hand[me],
            n={p: len(self.hand[p]) for p in self.pids}, up=self.up,
            down={p: [c is not None for c in self.down[p]] for p in self.pids},
            legal=self.legal(me) if self.phase == "play" and self.turn == me else [],
            trick_claims=self.trick_claims,
        )
        if self.phase == "hukum" and me == self.sel:
            v["elig"] = eligible_ordinary_suits(self.hand[me][:5])
            v["nf"] = self.hand[me][5:] if self.kind == "235" else ["?"] * 5
        if self.phase == "settlement_choice" and self.settlement:
            if me in (self.settlement["debtor"], self.settlement["creditor"]):
                v["settlement"] = dict(self.settlement)
        elif self.phase in ("settlement_select_source", "settlement_select_return", "settlement_give_hukum") and self.settlement:
            if me in (self.settlement["debtor"], self.settlement["creditor"]):
                v["settlement"] = dict(self.settlement)
                if me == self.settlement["creditor"] and self.phase == "settlement_select_source":
                    debtor = self.settlement["debtor"]
                    v["exchange_hand"] = list(self.hand[debtor])
                    v["exchange_down"] = [c for c in self.down[debtor] if c]
        if self.phase == "done":
            v["result"] = self.results()
        return v
