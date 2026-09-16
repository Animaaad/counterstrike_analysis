MIN_MAPS = 50

def get_weight(m):
    if m <= 3:
        return 0.37
    elif m <= 6:
        return 0.32
    elif m <= 9:
        return 0.21
    else:
        return 0.1