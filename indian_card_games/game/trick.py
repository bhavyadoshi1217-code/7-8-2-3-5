class Trick:
    def __init__(self):
        self.cards = []
    def add(self, player_id, card):
        self.cards.append((player_id, card))
