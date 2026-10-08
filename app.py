import os, re, secrets, threading
from functools import wraps
from flask import Flask, Response, request
from flask_socketio import SocketIO, emit, join_room
from engine import Game

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only")
sio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
LOCK = threading.RLock()
BASE = os.path.dirname(os.path.abspath(__file__))
ROOMS = {}
ALPHA = "ABCDEFGHJKLMNPQRTUVWXYZ2346789"
NEED = {"78": 2, "235": 3}

def locked(f):
    @wraps(f)
    def w(*x, **k):
        with LOCK:
            return f(*x, **k)
    return w

@app.route("/")
@app.route("/join/<code>")
def index(code=""):
    code = re.sub(r"[^A-Z0-9]", "", code.upper())[:6]
    html = open(os.path.join(BASE, "page.html"), encoding="utf-8").read().replace("{{ code }}", code)
    return Response(html, mimetype="text/html")

@app.route("/health")
def health():
    return "ok"

def clean(n):
    return re.sub(r"[<>&\"'`]", "", (n or "").strip())[:20]

def room_info(r):
    return dict(code=r["code"], kind=r["kind"], need=NEED[r["kind"]], started=r["game"] is not None,
                players=[dict(name=p["name"], on=p["on"], host=pid == r["host"]) for pid, p in r["players"].items()])

def push(r):
    for pid, p in r["players"].items():
        if p["sid"]:
            emit("state", dict(room=room_info(r), me=pid, host=pid == r["host"],
                               game=r["game"].view(pid) if r["game"] else None,
                               names={q: x["name"] for q, x in r["players"].items()}), to=p["sid"])

def request_sid():
    return request.sid

def get(d):
    r = ROOMS.get(str(d.get("code", "")).upper())
    p = r and r["players"].get(d.get("pid"))
    if p:
        p["sid"], p["on"] = request_sid(), True
    return (r, d.get("pid")) if p else (None, None)

def err(m):
    emit("err", m)

@sio.on("create")
@locked
def create(d):
    if d.get("kind") not in NEED or not clean(d.get("name")):
        return err("Enter a name")
    code = "".join(secrets.choice(ALPHA) for _ in range(5))
    while code in ROOMS:
        code = "".join(secrets.choice(ALPHA) for _ in range(5))
    pid = secrets.token_urlsafe(16)
    ROOMS[code] = r = dict(code=code, kind=d["kind"], host=pid, game=None,
                           players={pid: dict(name=clean(d["name"]), sid=request_sid(), on=True)})
    join_room(code)
    emit("joined", dict(pid=pid, code=code))
    push(r)

@sio.on("join")
@locked
def join(d):
    r = ROOMS.get(str(d.get("code", "")).upper())
    name = clean(d.get("name"))
    if not r or r["game"] or len(r["players"]) >= NEED[r["kind"]]:
        return err("Room not found or no longer available.")
    if not name or name.lower() in [p["name"].lower() for p in r["players"].values()]:
        return err("Name missing or already taken")
    pid = secrets.token_urlsafe(16)
    r["players"][pid] = dict(name=name, sid=request_sid(), on=True)
    join_room(r["code"])
    emit("joined", dict(pid=pid, code=r["code"]))
    push(r)

@sio.on("rejoin")
@locked
def rejoin(d):
    r, pid = get(d)
    if not r:
        return emit("expired")
    join_room(r["code"])
    push(r)

@sio.on("disconnect")
@locked
def disc():
    sid = request_sid()
    for r in ROOMS.values():
        for p in r["players"].values():
            if p["sid"] == sid:
                p["on"] = False
                push(r)

@sio.on("start")
@locked
def start(d):
    r, pid = get(d)
    if not r or pid != r["host"] or r["game"] or len(r["players"]) != NEED[r["kind"]]:
        return err("Cannot start")
    ids = list(r["players"])
    import random
    random.shuffle(ids)
    targets = dict(zip(ids, [8, 7] if r["kind"] == "78" else [5, 3, 2]))
    r["game"] = Game(r["kind"], ids, targets)
    push(r)

def act(d, fn):
    r, pid = get(d)
    if not r or not r["game"]:
        return err("Game not found")
    e = fn(r["game"], pid)
    if e:
        return err(e)
    push(r)

@sio.on("peek")
@locked
def peek(d):
    r, pid = get(d)
    if r and r["game"]:
        suits = r["game"].peek(pid, d.get("idxs") or [])
        if suits is None:
            return err("Invalid two-card selection")
        emit("peeked", dict(suits=suits, idxs=d.get("idxs")))

@sio.on("hukum")
@locked
def hukum(d):
    act(d, lambda g, p: g.set_hukum(p, d.get("suit"), d.get("idxs")))

@sio.on("play")
@locked
def play(d):
    act(d, lambda g, p: g.play(p, d.get("card")))

@sio.on("settle_choice")
@locked
def settle_choice(d):
    act(d, lambda g, p: g.choose_settlement(p, d.get("mode")))

@sio.on("settle_source")
@locked
def settle_source(d):
    act(d, lambda g, p: g.select_exchange_source(p, d.get("source"), d.get("index")))

@sio.on("settle_return")
@locked
def settle_return(d):
    act(d, lambda g, p: g.select_return_card(p, d.get("index")))

@sio.on("settle_hukum")
@locked
def settle_hukum(d):
    act(d, lambda g, p: g.give_hukum(p, d.get("index")))

@sio.on("next")
@locked
def nxt(d):
    r, pid = get(d)
    if r and pid == r["host"] and r["game"] and r["game"].phase == "done":
        r["game"] = r["game"].next_game()
        push(r)

if __name__ == "__main__":
    sio.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
