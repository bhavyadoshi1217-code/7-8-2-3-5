# Indian Card Games – Updated Compensation Rules

Flask + Flask-SocketIO implementation of 7–8 and 2–3–5.

## Key fixes
- After exactly two preview cards are inspected, Hukum can ONLY be selected from the ordinary suits of those two cards.
- 7♥ and 7♠ never count as ordinary Heart/Spade during Hukum preview.
- If the game creates a shortfall, the shortfall is settled before the next game.
- The shortfall player first chooses either transfer of the owed tricks or card exchange.
- For card exchange, the winning player selects the card from their hand or face-down cards.
- The selected card is exchanged for a card from the shortfall player's hand.
- If the winning player receives 7♥/7♠, they MUST return a Hukum card.
- Target roles rotate separately from compensation.

## Run
`pip install -r requirements.txt`
`python app.py`

## Test
`pytest`

## Render
Use the included `render.yaml`. Keep one Gunicorn worker because room state is in memory.
