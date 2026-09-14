ROOM_ID = "onsale"

QUEUE_KEY = f"waiting:{ROOM_ID}:queue"
SEQ_KEY = f"waiting:{ROOM_ID}:seq"
SHOPPERS_KEY = f"waiting:{ROOM_ID}:shoppers"
RATE_KEY_PREFIX = f"waiting:{ROOM_ID}:rate:"


def token_key(token: str) -> str:
    return f"waiting:{ROOM_ID}:tok:{token}"


def visitor_key(visitor_id: str) -> str:
    return f"waiting:{ROOM_ID}:vis:{visitor_id}"


def rate_key(epoch_second: int) -> str:
    return f"{RATE_KEY_PREFIX}{epoch_second}"


def admits_per_second(per_minute: int) -> int:
    return max(1, (per_minute + 59) // 60)
