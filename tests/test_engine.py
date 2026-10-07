import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from engine import *
def test_deck():
    d = create_deck(); assert len(d) == 30 == len(set(d))
    assert "7♥" in d and "7♠" in d and "7♦" not in d and "7♣" not in d
def test_rank():
    assert strength("7♥", "♦", "♣") > strength("7♠", "♦", "♣") > strength("A♦", "♦", "♣") > strength("K♦", "♦", "♣")
    assert strength("8♦", "♦", "♣") > strength("A♣", "♦", "♣")
def test_suit(): assert effective_suit("7♥") == effective_suit("7♠") == "HUKUM" and effective_suit("A♣") == "♣"
def test_follow():
    assert legal_plays(["A♣", "7♥"], "K♣", "♦") == ["A♣"]
    assert set(legal_plays(["A♦", "7♥"], "K♣", "♦")) == {"A♦", "7♥"}
    assert legal_plays(["A♦", "9♣"], "7♠", "♦") == ["A♦"]
def test_winner():
    assert trick_winner([("a", "A♣"), ("b", "7♠"), ("c", "8♦")], "♦") == "b"
def test_deal_and_rotation():
    g = Game("235", "abc", {"a": 5, "b": 3, "c": 2}); assert g.sel == "a" and all(len(g.hand[p]) == 10 for p in "abc")
    assert rotate_235_targets({"a": 5, "b": 3, "c": 2}) == {"a": 2, "b": 5, "c": 3}
    h = Game("78", "ab", {"a": 8, "b": 7}); assert len(h.hand["a"]) == len(h.down["a"]) == len(h.up["a"]) == 5
def test_reveal_and_shortfall():
    h = Game("78", "ab", {"a": 8, "b": 7}); h.phase, h.hukum = "play", "♦"; h.turn = "a"
    c, hid = h.up["a"][0], h.down["a"][0]; assert h.play("a", c) is None and h.up["a"][0] == hid
    assert calculate_shortfall(8, 6) == 2 and calculate_shortfall(5, 3) == 2 and calculate_shortfall(7, 9) == 0
