# Indian Card Games — 7–8 and 2–3–5

A Flask multiplayer implementation of 7–8 and 2–3–5 using the 30-card deck and server-authoritative game engine.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000.

## Render

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
gunicorn --worker-class gthread --threads 8 -w 1 -b 0.0.0.0:$PORT app:app
```

One worker is intentional because room/game state is currently held in memory. Use Redis/database before scaling to multiple instances.

## Multiplayer transport

This final version uses short HTTP polling for game state instead of Socket.IO/WebSockets. That avoids WebSocket/proxy upgrade problems and makes room creation/joining reliable across phones, computers and browsers on Render.

## Implemented

- Exact 30-card deck: 8-A in four suits plus 7♥ and 7♠.
- 7♥ highest, 7♠ second highest; both treated as Hukum for following suit.
- 7–8: two players, 8/7 targets, 5 hand + 5 face-down + 5 face-up.
- 2–3–5: three players, 5/3/2 targets, ten cards each.
- Hukum selection from first five, with two-card fallback from the next five.
- Follow-suit validation and server-authoritative trick resolution.
- 7–8 face-up card reveal of its paired face-down card.
- 2–3–5 target rotation 5→2, 3→5, 2→3.
- Shortfall recorded and carried to the next game.
- Private player state is filtered server-side.
- Room codes and shareable join links.
- Reconnect/session recovery using a browser session token.

## Not implemented because the exact negotiation mechanics were not fully specified

The shortfall is recorded as a pending obligation, but the interactive settlement choice between tricks, card exchange, and mixed settlement is not yet implemented.

### Hukum setup sequence
- **7–8:** both players first receive 5 cards and their face-down table cards are placed. The 8-trick player may choose Hukum from the first 5 immediately, or inspect exactly 2 of the 5 cards that will be face-up. Once the two-card preview is taken, all 5 face-up cards are revealed.
- **2–3–5:** the 5-trick player first receives 5 cards; the other two players receive their full 10 cards. The 5-trick player may choose Hukum from the first 5 immediately, or inspect exactly 2 of the remaining 5 cards. After Hukum is chosen, all 5 remaining cards go into the selector's hand.
- A Hukum selected after the two-card preview must be one of the suits represented by those two cards.
