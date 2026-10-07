import os, uuid
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from dotenv import load_dotenv
from game.game_78 import Game78
from game.game_235 import Game235
from game.base_game import PlayerState, GameError
from game.scoring import calculate_shortfall, rotate_235_targets
from multiplayer.room import RoomManager
from multiplayer.state import serialize_game

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode=os.getenv('SOCKETIO_ASYNC_MODE', 'threading'))
rooms = RoomManager()


def pid():
    if 'player_id' not in session:
        session['player_id'] = uuid.uuid4().hex
    return session['player_id']

@app.get('/')
def index():
    return render_template('index.html')

@app.get('/join/<code>')
def join_page(code):
    return render_template('join.html', code=code.upper())

@app.get('/game/<game_type>')
def game_page(game_type):
    if game_type not in ('78', '235'):
        return render_template('404.html'), 404
    return render_template('game.html', game_type=game_type)

@app.get('/api/room/<code>')
def room_info(code):
    r = rooms.get(code)
    if not r:
        return jsonify({'error': 'Room not found'}), 404
    return jsonify(r.public_lobby())


def room_for_sid(sid):
    for r in rooms.rooms.values():
        if sid in r.sessions:
            return r
    return None


def broadcast_lobby(r):
    socketio.emit('lobby_state', r.public_lobby(), room=r.code)


def make_game(r):
    players = {p: PlayerState(p, data['name']) for p, data in r.players.items()}
    r.game = Game78(players) if r.game_type == '78' else Game235(players)
    r.status = 'IN_PROGRESS'


def broadcast_game(r):
    for sid, p in list(r.sessions.items()):
        if p in r.players and r.game:
            socketio.emit('game_state', serialize_game(r.game, p), to=sid)

@app.post('/api/session')
def create_session():
    return jsonify({'player_id': pid()})

@socketio.on('connect')
def connected():
    emit('connected', {'player_id': pid()})

@socketio.on('create_game')
def create_game(data):
    try:
        game_type = data.get('game_type')
        name = str(data.get('name', '')).strip()[:20]
        if not name:
            raise ValueError('Enter a player name')
        p = pid()
        r = rooms.create(game_type, p, name, request.sid)
        join_room(r.code)
        emit('room_created', {'code': r.code, 'game_type': game_type, 'link': url_for('join_page', code=r.code, _external=True)})
        broadcast_lobby(r)
    except Exception as e:
        emit('error_message', {'message': str(e)})

@socketio.on('join_game')
def join_game(data):
    try:
        code = str(data.get('code', '')).strip().upper()
        name = str(data.get('name', '')).strip()[:20]
        r = rooms.get(code)
        if not r:
            raise ValueError('Room not found')
        if r.status != 'WAITING':
            raise ValueError('Game has already started')
        p = pid()
        r.add_player(p, name, request.sid)
        join_room(r.code)
        emit('room_joined', {'code': r.code, 'game_type': r.game_type})
        broadcast_lobby(r)
    except Exception as e:
        emit('error_message', {'message': str(e)})

@socketio.on('ready')
def ready(data):
    r = room_for_sid(request.sid)
    if not r or r.status != 'WAITING': return
    r.ready.add(r.sessions[request.sid]); broadcast_lobby(r)

@socketio.on('start_game')
def start_game():
    r = room_for_sid(request.sid)
    if not r: return
    p = r.sessions[request.sid]
    if p != r.host_id: return emit('error_message', {'message': 'Only the host can start the game'})
    if len(r.players) != r.capacity: return emit('error_message', {'message': 'Not enough players'})
    try:
        make_game(r); broadcast_game(r)
    except Exception as e:
        emit('error_message', {'message': str(e)})

@socketio.on('select_hukum')
def select_hukum(data):
    r = room_for_sid(request.sid)
    if not r or not r.game: return
    p = r.sessions[request.sid]
    try:
        if data.get('mode') == 'first5':
            r.game.choose_hukum_first_five(data['suit'])
        else:
            r.game.choose_hukum_fallback(data.get('card_indices', []), data['suit'])
        broadcast_game(r)
    except Exception as e:
        emit('error_message', {'message': str(e)})

@socketio.on('play_card')
def play_card(data):
    r = room_for_sid(request.sid)
    if not r or not r.game: return
    p = r.sessions[request.sid]
    try:
        result = r.game.play_card(p, data.get('card_id'))
        if result['trick_complete']:
            socketio.emit('trick_result', {'winner': result['winner']}, room=r.code)
            if r.game.complete:
                for ps in r.game.players.values():
                    ps.shortfall = calculate_shortfall(ps.target, ps.tricks)
                    ps.pending_compensation = ps.shortfall
                r.status = 'ROUND_COMPLETE'
                socketio.emit('round_complete', {'players': [{'id': x.player_id, 'name': x.name, 'target': x.target, 'tricks': x.tricks, 'shortfall': x.shortfall} for x in r.game.players.values()]}, room=r.code)
        broadcast_game(r)
    except Exception as e:
        emit('error_message', {'message': str(e)})

@socketio.on('next_game')
def next_game():
    r = room_for_sid(request.sid)
    if not r or not r.game: return
    if r.sessions.get(request.sid) != r.host_id:
        return emit('error_message', {'message': 'Only the host can start the next game'})
    try:
        old = r.game
        ids = list(old.players)
        previous_comp = {pid_: old.players[pid_].pending_compensation for pid_ in ids}
        if r.game_type == '235':
            targets = rotate_235_targets({pid_: old.players[pid_].target for pid_ in ids})
            new_players = {pid_: PlayerState(pid_, r.players[pid_]['name']) for pid_ in ids}
            r.game = Game235(new_players, targets)
        else:
            new_players = {pid_: PlayerState(pid_, r.players[pid_]['name']) for pid_ in ids}
            r.game = Game78(new_players)
        for pid_ in ids:
            r.game.players[pid_].pending_compensation = previous_comp[pid_]
        r.status = 'IN_PROGRESS'
        broadcast_game(r)
    except Exception as e:
        emit('error_message', {'message': str(e)})

@socketio.on('disconnect')
def disconnected():
    r = room_for_sid(request.sid)
    if r:
        r.remove_session(request.sid)
        broadcast_lobby(r)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
