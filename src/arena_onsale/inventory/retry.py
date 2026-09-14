import random


def jitter_delay_seconds(min_ms: int, max_ms: int, rng: random.Random) -> float:
    """Uniform jitter so colliding GA buyers do not retry in lockstep."""
    if min_ms < 0 or max_ms < min_ms:
        msg = "retry window must satisfy 0 <= min_ms <= max_ms"
        raise ValueError(msg)
    return rng.uniform(min_ms, max_ms) / 1000.0
