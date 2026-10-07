"""Server-authoritative engine for 7-8 and 2-3-5 (30-card deck)."""
import random
SUITS = "♠♥♦♣"; RANKS = ["8", "9", "10", "J", "Q", "K", "A"]
RV = {r: i for i, r in enumerate(RANKS)}
SPECIAL = ["7♥", "7♠"]            # always Hukum; 7♥ > 7♠ > Hukum Ace
KEEP_78_ROLES = True              # CONFIG: 7-8 role transition is unspecified -> roles stay
ROT_235 = {5: 2, 3: 5, 2: 3}      # target roles rotate regardless of tricks won

def create_deck(): return [r + s for s in SUITS for r in RANKS] + SPECIAL
def suit(c): return c[-1]
def rank(c): return c[:-1]
def effective_suit(c, hukum=None):
    if c in SPECIAL: return "HUKUM"
    return "HUKUM" if hukum and suit(c) == hukum else suit(c)
def strength(c, hukum, lead):
    if c == "7♥": return 100
    if c == "7♠": return 99
    e = effective_suit(c, hukum)
    if e == "HUKUM": return 50 + RV[rank(c)]
    return 10 + RV[rank(c)] if e == lead else 0
def legal_plays(playable, lead_card, hukum):
    if lead_card is None: return list(playable)
    L = effective_suit(lead_card, hukum)
    f = [c for c in playable if effective_suit(c, hukum) == L]
    return f or list(playable)
def trick_winner(plays, hukum):
    lead = effective_suit(plays[0][1], hukum)
    return max(plays, key=lambda p: strength(p[1], hukum, lead))[0]
def calculate_shortfall(target, actual): return max(0, target - actual)
def rotate_235_targets(t): return {p: ROT_235[v] for p, v in t.items()}

class Game:
    def __init__(s, kind, pids, targets, carry=None):
        s.kind, s.pids, s.targets = kind, list(pids), dict(targets)
        s.carry = carry or {p: 0 for p in pids}   # PREVIOUS-game shortfall (not applied yet)
        d = create_deck(); random.shuffle(d)
        n = 15 if kind == "78" else 10; s.total = n
        s.hand, s.up, s.down = {}, {}, {}
        for i, p in enumerate(s.pids):
            c = d[i * n:(i + 1) * n]
            if kind == "78": s.hand[p], s.down[p], s.up[p] = c[:5], c[5:10], c[10:]
            else: s.hand[p], s.down[p], s.up[p] = c, [], []
        s.won = {p: 0 for p in s.pids}; s.hukum = None; s.trick = []; s.last = None
        s.sel = max(s.pids, key=lambda p: s.targets[p]); s.turn = s.sel
        s.phase = "hukum"; s.played = 0
    def playable(s, p): return s.hand[p] + [c for c in s.up[p] if c]
    def legal(s, p): return legal_plays(s.playable(p), s.trick[0][1] if s.trick else None, s.hukum)
    def next_five(s, p): return s.hand[p][5:] if s.kind == "235" else s.down[p]
    def peek(s, p, idxs):
        nf = s.next_five(p)
        if p != s.sel or s.phase != "hukum" or len(set(idxs)) != 2 or not all(isinstance(i, int) and 0 <= i < len(nf) for i in idxs): return None
        return sorted({suit(nf[i]) for i in idxs})
    def set_hukum(s, p, h, idxs=None):
        if p != s.sel or s.phase != "hukum": return "Not allowed"
        elig = s.peek(p, idxs) if idxs else sorted({suit(c) for c in s.hand[p][:5]})
        if not elig or h not in elig: return "Suit not eligible"
        s.hukum, s.phase = h, "play"; return None
    def play(s, p, card):
        if s.phase != "play" or s.turn != p: return "Not your turn"
        if card not in s.legal(p): return "Illegal card (follow suit)"
        if card in s.hand[p]: s.hand[p].remove(card)
        else:
            i = s.up[p].index(card)                       # reveal underlying face-down card
            s.up[p][i] = s.down[p][i] if s.kind == "78" else None
            if s.kind == "78": s.down[p][i] = None
        s.trick.append((p, card))
        if len(s.trick) == len(s.pids):
            w = trick_winner(s.trick, s.hukum); s.won[w] += 1
            s.last = {"winner": w, "plays": s.trick}; s.trick = []; s.turn = w; s.played += 1
            if s.played == s.total: s.phase = "done"
        else: s.turn = s.pids[(s.pids.index(p) + 1) % len(s.pids)]
        return None
    def results(s):
        return {p: {"target": s.targets[p], "won": s.won[p],
                    "shortfall": calculate_shortfall(s.targets[p], s.won[p])} for p in s.pids}
    def next_game(s):
        r = s.results()
        t = rotate_235_targets(s.targets) if s.kind == "235" else s.targets
        return Game(s.kind, s.pids, t, {p: r[p]["shortfall"] for p in s.pids})
    def view(s, me):
        v = dict(kind=s.kind, phase=s.phase, hukum=s.hukum, turn=s.turn, sel=s.sel, targets=s.targets,
                 won=s.won, carry=s.carry, trick=s.trick, last=s.last, hand=s.hand[me],
                 n={p: len(s.hand[p]) for p in s.pids}, up=s.up,
                 down={p: [c is not None for c in s.down[p]] for p in s.pids},
                 legal=s.legal(me) if s.phase == "play" and s.turn == me else [])
        if s.phase == "hukum" and me == s.sel:
            v["elig"] = sorted({suit(c) for c in s.hand[me][:5]})
            v["nf"] = s.hand[me][5:] if s.kind == "235" else ["?"] * 5
        if s.phase == "done": v["result"] = s.results()
        return v
