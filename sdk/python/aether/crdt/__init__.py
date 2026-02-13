from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Generic, Iterable, Optional, Set, Tuple, TypeVar


T = TypeVar("T")


@dataclass
class GCounter:
    """Grow-only counter (monotonic per-replica increments)."""

    counts: Dict[str, int] = field(default_factory=dict)

    def add(self, amount: int, replica_id: str) -> None:
        """Increment the counter for a replica by a non-negative amount."""

        if amount < 0:
            raise ValueError("amount must be non-negative")
        self.counts[replica_id] = self.counts.get(replica_id, 0) + amount

    def update(self, other: "GCounter") -> None:
        """Merge another counter by taking per-replica maxima."""

        for replica_id, value in other.counts.items():
            current = self.counts.get(replica_id, 0)
            if value > current:
                self.counts[replica_id] = value

    def remove(self, amount: int, replica_id: str) -> None:
        """No-op for G-Counter; provided for API symmetry."""

        if amount != 0:
            raise ValueError("G-Counter does not support decrements")

    @property
    def value(self) -> int:
        """Return the total value across all replicas."""

        return sum(self.counts.values())


@dataclass
class PNCounter:
    """PN-Counter backed by two grow-only counters (increments/decrements)."""

    positive: GCounter = field(default_factory=GCounter)
    negative: GCounter = field(default_factory=GCounter)

    def add(self, amount: int, replica_id: str) -> None:
        """Increment the counter by a non-negative amount."""

        self.positive.add(amount, replica_id)

    def remove(self, amount: int, replica_id: str) -> None:
        """Decrement the counter by a non-negative amount."""

        self.negative.add(amount, replica_id)

    def update(self, other: "PNCounter") -> None:
        """Merge another counter by merging positive and negative parts."""

        self.positive.update(other.positive)
        self.negative.update(other.negative)

    @property
    def value(self) -> int:
        """Return the total value (positive - negative)."""

        return self.positive.value - self.negative.value


@dataclass
class LWWRegister(Generic[T]):
    """Last-writer-wins register using (timestamp, replica_id) ordering."""

    value: Optional[T] = None
    timestamp: int = 0
    replica_id: str = ""
    tombstone: bool = False

    def update(self, value: T, timestamp: int, replica_id: str) -> None:
        """Set the register if the update is newer by timestamp/replica_id."""

        if (timestamp, replica_id) >= (self.timestamp, self.replica_id):
            self.value = value
            self.timestamp = timestamp
            self.replica_id = replica_id
            self.tombstone = False

    def remove(self, timestamp: int, replica_id: str) -> None:
        """Tombstone the register if the remove is newer."""

        if (timestamp, replica_id) >= (self.timestamp, self.replica_id):
            self.value = None
            self.timestamp = timestamp
            self.replica_id = replica_id
            self.tombstone = True

    def add(self, value: T, timestamp: int, replica_id: str) -> None:
        """Alias for update to align with add/update/remove APIs."""

        self.update(value, timestamp, replica_id)


@dataclass
class ORSet(Generic[T]):
    """Observed-Remove Set with add/remove/update merge semantics."""

    adds: Dict[T, Set[str]] = field(default_factory=dict)
    removes: Dict[T, Set[str]] = field(default_factory=dict)

    def add(self, value: T, tag: str) -> None:
        """Add a value with a unique tag (e.g., UUID)."""

        self.adds.setdefault(value, set()).add(tag)

    def remove(self, value: T, tags: Iterable[str]) -> None:
        """Remove a value by recording observed tags."""

        self.removes.setdefault(value, set()).update(tags)

    def update(self, other: "ORSet[T]") -> None:
        """Merge another OR-Set by unioning add/remove tags."""

        for value, tags in other.adds.items():
            self.adds.setdefault(value, set()).update(tags)
        for value, tags in other.removes.items():
            self.removes.setdefault(value, set()).update(tags)

    def elements(self) -> Set[T]:
        """Return the visible elements after applying removals."""

        visible: Set[T] = set()
        for value, add_tags in self.adds.items():
            removed = self.removes.get(value, set())
            if add_tags - removed:
                visible.add(value)
        return visible


__all__ = [
    "GCounter",
    "PNCounter",
    "LWWRegister",
    "ORSet",
]
