def card_public(c):
    return {'id': c.id, 'label': c.label, 'rank': c.rank, 'suit': c.suit}

def serialize_game(game, viewer_id):
    players = []
    for pid, p in game.players.items():
        players.append({
            'id': pid, 'name': p.name, 'target': p.target, 'tricks': p.tricks,
            'hand_count': len(p.hand), 'table_up': [card_public(c) for c in p.table_up],
            'table_down_count': sum(c is not None for c in p.table_down),
            'table_down_slots': [i for i,c in enumerate(p.table_down) if c is not None],
            'shortfall': p.shortfall, 'pending_compensation': p.pending_compensation,
        })
    private = game.players[viewer_id]
    return {
        'players': players,
        'viewer': viewer_id,
        'my_hand': [card_public(c) for c in private.hand],
        'trump': game.trump,
        'current_turn': game.current_turn,
        'trick': [{'player_id': pid, 'card': card_public(card)} for pid, card in game.trick],
        'complete': game.complete,
        'round': game.round_no,
        'trick_history': game.trick_history[-10:],
    }
