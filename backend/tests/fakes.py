"""Implementaciones en memoria de los puertos, para tests sin infraestructura."""


class FakeDatabaseProbe:
    def __init__(self, *, reachable: bool) -> None:
        self.reachable = reachable
        self.calls = 0

    async def is_reachable(self) -> bool:
        self.calls += 1
        return self.reachable
