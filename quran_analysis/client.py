"""Diyanet Açık Kaynak Kur'an API istemcisi.

Bilinen uç noktalar (Diyanet'in kendi açık kaynak istemcisi diyanet-bid/Kuran
deposundan alınmıştır):

    GET {base}/api/v1/chapters              -> sure listesi
    GET {base}/api/v1/chapters/{sure_id}    -> surenin ayetleri
    GET {base}/api/v1/verses/page/{sayfa}   -> mushaf sayfasındaki ayetler

Kimlik doğrulama: ``Authorization: Bearer <token>``.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .cache import JsonCache


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


class DiyanetClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        cache: JsonCache | None = None,
        language: str | None = None,
        timeout: float = 30.0,
        retries: int = 3,
        min_interval: float = 0.2,
    ):
        if not token:
            raise ValueError(
                "API token eksik. .env dosyasına DIB_KURAN_API_TOKEN değerini girin."
            )
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.cache = cache
        self.language = language
        self.timeout = timeout
        self.retries = retries
        self.min_interval = min_interval
        self._last_request = 0.0

    def __repr__(self) -> str:  # token'ı asla loglara yazma
        return f"DiyanetClient(base_url={self.base_url!r})"

    # -- düşük seviye -----------------------------------------------------
    def get(self, path: str, params: dict[str, Any] | None = None, use_cache: bool = True) -> Any:
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base_url}/{path.lstrip('/')}" + (f"?{query}" if query else "")
        cache_key = url.removeprefix(self.base_url)
        if use_cache and self.cache is not None:
            hit = self.cache.get(cache_key)
            if hit is not None:
                return hit

        data = self._request(url)
        if self.cache is not None:
            self.cache.set(cache_key, data)
        return data

    def _request(self, url: str) -> Any:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "quran-analysis/0.1",
        }
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:300]
                if e.code in (429, 500, 502, 503, 504) and attempt + 1 < self.retries:
                    time.sleep(2 ** attempt)
                    last_exc = e
                    continue
                raise ApiError(e.code, body) from None
            except urllib.error.URLError as e:
                last_exc = e
                time.sleep(2 ** attempt)
        raise ApiError(0, f"Bağlantı kurulamadı: {last_exc}")

    def _lang_params(self) -> dict[str, Any]:
        return {"language": self.language} if self.language else {}

    # -- yüksek seviye ----------------------------------------------------
    def chapters(self) -> list[dict]:
        return _unwrap(self.get("/api/v1/chapters", self._lang_params()))

    def chapter_verses(self, chapter_id: int) -> list[dict]:
        return _unwrap(self.get(f"/api/v1/chapters/{chapter_id}", self._lang_params()))

    def page_verses(self, page: int) -> list[dict]:
        return _unwrap(self.get(f"/api/v1/verses/page/{page}", self._lang_params()))


def _unwrap(payload: Any) -> list[dict]:
    if isinstance(payload, dict) and "data" in payload:
        payload = payload["data"]
    if not isinstance(payload, list):
        raise ApiError(0, f"Beklenmeyen yanıt biçimi: {type(payload).__name__}")
    return payload
