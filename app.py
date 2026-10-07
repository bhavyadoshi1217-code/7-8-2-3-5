import os
import re
import secrets
import threading
from functools import wraps

from flask import Flask, Response, request
from flask_socketio import SocketIO, emit, join_room

from engine import Game

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only")

# Threading mode matches the Render/gthread configuration in this project.
sio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=False,
    engineio_logger=False,
)

LOCK = threading.RLock()
BASE = os.path.dirname(os.path.abspath(__file__))
ROOMS = {}
ALPHA = "ABCDEFGHJKLMNPQRTUVWXYZ2346789"  # no O,0,I,1,S,5
NEED = {"78": 2, "235": 3}


def locked(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        with LOCK:
            return f(*args, **kwargs)
    return wrapper


def clean(value):
    return re.sub(r"[<>&\"'`]", "", (value or "").strip())[:20]


def room_info(room):
    return {
        "code": room["code"],
        "kind": room["kind"],
        "need": NEED[room["kind"]],
        "started": room["game"] is not None,
        "players": [
            {
                "name": player["name"],
                "on": player["on"],
                "host": pid == room["host"],
            }
            for pid, player in room["players"].items()
        ],
    }


def push(room):
    """Send each player only the state they are allowed to see."""
    for pid, player in room["players"].items():
        sid = player.get("sid")
        if not sid:
            continue

        payload = {
            "room": room_info(room),
            "me": pid,
            "host": pid == room["host"],
            "game": room["game"].view(pid) if room["game"] else None,
            "names": {q: x["name"] for q, x in room["players"].items()},
        }
        sio.emit("state", payload, to=sid)


def find_player(data):
    code = str((data or {}).get("code", "")).upper().strip()
    pid = (data or {}).get("pid")
    room = ROOMS.get(code)
    player = room and room["players"].get(pid)

    if player:
        player["sid"] = request.sid
        player["on"] = True

    return (room, pid) if player else (None, None)


def error(message):
    emit("err", {"message": message})


@app.route("/")
@app.route("/join/<code>")
def index(code=""):
    code = re.sub(r"[^A-Z0-9]", "", code.upper())[:6]
    with open(os.path.join(BASE, "page.html"), encoding="utf-8") as f:
        html = f.read()
    return Response(html.replace("{{ code }}", code), mimetype="text/html")


@app.route("/health")
def health():
    return "ok"


@sio.on("connect")
def socket_connect(auth=None):
    emit("server_ready", {"ok": True})


@sio.on("create")
@locked
def create(data):
    data = data or {}
    kind = data.get("kind")
    name = clean(data.get("name"))

    if kind not in NEED:
        return error("Please select 7–8 or 2–3–5 first.")
    if not name:
        return error("Please enter your name.")

    # Generate a unique room code.
    for _ in range(20):
        code = "".join(secrets.choice(ALPHA) for _ in range(5))
        if code not in ROOMS:
            break
    else:
        return error("Could not create a room. Please try again.")

    pid = secrets.token_urlsafe(16)
    room = {
        "code": code,
        "kind": kind,
        "host": pid,
        "game": None,
        "players": {
            pid: {
                "name": name,
                "sid": request.sid,
                "on": True,
            }
        },
    }
    ROOMS[code] = room

    join_room(code)

    # Explicit acknowledgement for the browser.
    emit("joined", {"pid": pid, "code": code, "kind": kind, "created": True})
    push(room)


@sio.on("join")
@locked
def join(data):
    data = data or {}
    code = str(data.get("code", "")).upper().strip()
    name = clean(data.get("name"))
    room = ROOMS.get(code)

    if not room:
        return error("Room not found. Check the room code.")
    if room["game"] is not None:
        return error("This game has already started.")
    if len(room["players"]) >= NEED[room["kind"]]:
        return error("This room is already full.")
    if not name:
        return error("Please enter your name.")
    if name.lower() in [p["name"].lower() for p in room["players"].values()]:
        return error("That name is already taken in this room.")

    pid = secrets.token_urlsafe(16)
    room["players"][pid] = {
        "name": name,
        "sid": request.sid,
        "on": True,
    }

    join_room(room["code"])
    emit("joined", {"pid": pid, "code": room["code"], "kind": room["kind"]})
    push(room)


@sio.on("rejoin")
@locked
def rejoin(data):
    room, pid = find_player(data)
    if not room:
        return emit("expired")

    join_room(room["code"])
    push(room)


@sio.on("disconnect")
@locked
def disconnect():
    sid = request.sid
    for room in ROOMS.values():
        for player in room["players"].values():
            if player.get("sid") == sid:
                player["on"] = False
                push(room)


@sio.on("start")
@locked
def start(data):
    room, pid = find_player(data)

    if not room:
        return error("Your room session has expired. Please rejoin the room.")
    if pid != room["host"]:
        return error("Only the host can start the game.")
    if room["game"] is not None:
        return error("The game has already started.")
    if len(room["players"]) != NEED[room["kind"]]:
        return error(f"Waiting for all players: {len(room['players'])}/{NEED[room['kind']]}.")

    ids = list(room["players"])
    import random
    random.shuffle(ids)
    targets = dict(zip(ids, [8, 7] if room["kind"] == "78" else [5, 3, 2]))
    room["game"] = Game(room["kind"], ids, targets)
    push(room)


def act(data, fn):
    room, pid = find_player(data)
    if not room:
        return error("Room session expired. Please refresh or rejoin.")
    if not room["game"]:
        return error("The game has not started yet.")

    message = fn(room["game"], pid)
    if message:
        return error(message)
    push(room)


@sio.on("peek")
@locked
def peek(data):
    room, pid = find_player(data)
    if not room or not room["game"]:
        return error("The game is not available.")

    idxs = (data or {}).get("idxs") or []
    suits = room["game"].peek(pid, idxs)
    if suits is None:
        return error("Select exactly two valid cards.")

    emit("peeked", {"suits": suits, "idxs": idxs})


@sio.on("hukum")
@locked
def hukum(data):
    data = data or {}
    act(data, lambda game, player: game.set_hukum(
        player, data.get("suit"), data.get("idxs")
    ))


@sio.on("play")
@locked
def play(data):
    data = data or {}
    act(data, lambda game, player: game.play(player, data.get("card")))


@sio.on("next")
@locked
def next_game(data):
    room, pid = find_player(data)
    if not room:
        return error("Room session expired.")
    if pid != room["host"]:
        return error("Only the host can start the next game.")
    if not room["game"] or room["game"].phase != "done":
        return error("The current game is not finished yet.")

    room["game"] = room["game"].next_game()
    push(room)


if __name__ == "__main__":
    sio.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        allow_unsafe_werkzeug=True,
    )
