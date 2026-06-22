from __future__ import annotations

import asyncio
from time import monotonic
from typing import Any, Awaitable, Callable

from fastapi import Response


MAX_CACHE_ENTRIES = 512
DEFAULT_PURGE_INTERVAL_SECONDS = 60

_TTL_CACHE: dict[str, tuple[float, Any]] = {}
_KEY_LOCKS: dict[str, asyncio.Lock] = {}


def _drop_cache_entry(key: str) -> None:
    _TTL_CACHE.pop(key, None)
    lock = _KEY_LOCKS.get(key)
    if lock is not None and not lock.locked():
        _KEY_LOCKS.pop(key, None)


def purge_expired_ttl_cache() -> int:
    now = monotonic()
    expired_keys = [
        cache_key
        for cache_key, (expires_at, _) in list(_TTL_CACHE.items())
        if expires_at <= now
    ]
    for cache_key in expired_keys:
        _drop_cache_entry(cache_key)
    return len(expired_keys)


def get_ttl_cache(key: str) -> Any | None:
    entry = _TTL_CACHE.get(key)
    if not entry:
        return None

    expires_at, value = entry
    if expires_at <= monotonic():
        _drop_cache_entry(key)
        return None

    return value


def set_ttl_cache(key: str, value: Any, ttl_seconds: int) -> None:
    now = monotonic()
    purge_expired_ttl_cache()

    if len(_TTL_CACHE) >= MAX_CACHE_ENTRIES:
        oldest_key = min(_TTL_CACHE, key=lambda cache_key: _TTL_CACHE[cache_key][0])
        _drop_cache_entry(oldest_key)

    _TTL_CACHE[key] = (now + max(1, int(ttl_seconds or 1)), value)


def invalidate_ttl_cache_key(key: str) -> int:
    """Remove one public cache entry if present."""
    if key not in _TTL_CACHE:
        return 0
    _drop_cache_entry(key)
    return 1


def invalidate_ttl_cache_prefix(prefix: str) -> int:
    """Remove public cache entries whose keys start with the given prefix."""
    normalized_prefix = str(prefix or "")
    if not normalized_prefix:
        return 0
    matching_keys = [
        cache_key
        for cache_key in list(_TTL_CACHE.keys())
        if cache_key.startswith(normalized_prefix)
    ]
    for cache_key in matching_keys:
        _drop_cache_entry(cache_key)
    return len(matching_keys)


async def get_or_set_ttl_cache(
    key: str,
    ttl_seconds: int,
    factory: Callable[[], Awaitable[Any]],
) -> Any:
    cached = get_ttl_cache(key)
    if cached is not None:
        return cached

    lock = _KEY_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _KEY_LOCKS[key] = lock

    async with lock:
        cached = get_ttl_cache(key)
        if cached is not None:
            return cached

        value = await factory()
        set_ttl_cache(key, value, ttl_seconds)
        return value


async def ttl_cache_maintenance_loop(
    interval_seconds: int = DEFAULT_PURGE_INTERVAL_SECONDS,
) -> None:
    interval = max(1, int(interval_seconds or DEFAULT_PURGE_INTERVAL_SECONDS))
    while True:
        await asyncio.sleep(interval)
        purge_expired_ttl_cache()


def set_public_cache_headers(
    response: Response,
    *,
    max_age: int,
    stale_while_revalidate: int = 0,
) -> None:
    directives = ["public", f"max-age={max(0, int(max_age or 0))}"]
    if stale_while_revalidate > 0:
        directives.append(f"stale-while-revalidate={int(stale_while_revalidate)}")
    response.headers["Cache-Control"] = ", ".join(directives)
