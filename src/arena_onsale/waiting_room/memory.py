from arena_onsale.waiting_room.store import Shopper


class InMemoryWaitingRoomStore:
    def __init__(self) -> None:
        self.queue: dict[str, float] = {}
        self.shoppers: dict[str, Shopper] = {}
        self.tokens: dict[str, str] = {}
        self.seq = 0
        self.rate: dict[int, int] = {}

    async def next_score(self) -> float:
        self.seq += 1
        return float(self.seq)

    async def enqueue(self, visitor_id: str, score: float) -> bool:
        if visitor_id in self.queue:
            return False
        self.queue[visitor_id] = score
        return True

    async def rank(self, visitor_id: str) -> int | None:
        if visitor_id not in self.queue:
            return None
        ordered = sorted(self.queue, key=lambda vid: self.queue[vid])
        return ordered.index(visitor_id)

    async def queue_size(self) -> int:
        return len(self.queue)

    async def pop_front(self, n: int) -> list[str]:
        if n <= 0:
            return []
        ordered = sorted(self.queue, key=lambda vid: self.queue[vid])
        taken = ordered[:n]
        for visitor_id in taken:
            del self.queue[visitor_id]
        return taken

    async def put_shopper(self, shopper: Shopper, ttl_seconds: int) -> None:
        del ttl_seconds
        self.shoppers[shopper.visitor_id] = shopper
        self.tokens[shopper.token] = shopper.visitor_id

    async def get_shopper(self, visitor_id: str) -> Shopper | None:
        return self.shoppers.get(visitor_id)

    async def visitor_for_token(self, token: str) -> str | None:
        visitor_id = self.tokens.get(token)
        if visitor_id is None:
            return None
        shopper = self.shoppers.get(visitor_id)
        if shopper is None or shopper.token != token:
            return None
        return visitor_id

    async def gc_shoppers(self, now: float) -> None:
        expired = [
            visitor_id for visitor_id, shopper in self.shoppers.items() if shopper.expires_at <= now
        ]
        for visitor_id in expired:
            shopper = self.shoppers.pop(visitor_id)
            self.tokens.pop(shopper.token, None)

    async def shopper_count(self, now: float) -> int:
        return sum(1 for shopper in self.shoppers.values() if shopper.expires_at > now)

    async def take_rate_tokens(self, epoch_second: int, limit: int, wanted: int) -> int:
        if wanted <= 0 or limit <= 0:
            return 0
        current = self.rate.get(epoch_second, 0)
        remaining = max(0, limit - current)
        granted = min(wanted, remaining)
        self.rate[epoch_second] = current + granted
        return granted
