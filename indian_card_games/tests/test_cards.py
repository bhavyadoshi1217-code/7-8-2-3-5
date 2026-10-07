from game.cards import create_deck, Card

def test_30_cards():
    d=create_deck(); assert len(d)==30; assert len({c.id for c in d})==30
    assert '7H' in {c.id for c in d}; assert '7S' in {c.id for c in d}
    assert '7D' not in {c.id for c in d}; assert '7C' not in {c.id for c in d}
    assert not any(c.rank in {'2','3','4','5','6'} for c in d)

def test_special_ranking():
    a=Card('AH','A','H'); s=Card('7S','7','S'); h=Card('7H','7','H')
    assert h.strength('D') > s.strength('D') > a.strength('D')
    assert s.effective_suit == 'TRUMP'; assert h.effective_suit == 'TRUMP'
