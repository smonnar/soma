from __future__ import annotations

from typing import IO, Any, Dict
from pathlib import Path
import json


class JsonlEventLog:
    """Very small JSONL event logger for M0.

    Each call to `write` appends a one-line JSON object and flushes the file.
    """

    def __init__(self, path: Path):
        self._fh: IO[str] = path.open("a", encoding="utf-8")

    def write(self, event: Dict[str, Any]) -> None:
        json.dump(event, self._fh, ensure_ascii=False)
        self._fh.write("\n")
        self._fh.flush()

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass