# Indian Card Games – 7–8 and 2–3–5
Flask + Flask-SocketIO. Run locally: `pip install -r requirements.txt && python app.py` → http://localhost:5000
Tests: `pytest`

## Deploy (GitHub → Render)
1. Push this folder to a GitHub repo.
2. Render → New → Blueprint (reads render.yaml), or New Web Service with:
   Build `pip install -r requirements.txt`, Start `gunicorn --worker-class gthread --threads 100 -w 1 -b 0.0.0.0:$PORT app:app`.
3. Keep **one worker** (rooms live in memory). Free instances sleep and lose rooms.

## Implemented
30-card deck, special 7♥/7♠, follow-suit, trick winner, Hukum selection (first five / two of next five),
7–8 face-up/face-down reveal, 2–3–5 target rotation (5→2, 3→5, 2→3), shortfall carried to next game,
rooms, invite links, WhatsApp share, private state per player, reconnect via saved token.

## NOT yet implemented (rules unspecified)
Compensation settlement and card exchange (shortfall is only recorded as `carry`), 7–8 role transition
(`KEEP_78_ROLES` in engine.py), database, Redis, sounds, disconnect timeout.
