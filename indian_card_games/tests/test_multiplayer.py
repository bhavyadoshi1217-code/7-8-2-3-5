from game.base_game import PlayerState, GameError
from game.game_235 import Game235

def test_server_turn_validation():
    ps={x:PlayerState(x,x) for x in 'abc'}
    g=Game235(ps, {'a':5,'b':3,'c':2})
    try: g.play_card('b', g.players['b'].hand[0].id); assert False
    except GameError: assert True
