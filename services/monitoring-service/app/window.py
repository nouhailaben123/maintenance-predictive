from bisect import insort
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Sample:
    message_id: str
    machine_id: str
    seq: int
    timestamp: datetime
    status: str
    values: dict

class Window:
    """Fenêtre glissante triée par timestamp (pas par heure d'arrivée) et dédoublonnée."""

    def __init__(self, size: int):
        self.size = size
        self.items: list = []
        self.ids: set = set()

    def add(self, s: Sample) -> bool:
        """False si doublon (at-least-once : la même mesure peut arriver 2 fois)."""
        if s.message_id in self.ids:
            return False
        insort(self.items, s, key=lambda x: x.timestamp)
        self.ids.add(s.message_id)
        if len(self.items) > self.size:
            self.ids.discard(self.items.pop(0).message_id)
        return True

    def baseline(self, metric: str, skip_last: int) -> list:
        ref = self.items[:-skip_last] if skip_last else self.items
        return [s.values[metric] for s in ref]

    def __len__(self):
        return len(self.items)