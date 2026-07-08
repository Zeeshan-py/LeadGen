"""Coverage and quality reporting helpers for lead automation output."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class CoverageTracker:
    def __init__(self, coverage_file: Path) -> None:
        self.path = coverage_file
        self._data: dict = self._load()

    def is_complete(self, market: str) -> bool:
        return self._data.get(market, {}).get("status") == "complete"

    def record_run(
        self,
        market: str,
        query_count: int,
        requested_results: int,
        written_results: int,
        mode: str = "upsert",
    ) -> None:
        self._data[market] = {
            "status": "complete",
            "last_run": datetime.now(timezone.utc).isoformat(),
            "query_count": query_count,
            "requested_results": requested_results,
            "written_results": written_results,
            "mode": mode,
        }
        self._save()

    def pending_markets(self, all_markets: list[str]) -> list[str]:
        return [m for m in all_markets if not self.is_complete(m)]

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception:
                return {}
        return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))
