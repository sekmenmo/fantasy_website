from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session

from app.database.models import CacheEntry
from app.database.session import engine


class JsonCache:
    def get(self, key: str) -> Any | None:
        now = datetime.now(UTC)
        with Session(engine) as session:
            entry = session.get(CacheEntry, key)
            if entry is None:
                return None
            if entry.expires_at and entry.expires_at.replace(tzinfo=UTC) <= now:
                return None
            return json.loads(entry.payload)

    def get_stale(self, key: str) -> Any | None:
        with Session(engine) as session:
            entry = session.get(CacheEntry, key)
            if entry is None:
                return None
            return json.loads(entry.payload)

    def updated_at(self, key: str) -> datetime | None:
        with Session(engine) as session:
            entry = session.get(CacheEntry, key)
            if entry is None:
                return None
            return entry.updated_at

    def set(self, key: str, payload: Any, ttl_seconds: int | None = None) -> None:
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds) if ttl_seconds else None
        serialized = json.dumps(payload)
        with Session(engine) as session:
            entry = session.get(CacheEntry, key)
            if entry is None:
                entry = CacheEntry(
                    key=key,
                    payload=serialized,
                    updated_at=now,
                    expires_at=expires_at,
                )
            else:
                entry.payload = serialized
                entry.updated_at = now
                entry.expires_at = expires_at
            session.add(entry)
            session.commit()
