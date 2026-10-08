import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from engine import Game, eligible_ordinary_suits


def test_special_sevens_not_ordinary_preview():
    assert eligible_ordinary_suits(["7♥", "7♠"]) == []
    assert eligible_ordinary_suits(["7♥", "A♦"]) == ["♦"]


def test_peek_limits_hukum_to_two_cards():
    g = Game("235", ["a", "b", "c"], {"a":5,"b":3,"c":2})
    g.hand["a"] = ["8♣","9♣","10♣","J♣","Q♣","K♣","A♣","8♥","9♥","10♥"]
    assert g.sel == "a"
    assert g.peek("a", [0,1]) == ["♣"]
    assert g.set_hukum("a", "♥", [0,1])
    assert g.set_hukum("a", "♣", [0,1]) is None


def test_shortfall_is_pending_for_next_game():
    g = Game("78", ["a", "b"], {"a":8,"b":7})
    g.won = {"a":6,"b":9}
    g._prepare_settlement()
    assert g.phase == "done_settlement_pending"
    n = g.next_game()
    assert n.phase == "hukum"
    assert n.obligations["a"][0]["amount"] == 2
    assert n.obligations["a"][0]["creditor"] == "b"


def test_trick_settlement_gives_creditor_claim_then_starts_play():
    g = Game("78", ["a", "b"], {"a":8,"b":7})
    g.won = {"a":6,"b":9}
    g._prepare_settlement()
    n = g.next_game()
    # b is the new 8-trick selector and therefore chooses Hukum first.
    n.hand["b"][:5] = ["8♦","9♣","10♠","J♥","Q♣"]
    assert n.set_hukum("b", "♦") is None
    assert n.choose_settlement("a", "tricks") is None
    assert n.trick_claims["b"] == 2
    assert n.phase == "play"


def test_card_exchange_and_compulsory_hukum_for_seven():
    g = Game("78", ["a", "b"], {"a":8,"b":7})
    g.won = {"a":7,"b":8}
    g._prepare_settlement()
    n = g.next_game()
    n.hand["b"][:5] = ["8♦","9♣","10♠","J♥","Q♣"]
    assert n.set_hukum("b", "♦") is None
    n.hand["a"] = ["7♥", "8♣", "9♣"]
    n.down["a"] = ["K♣", "Q♣", "J♣", "10♣", "9♣"]
    n.hand["b"] = ["A♦", "8♣", "9♣"]
    assert n.choose_settlement("a", "cards") is None
    assert n.phase == "settlement_select_source"
    # b (winner/creditor) selects the 7 from a (loser's) hand.
    assert n.select_exchange_source("b", "hand", 0) is None
    assert n.phase == "settlement_give_hukum"
    # b must give Hukum from b's hand.
    assert n.give_hukum("b", 0) is None
    assert n.phase == "play"
    assert "7♥" in n.hand["b"]
    assert "A♦" in n.hand["a"]
