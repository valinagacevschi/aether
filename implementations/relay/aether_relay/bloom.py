"""Simple Bloom filter for event_id deduplication."""

from __future__ import annotations

from dataclasses import dataclass

from blake3 import blake3


@dataclass
class BloomFilter:
    size_bits: int
    hash_count: int

    def __post_init__(self) -> None:
        if self.size_bits <= 0:
            raise ValueError("size_bits must be positive")
        if self.hash_count <= 0:
            raise ValueError("hash_count must be positive")
        self._bits = bytearray((self.size_bits + 7) // 8)

    def add(self, data: bytes) -> None:
        for index in self._indices(data):
            self._set_bit(index)

    def might_contain(self, data: bytes) -> bool:
        return all(self._get_bit(index) for index in self._indices(data))

    def _indices(self, data: bytes) -> list[int]:
        indices: list[int] = []
        for i in range(self.hash_count):
            digest = blake3(data + i.to_bytes(2, "big")).digest()
            value = int.from_bytes(digest[:8], "big")
            indices.append(value % self.size_bits)
        return indices

    def _set_bit(self, index: int) -> None:
        byte_index, bit_index = divmod(index, 8)
        self._bits[byte_index] |= 1 << bit_index

    def _get_bit(self, index: int) -> bool:
        byte_index, bit_index = divmod(index, 8)
        return bool(self._bits[byte_index] & (1 << bit_index))
