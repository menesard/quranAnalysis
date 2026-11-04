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
        value = value.strip()
        if value[:1] in ("'", '"') and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()  # satır sonu yorumu
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

    @property
    def morphology_path(self) -> Path:
        env = os.environ.get("QURAN_MORPHOLOGY_PATH")
        return Path(env) if env else self.data_dir / "quranic-corpus-morphology-0.4.txt"


def get_settings(env_file: str | os.PathLike = ".env") -> Settings:
    load_dotenv(env_file)
    return Settings(
        base_url=os.environ.get("DIB_KURAN_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        token=os.environ.get("DIB_KURAN_API_TOKEN") or None,
        language=os.environ.get("DIB_KURAN_LANGUAGE", "tr"),
        data_dir=Path(os.environ.get("QURAN_DATA_DIR", "data")),
    )
