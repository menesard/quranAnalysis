"""API verisini tek, kararlı bir JSON şemasına dönüştürür ve yükler.

Şema (data/quran.json):
{
  "source": {...},
  "surahs": [
    {"id": 1, "name_tr": "...", "name_ar": "...", "verse_count": 7,
     "revelation_order": 5, "juz": 1, "first_page": 1, "basmala": false,
     "verses": [{"n": 1, "page": 1, "arabic": "...", "translation": "..."}]}
  ]
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

from .client import DiyanetClient


@dataclass
class Verse:
    surah: int
    n: int
    arabic: str
    translation: str = ""
    page: int | None = None


@dataclass
class Surah:
    id: int
    name_tr: str
    name_ar: str
    verse_count: int
    revelation_order: int | None = None
    juz: int | None = None
    first_page: int | None = None
    basmala: bool | None = None
    verses: list[Verse] = field(default_factory=list)

    @property
    def revelation_place(self) -> str | None:
        return MEDINAN.get(self.id, "mekki") if self.id else None


# Yaygın kabul gören (Diyanet/Kral Fahd mushafı başlıkları) Medenî sure listesi.
# API bu bilgiyi doğrudan vermediği için burada tutulur.
_MEDINAN_IDS = {2, 3, 4, 5, 8, 9, 13, 22, 24, 33, 47, 48, 49, 55, 57, 58, 59, 60,
                61, 62, 63, 64, 65, 66, 76, 98, 99, 110}
MEDINAN = {i: "medeni" for i in _MEDINAN_IDS}


@dataclass
class Corpus:
    surahs: list[Surah]
    source: dict = field(default_factory=dict)

    def verses(self) -> Iterator[Verse]:
        for s in self.surahs:
            yield from s.verses

    def surah(self, sid: int) -> Surah:
        return next(s for s in self.surahs if s.id == sid)

    # -- kaydet / yükle -----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "surahs": [
                {
                    **{k: v for k, v in s.__dict__.items() if k != "verses"},
                    "verses": [
                        {"n": v.n, "page": v.page, "arabic": v.arabic, "translation": v.translation}
                        for v in s.verses
                    ],
                }
                for s in self.surahs
            ],
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def from_dict(cls, d: dict) -> "Corpus":
        surahs = []
        for s in d["surahs"]:
            verses = [Verse(surah=s["id"], **v) for v in s.get("verses", [])]
            meta = {k: v for k, v in s.items() if k != "verses"}
            surahs.append(Surah(**meta, verses=verses))
        return cls(surahs=surahs, source=d.get("source", {}))

    @classmethod
    def load(cls, path: Path) -> "Corpus":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# -- API -> Corpus ----------------------------------------------------------
def _chapter_meta(ch: dict) -> Surah:
    g = ch.get
    return Surah(
        id=int(g("SureId") or g("id")),
        name_tr=g("SureNameTurkish") or g("name_tr") or "",
        name_ar=g("SureNameArabic") or g("name_ar") or "",
        verse_count=int(g("AyetCount") or g("verses_count") or 0),
        revelation_order=g("InisOrder"),
        juz=g("Cuz"),
        first_page=g("FirstPage"),
        basmala=g("BesmeleVisible"),
    )


def _verse(raw: dict, surah_id: int) -> Verse:
    arabic = (raw.get("arabic_script") or {}).get("text") or raw.get("text_arabic") or ""
    tr = (raw.get("translation") or {}).get("text") or ""
    return Verse(
        surah=int(raw.get("surah_id") or surah_id),
        n=int(raw["verse_id_in_surah"]),
        arabic=arabic,
        translation=tr,
        page=raw.get("page_number"),
    )


def build_corpus(client: DiyanetClient, progress: Callable[[str], None] | None = None) -> Corpus:
    surahs = sorted((_chapter_meta(c) for c in client.chapters()), key=lambda s: s.id)
    for s in surahs:
        if progress:
            progress(f"{s.id:3d}/114 {s.name_tr}")
        seen: dict[int, Verse] = {}
        for raw in client.chapter_verses(s.id):
            v = _verse(raw, s.id)
            seen.setdefault(v.n, v)  # API bazen aynı ayeti tekrarlıyor
        s.verses = [seen[k] for k in sorted(seen)]
        if s.verse_count and len(s.verses) != s.verse_count:
            if progress:
                progress(f"  UYARI: {s.name_tr} için {s.verse_count} ayet beklendi, {len(s.verses)} geldi")
    return Corpus(
        surahs=surahs,
        source={
            "api": client.base_url,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "language": client.language,
        },
    )
