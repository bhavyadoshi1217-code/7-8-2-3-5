from game.base_game import PlayerState
from game.game_235 import Game235
from game.scoring import rotate_235_targets

def test_distribution_and_targets():
    ps={x:PlayerState(x,x) for x in 'abc'}
    g=Game235(ps, {'a':5,'b':3,'c':2})
    assert all(len(p.hand)==10 for p in g.players.values())
    assert g.hukum_selector=='a'; assert g.current_turn=='a'

def test_rotation():
    assert rotate_235_targets({'a':5,'b':3,'c':2}) == {'a':2,'b':5,'c':3}
