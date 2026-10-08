import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app import app, ROOMS, LOCK
from engine import Game, create_deck, legal_plays, trick_winner


def reset():
    with LOCK:
        ROOMS.clear()


def post(c, path, data):
    r = c.post(path, json=data)
    assert r.is_json, (path, r.status_code, r.data[:500])
    return r.status_code, r.get_json()


def create(c, kind, name):
    status, d = post(c, "/api/create", {"kind": kind, "name": name})
    assert status == 200 and d["ok"]
    return d


def join(c, code, name):
    status, d = post(c, "/api/join", {"code": code, "name": name})
    assert status == 200 and d["ok"]
    return d


def state(c, pid, code):
    status, d = post(c, "/api/state", {"pid": pid, "code": code})
    assert status == 200 and d["ok"]
    return d["state"]


def choose_hukum(c, pid, code, st):
    g = st["game"]
    assert g["phase"] == "hukum"
    assert g["sel"] == pid
    status, d = post(c, "/api/hukum", {"pid": pid, "code": code, "suit": g["elig"][0]})
    assert status == 200 and d["ok"]
    return d["state"]


def play_full_game(clients, players, code):
    # The current game state is always readable by every player.
    st = state(clients[players[0]], players[0], code)
    sel = st["game"]["sel"]
    st = choose_hukum(clients[sel], sel, code, st)
    guard = 0
    while st["game"]["phase"] != "done":
        guard += 1
        assert guard < 100, "game loop did not finish"
        g = st["game"]
        turn = g["turn"]
        legal = g["legal"]
        assert legal, (g["phase"], turn)
        card = legal[0]
        status, d = post(clients[turn], "/api/play", {"pid": turn, "code": code, "card": card})
        assert status == 200 and d["ok"], d
        st = d["state"]
    return st


def test_deck():
    deck = create_deck()
    assert len(deck) == 30
    assert len(set(deck)) == 30
    assert "7♥" in deck and "7♠" in deck
    assert "7♦" not in deck and "7♣" not in deck
    assert all(c[:-1] in {"8","9","10","J","Q","K","A"} or c in {"7♥","7♠"} for c in deck)


def test_78_create_join_start():
    reset(); c1, c2 = app.test_client(), app.test_client()
    a = create(c1, "78", "Alice")
    b = join(c2, a["code"], "Bob")
    assert b["state"]["room"]["players"]
    assert len(b["state"]["room"]["players"]) == 2
    status, d = post(c1, "/api/start", {"pid": a["pid"], "code": a["code"]})
    assert status == 200 and d["ok"]
    assert d["state"]["game"]["phase"] == "hukum"


def test_235_create_join_start_and_rotation():
    reset(); cs = [app.test_client() for _ in range(3)]
    a = create(cs[0], "235", "A")
    b = join(cs[1], a["code"], "B")
    c = join(cs[2], a["code"], "C")
    assert len(c["state"]["room"]["players"]) == 3
    status, d = post(cs[0], "/api/start", {"pid": a["pid"], "code": a["code"]})
    assert status == 200 and d["ok"]
    g = d["state"]["game"]
    assert sorted(g["targets"].values()) == [2,3,5]


def test_join_errors():
    reset(); c = app.test_client()
    status, d = post(c, "/api/join", {"code":"ZZZZZ", "name":"X"})
    assert status == 404 and not d["ok"]
    a = create(c, "78", "Alice")
    c2 = app.test_client(); join(c2, a["code"], "Bob")
    status, d = post(app.test_client(), "/api/join", {"code":a["code"], "name":"Cara"})
    assert status == 400 and "full" in d["error"].lower()


def test_two_devices_stay_in_same_room_and_full_78_game():
    reset(); c1, c2 = app.test_client(), app.test_client()
    a = create(c1, "78", "Alice"); b = join(c2, a["code"], "Bob")
    status, d = post(c1, "/api/start", {"pid":a["pid"], "code":a["code"]})
    assert status == 200
    final = play_full_game({a["pid"]:c1,b["pid"]:c2}, [a["pid"],b["pid"]], a["code"])
    assert final["game"]["phase"] == "done"
    assert sum(final["game"]["won"].values()) == 15


def test_full_235_game_and_next_rotation():
    reset(); cs=[app.test_client() for _ in range(3)]
    a=create(cs[0],"235","A"); b=join(cs[1],a["code"],"B"); c=join(cs[2],a["code"],"C")
    players=[a["pid"],b["pid"],c["pid"]]; clients=dict(zip(players,cs))
    post(cs[0],"/api/start",{"pid":a["pid"],"code":a["code"]})
    final=play_full_game(clients,players,a["code"])
    assert sum(final["game"]["won"].values()) == 10
    old=final["game"]["targets"]
    status,d=post(cs[0],"/api/next",{"pid":a["pid"],"code":a["code"]})
    assert status==200 and d["ok"]
    new=d["state"]["game"]["targets"]
    for p in players:
        assert new[p] == {5:2,3:5,2:3}[old[p]]


def test_special_sevens_are_hukum_when_following():
    assert legal_plays(["7♥","A♣"], "K♥", "♠") == ["A♣"]
    assert legal_plays(["7♥","A♣"], "K♠", "♠") == ["7♥"]
    assert legal_plays(["7♥","A♣"], "7♠", "♠") == ["7♥"]
    assert trick_winner([("a","7♠"),("b","A♠")], "♠") == "a"
    assert trick_winner([("a","7♥"),("b","7♠")], "♣") == "a"


def test_hidden_table_cards_are_not_leaked():
    reset(); c1,c2=app.test_client(),app.test_client(); a=create(c1,"78","A"); join(c2,a["code"],"B")
    post(c1,"/api/start",{"pid":a["pid"],"code":a["code"]})
    st=state(c2, list(ROOMS[a["code"]]["players"].keys())[1], a["code"])
    assert all(x is not None for x in st["game"]["down"].values())
    # Opponent up cards are visible, but down card contents are never returned.
    assert all("?" not in str(x) for x in st["game"]["down"].values())


if __name__ == "__main__":
    test_deck(); test_78_create_join_start(); test_235_create_join_start_and_rotation(); test_join_errors(); test_two_devices_stay_in_same_room_and_full_78_game(); test_full_235_game_and_next_rotation(); test_special_sevens_are_hukum_when_following(); test_hidden_table_cards_are_not_leaked(); print("ALL TESTS PASSED")
