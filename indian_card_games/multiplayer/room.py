import secrets, string, time

ALPHABET = 'ABCDEFGHJKLMNPQRTUVWXYZ2346789'

class GameRoom:
    def __init__(self, code, game_type, host_id):
        self.code = code
        self.game_type = game_type
        self.host_id = host_id
        self.players = {}
        self.ready = set()
        self.game = None
        self.status = 'WAITING'
        self.created_at = time.time()
        self.last_activity = self.created_at
        self.sessions = {}

    @property
    def capacity(self):
        return 2 if self.game_type == '78' else 3

    def add_player(self, pid, name, sid):
        if len(self.players) >= self.capacity and pid not in self.players:
            raise ValueError('Room is full')
        if pid not in self.players and any(p['name'].lower() == name.lower() for p in self.players.values()):
            raise ValueError('That name is already in use')
        self.players[pid] = {'name': name, 'connected': True}
        self.sessions[sid] = pid
        self.last_activity = time.time()

    def remove_session(self, sid):
        pid = self.sessions.pop(sid, None)
        if pid and pid in self.players:
            self.players[pid]['connected'] = False
        return pid

    def public_lobby(self):
        return {'code': self.code, 'game_type': self.game_type, 'host_id': self.host_id,
                'status': self.status, 'capacity': self.capacity,
                'players': [{'id': pid, **p} for pid, p in self.players.items()]}

class RoomManager:
    def __init__(self):
        self.rooms = {}

    def code(self):
        while True:
            c = ''.join(secrets.choice(ALPHABET) for _ in range(5))
            if c not in self.rooms:
                return c

    def create(self, game_type, host_id, name, sid):
        if game_type not in ('78', '235'):
            raise ValueError('Invalid game')
        r = GameRoom(self.code(), game_type, host_id)
        r.add_player(host_id, name, sid)
        self.rooms[r.code] = r
        return r

    def get(self, code):
        return self.rooms.get(code.upper())

    def delete(self, code):
        self.rooms.pop(code.upper(), None)
