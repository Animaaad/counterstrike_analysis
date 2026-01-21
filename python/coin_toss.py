import numpy as np
from collections import Counter

def simulate_unfair_coins(n, p, num_simulations=50000):
    """
    Simulate num_simulations experiments of n unfair coin tosses.
    
    Parameters:
        n (int): number of tosses per experiment
        p (float): probability of heads
        num_simulations (int): number of experiments
    
    Returns:
        np.ndarray: array of heads counts (length = num_simulations)
    """
    return np.random.binomial(n=n, p=p, size=num_simulations)

def count_around_half(results, n, p):
    """
    Count how many simulations resulted in k heads,
    grouped by offset from n/2.

    Parameters:
        results (array-like): heads counts from simulations
        n (int): number of tosses per simulation

    Returns:
        dict: {offset_from_half: count}
              where offset = heads - (n/2)
    """
    half = n * p
    print(half)
    offsets = [heads - half for heads in results]
    return dict(Counter(offsets))

def print_tail_probabilities(results, n, p):
    """
    Print cumulative probabilities around n/2:
    - for x <= n/2: P(heads <= x)
    - for x >= n/2: P(heads >= x)
    """
    total = len(results)
    half = n * p

    # sort results once
    sorted_results = sorted(results)

    # precompute cumulative counts
    from bisect import bisect_right, bisect_left

    unique_xs = sorted(set(results))

    for x in unique_xs:
        if x <= half:
            count = bisect_right(sorted_results, x)
            prob = count / total
            print(f"x = {x}: P(heads <= {x}) = {prob:.4f}")
        else:
            count = total - bisect_left(sorted_results, x)
            prob = count / total
            print(f"x = {x}: P(heads >= {x}) = {prob:.4f}")



# Example usage
n = 67      # tosses per experiment
p = 0.45    # probability of heads

results = simulate_unfair_coins(n, p)

counts = count_around_half(results, n, p)

for offset in sorted(counts):
    print(f"{n * p} {offset:+}: {counts[offset]}")

print_tail_probabilities(results, n, p)
