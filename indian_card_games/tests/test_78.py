from game.base_game import PlayerState
from game.game_78 import Game78

def make():
    ps={'a':PlayerState('a','A'),'b':PlayerState('b','B')}
    return Game78(ps)

def test_distribution():
    g=make()
    for p in g.players.values():
        assert len(p.hand)==5; assert len(p.table_up)==5; assert len(p.table_down)==5

def test_selector_and_first_player():
    g=make(); assert g.hukum_selector=='a'; assert g.current_turn=='a'

def test_special_seven_lead_requires_hukum():
    g=make(); g.trump='D';
    # Force a special 7 lead and a normal trump in the other player's hand.
    from game.cards import Card
    g.trick=[('a', Card('7H','7','H'))]
    g.players['b'].hand=[Card('AD','A','D'), Card('8C','8','C')]
    g.players['b'].table_up=[]
    legal={c.id for c in g.legal_cards('b')}
    assert legal == {'AD'}
