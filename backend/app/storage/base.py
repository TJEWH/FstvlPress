from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StoredObject:
    key: str
    url: str
    size: int
    content_type: str
    filename: str


class Storage(ABC):
    @abstractmethod
    async def put(
        self, *, data: bytes, key: str, content_type: str, filename: str
    ) -> StoredObject: ...

    @abstractmethod
    async def delete(self, *, key: str) -> None: ...

    @abstractmethod
    async def get(self, *, key: str) -> bytes | None: ...
