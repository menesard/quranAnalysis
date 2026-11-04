"""Basit dosya tabanlı JSON önbellek.

Her API yanıtı istek yoluna göre adlandırılmış bir dosyada saklanır; böylece
analizler tekrar tekrar API'ye gitmeden çalışır ve sonuçlar tekrarlanabilir olur.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


class JsonCache:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def _path(self, key: str) -> Path:
        slug = re.sub(r"[^A-Za-z0-9]+", "_", key).strip("_")[:80]
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        return self.directory / f"{slug}_{digest}.json"

    def get(self, key: str) -> Any | None:
        p = self._path(key)
        if not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def set(self, key: str, value: Any) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        p = self._path(key)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
