import random
from engine import Game, create_deck, legal_plays, trick_winner

def test_exact_deck():
    d=create_deck()
    assert len(d)==30 and len(set(d))==30
    assert '7♥' in d and '7♠' in d
    assert '7♦' not in d and '7♣' not in d

def test_special_sevens_follow_hukum():
    # Special 7s are Hukum, not ordinary Hearts/Spades.
    assert legal_plays(['7♥','A♣'],'K♥','♠') == ['7♥','A♣']
    assert legal_plays(['7♥','A♣'],'K♠','♠') == ['7♥']
    assert legal_plays(['7♥','A♣'],'7♠','♠') == ['7♥']
    assert trick_winner([('a','7♠'),('b','A♠')],'♠') == 'a'
    assert trick_winner([('a','7♥'),('b','7♠')],'♣') == 'a'

def test_many_complete_games():
    for kind in ('78','235'):
        for seed in range(25):
            random.seed(seed)
            ids=['a','b'] if kind=='78' else ['a','b','c']
            targets=dict(zip(ids,[8,7] if kind=='78' else [5,3,2]))
            g=Game(kind,ids,targets)
            assert g.set_hukum(g.sel, sorted({c[-1] for c in g.hand[g.sel][:5]})[0]) is None
            for _ in range(100):
                if g.phase=='done': break
                legal=g.legal(g.turn)
                assert legal
                assert g.play(g.turn,legal[0]) is None
            assert g.phase=='done'
            assert sum(g.won.values())==(15 if kind=='78' else 10)


def test_staged_hukum_setup_235():
    random.seed(123)
    ids=['a','b','c']; targets={'a':3,'b':5,'c':2}
    g=Game('235',ids,targets)
    sel=g.sel
    assert sel=='b'
    assert len(g.hand[sel])==5
    assert len(g.down[sel])==5
    assert all(len(g.hand[p])==10 for p in ids if p!=sel)
    cards=g.peek(sel,[1,4])
    assert len(cards)==2
    assert len(g.hand[sel])==5
    h=cards[0][-1]
    assert g.set_hukum(sel,h,[1,4]) is None
    assert len(g.hand[sel])==10
    assert g.down[sel]==[]


def test_staged_hukum_setup_78():
    random.seed(456)
    g=Game('78',['a','b'],{'a':8,'b':7})
    sel=g.sel
    assert len(g.hand[sel])==5
    assert all(c is None for c in g.view('a')['up'][sel])
    assert all(c is None for c in g.view('b')['up'][sel])
    cards=g.peek(sel,[0,3])
    assert len(cards)==2
    assert all(c is not None for c in g.view('a')['up'][sel])
    assert all(c is not None for c in g.view('b')['up'][sel])
    assert g.set_hukum(sel,cards[0][-1],[0,3]) is None
    assert g.phase=='play'


def test_direct_hukum_finishes_setup():
    random.seed(789)
    g=Game('235',['a','b','c'],{'a':5,'b':3,'c':2})
    sel=g.sel
    assert g.set_hukum(sel,g.view(sel)['elig'][0]) is None
    assert len(g.hand[sel])==10

