from __future__ import annotations
import hashlib
import json


def compute_etag(payload: object) -> str:
    raw = json.dumps(
        payload, default=str, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
