def calculate_shortfall(target, actual):
    return max(0, target - actual)


def rotate_235_targets(targets):
    return {pid: {5: 2, 3: 5, 2: 3}[target] for pid, target in targets.items()}
