"""Ayarlar: ortam değişkenleri ve isteğe bağlı .env dosyası.

Harici bağımlılık olmaması için küçük bir .env okuyucu içerir. Ortamda zaten
tanımlı olan değişkenler .env tarafından ezilmez.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://api.diyanet.gov.tr"


def load_dotenv(path: str | os.PathLike = ".env") -> None:
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    base_url: str
    token: str | None
    language: str
    data_dir: Path

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def corpus_path(self) -> Path:
        return self.data_dir / "quran.json"


def get_settings(env_file: str | os.PathLike = ".env") -> Settings:
    load_dotenv(env_file)
    return Settings(
        base_url=os.environ.get("DIB_KURAN_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        token=os.environ.get("DIB_KURAN_API_TOKEN") or None,
        language=os.environ.get("DIB_KURAN_LANGUAGE", "tr"),
        data_dir=Path(os.environ.get("QURAN_DATA_DIR", "data")),
    )
