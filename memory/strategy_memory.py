"""Strategy memory retrieval and persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path

from schemas.strategy import StrategyMemorySnapshot, StrategyUpdate
from tools.neo4j_store import Neo4jStore


class StrategyMemory:
    """Reads and writes reflection-derived strategy updates."""

    def __init__(self, neo4j_store: Neo4jStore, local_cache_path: Path) -> None:
        self.neo4j_store = neo4j_store
        self.local_cache_path = local_cache_path

    def load_snapshot(self, topic: str, limit: int = 8) -> StrategyMemorySnapshot:
        hints: list[str] = []
        updates: list[StrategyUpdate] = []
        if self.neo4j_store.enabled and self.neo4j_store.has_schema(
            labels=["StrategyUpdate", "Topic"],
            rel_types=["ABOUT_TOPIC"],
        ):
            hints = self.neo4j_store.fetch_strategy_hints(topic, limit=limit)

        local_data = self._load_local_cache().get(topic, [])
        for item in local_data[-limit:]:
            try:
                update = StrategyUpdate.model_validate(item)
                updates.append(update)
                hints.append(update.recommendation)
            except Exception:
                continue

        deduped_hints = list(dict.fromkeys(hints))
        return StrategyMemorySnapshot(topic=topic, hints=deduped_hints[:limit], updates=updates)

    def persist_updates(self, topic: str, updates: list[StrategyUpdate]) -> None:
        if not updates:
            return
        if self.neo4j_store.enabled:
            for update in updates:
                self.neo4j_store.upsert_strategy_update(topic, update.model_dump(mode="json"))

        cache = self._load_local_cache()
        existing = cache.get(topic, [])
        existing.extend(update.model_dump(mode="json") for update in updates)
        cache[topic] = existing[-100:]
        self._write_local_cache(cache)

    def _load_local_cache(self) -> dict[str, list[dict[str, object]]]:
        if not self.local_cache_path.exists():
            return {}
        try:
            return json.loads(self.local_cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_local_cache(self, data: dict[str, list[dict[str, object]]]) -> None:
        self.local_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.local_cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
