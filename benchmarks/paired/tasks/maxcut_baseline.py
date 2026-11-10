"""Seeded multi-start, best-improvement one-vertex Max-Cut local search."""
import random


def solve(n, edges, seed):
    adjacency = [[] for _ in range(n)]
    for u, v, weight in edges:
        adjacency[u].append((v, weight))
        adjacency[v].append((u, weight))
    rng = random.Random(seed)
    best_cut, best = 0, [0] * n
    for _ in range(8):
        partition = [rng.randrange(2) for _ in range(n)]
        gains = [0] * n
        cut = 0
        for u, v, weight in edges:
            crossed = partition[u] != partition[v]
            cut += weight if crossed else 0
            gain = -weight if crossed else weight
            gains[u] += gain
            gains[v] += gain
        while True:
            vertex = max(range(n), key=gains.__getitem__)
            gain = gains[vertex]
            if gain <= 0:
                break
            cut += gain
            partition[vertex] ^= 1
            gains[vertex] = -gain
            for neighbor, weight in adjacency[vertex]:
                gains[neighbor] += 2 * weight if partition[neighbor] == partition[vertex] else -2 * weight
        if cut > best_cut:
            best_cut, best = cut, partition[:]
    return best
