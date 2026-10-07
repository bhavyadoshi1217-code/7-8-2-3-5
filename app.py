import os
import re
import secrets
import threading
import time
from functools import wraps

from flask import Flask, Response, jsonify, request

from engine import Game

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only")

LOCK = threading.RLock()
BASE = os.path.dirname(os.path.abspath(__file__))
ROOMS = {}
ALPHA = "ABCDEFGHJKLMNPQRTUVWXYZ2346789"
NEED = {"78": 2, "235": 3}
PLAYER_TTL = 20


def locked(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        with LOCK:
            return fn(*args, **kwargs)
    return wrapper


def clean(value):
    return re.sub(r"[<>&\"'`]", "", (value or "").strip())[:20]


def new_code():
    for _ in range(100):
        code = "".join(secrets.choice(ALPHA) for _ in range(5))
        if code not in ROOMS:
            return code
    raise RuntimeError("Could not generate a unique room code")


def new_pid():
    return secrets.token_urlsafe(18)


def room_info(room):
    now = time.time()
    return {
        "code": room["code"],
        "kind": room["kind"],
        "need": NEED[room["kind"]],
        "started": room["game"] is not None,
        "players": [
            {
                "name": p["name"],
                "on": (now - p["seen"] <= PLAYER_TTL),
                "host": pid == room["host"],
            }
            for pid, p in room["players"].items()
        ],
    }


def public_payload(room, pid):
    player = room["players"].get(pid)
    if not player:
        return None
    player["seen"] = time.time()
    return {
        "room": room_info(room),
        "me": pid,
        "host": pid == room["host"],
        "game": room["game"].view(pid) if room["game"] else None,
        "names": {p: x["name"] for p, x in room["players"].items()},
        "server_time": int(time.time()),
    }


def find_room_player(data):
    data = data or {}
    code = str(data.get("code", "")).upper().strip()
    pid = str(data.get("pid", ""))
    room = ROOMS.get(code)
    if not room or pid not in room["players"]:
        return None, None
    room["players"][pid]["seen"] = time.time()
    return room, pid


def ok(payload):
    return jsonify({"ok": True, **payload})


def fail(message, status=400):
    return jsonify(ok=False, error=message), status


@app.route("/")
@app.route("/join/<code>")
def index(code=""):
    code = re.sub(r"[^A-Z0-9]", "", code.upper())[:6]
    with open(os.path.join(BASE, "page.html"), encoding="utf-8") as f:
        html = f.read()
    return Response(html.replace("{{ code }}", code), mimetype="text/html")


@app.get("/health")
def health():
    return "ok"


@app.post("/api/create")
@locked
def api_create():
    data = request.get_json(silent=True) or {}
    kind = data.get("kind")
    name = clean(data.get("name"))
    if kind not in NEED:
        return fail("Please select 7–8 or 2–3–5 first.")
    if not name:
        return fail("Please enter your name.")
    try:
        code = new_code()
    except RuntimeError:
        return fail("The server could not create a room. Please try again.", 503)
    pid = new_pid()
    room = {
        "code": code,
        "kind": kind,
        "host": pid,
        "game": None,
        "players": {pid: {"name": name, "seen": time.time()}},
    }
    ROOMS[code] = room
    return ok({
        "pid": pid,
        "code": code,
        "kind": kind,
        "host": True,
        "state": public_payload(room, pid),
    })


@app.post("/api/join")
@locked
def api_join():
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).upper().strip()
    name = clean(data.get("name"))
    if not code:
        return fail("Enter the room code.")
    if not name:
        return fail("Please enter your name.")
    room = ROOMS.get(code)
    if not room:
        return fail("Room not found. Check the room code.", 404)
    if room["game"] is not None:
        return fail("This game has already started.")
    if len(room["players"]) >= NEED[room["kind"]]:
        return fail("This room is already full.")
    if any(name.lower() == p["name"].lower() for p in room["players"].values()):
        return fail("That name is already taken in this room.")
    pid = new_pid()
    room["players"][pid] = {"name": name, "seen": time.time()}
    return ok({
        "pid": pid,
        "code": code,
        "kind": room["kind"],
        "host": pid == room["host"],
        "state": public_payload(room, pid),
    })


@app.post("/api/state")
@locked
def api_state():
    room, pid = find_room_player(request.get_json(silent=True))
    if not room:
        return fail("Your room session is no longer available.", 404)
    return ok({"state": public_payload(room, pid)})


@app.post("/api/start")
@locked
def api_start():
    room, pid = find_room_player(request.get_json(silent=True))
    if not room:
        return fail("Room not found or your player session is invalid.", 404)
    if pid != room["host"]:
        return fail("Only the host can start the game.", 403)
    if room["game"] is not None:
        return fail("The game has already started.")
    if len(room["players"]) != NEED[room["kind"]]:
        return fail(f"Waiting for all players: {len(room['players'])} / {NEED[room['kind']]}." )
    ids = list(room["players"])
    import random
    random.shuffle(ids)
    targets = dict(zip(ids, [8, 7] if room["kind"] == "78" else [5, 3, 2]))
    room["game"] = Game(room["kind"], ids, targets)
    return ok({"state": public_payload(room, pid)})


@app.post("/api/peek")
@locked
def api_peek():
    room, pid = find_room_player(request.get_json(silent=True))
    if not room or not room["game"]:
        return fail("Game not found.", 404)
    data = request.get_json(silent=True) or {}
    idxs = data.get("idxs") or []
    suits = room["game"].peek(pid, idxs)
    if suits is None:
        return fail("Invalid selection. Select exactly two of the next five cards.")
    return ok({"suits": suits, "idxs": idxs, "state": public_payload(room, pid)})


@app.post("/api/hukum")
@locked
def api_hukum():
    room, pid = find_room_player(request.get_json(silent=True))
    if not room or not room["game"]:
        return fail("Game not found.", 404)
    data = request.get_json(silent=True) or {}
    error = room["game"].set_hukum(pid, data.get("suit"), data.get("idxs"))
    if error:
        return fail(error)
    return ok({"state": public_payload(room, pid)})


@app.post("/api/play")
@locked
def api_play():
    room, pid = find_room_player(request.get_json(silent=True))
    if not room or not room["game"]:
        return fail("Game not found.", 404)
    data = request.get_json(silent=True) or {}
    error = room["game"].play(pid, data.get("card"))
    if error:
        return fail(error)
    return ok({"state": public_payload(room, pid)})


@app.post("/api/next")
@locked
def api_next():
    room, pid = find_room_player(request.get_json(silent=True))
    if not room or not room["game"]:
        return fail("Game not found.", 404)
    if pid != room["host"]:
        return fail("Only the host can start the next game.", 403)
    if room["game"].phase != "done":
        return fail("The current game is not finished yet.")
    room["game"] = room["game"].next_game()
    return ok({"state": public_payload(room, pid)})


@app.errorhandler(404)
def not_found(e):
    return jsonify(ok=False, error="Not found"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), threaded=True)
