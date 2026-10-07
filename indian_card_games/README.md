# Indian Card Games — 7–8 and 2–3–5

A Flask + Socket.IO multiplayer implementation of the specified 30-card Indian trick-taking games.

## Features

- One website with 7–8 and 2–3–5 selection
- Private rooms with 5-character codes
- Shareable `/join/<code>` invitation links
- Real-time Socket.IO gameplay
- Server-authoritative turns and card validation
- Private player hands
- 30-card deck with special 7♥ and 7♠
- 7–8 hand/table card structure
- Hukum selection and fallback selection
- 2–3–5 target rotation
- Shortfall state carried into the next game
- Responsive mobile UI

## Run locally

Python 3.11+ is recommended.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Tests

```bash
pytest
```

## Render

Push the repository to GitHub and create a Render Web Service. Render can use the included `render.yaml` or:

Build command:

`pip install -r requirements.txt`

Start command:

`gunicorn --worker-class eventlet -w 1 app:app`

Set a strong `SECRET_KEY` in Render. For a multi-instance deployment, add a shared Socket.IO message broker such as Redis and adapt `RoomStorage` accordingly.

## Important implementation note

The project deliberately keeps gameplay logic separate from the web layer. The current implementation provides a working multiplayer MVP and explicit game-state fields for shortfall/compensation. The exact settlement negotiation for a shortfall (tricks vs cards vs combination) is kept as a distinct phase so additional house-specific settlement UI can be added without changing the trick engine.
