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

from . import reference
from .client import ApiError, DiyanetClient


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
        for s in self.surahs:
            if s.id == sid:
                return s
        raise KeyError(f"Sure bulunamadı: {sid}")

    def validate(self) -> list[str]:
        """Veriyi Hafs/Kûfe referans sayılarıyla karşılaştırır; sorun listesi döner."""
        issues: list[str] = []
        ids = [s.id for s in self.surahs]
        missing = sorted(set(range(1, reference.SURAH_COUNT + 1)) - set(ids))
        if missing:
            issues.append(f"Eksik sureler: {missing}")
        extra = sorted(i for i in set(ids) if not 1 <= i <= reference.SURAH_COUNT)
        if extra:
            issues.append(f"Geçersiz sure numaraları: {extra}")
        if len(ids) != len(set(ids)):
            issues.append("Tekrarlanan sure numaraları var")
        for s in self.surahs:
            if not 1 <= s.id <= reference.SURAH_COUNT:
                continue
            exp = reference.expected_verses(s.id)
            nums = [v.n for v in s.verses]
            if len(nums) != exp:
                issues.append(f"{s.id} {s.name_tr}: {exp} ayet bekleniyordu, {len(nums)} var")
            elif nums != list(range(1, exp + 1)):
                issues.append(f"{s.id} {s.name_tr}: ayet numaraları 1..{exp} sırasında değil")
            empty = [v.n for v in s.verses if not v.arabic.strip()]
            if empty:
                issues.append(f"{s.id} {s.name_tr}: Arapça metni boş ayetler {empty[:10]}")
        return issues

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
def _first(d: dict, *keys):
    """Verilen anahtarlardan ilk dolu olanı döndürür (API alan adları sürüme göre değişebilir)."""
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return None


def _int_or_none(v) -> int | None:
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _text(v) -> str:
    """``{"text": ...}`` nesnesi ya da düz metin kabul eder."""
    if isinstance(v, dict):
        return v.get("text") or ""
    return v if isinstance(v, str) else ""


def _chapter_meta(ch: dict) -> Surah:
    sid = _int_or_none(_first(ch, "SureId", "sure_id", "surah_id", "id"))
    if sid is None:
        raise ApiError(0, f"Sure kaydında numara yok: {sorted(ch)[:10]}")
    return Surah(
        id=sid,
        name_tr=_first(ch, "SureNameTurkish", "name_tr", "name") or "",
        name_ar=_first(ch, "SureNameArabic", "name_ar") or "",
        verse_count=_int_or_none(_first(ch, "AyetCount", "verses_count", "verse_count")) or 0,
        revelation_order=_int_or_none(_first(ch, "InisOrder", "revelation_order")),
        juz=_int_or_none(_first(ch, "Cuz", "juz")),
        first_page=_int_or_none(_first(ch, "FirstPage", "first_page")),
        basmala=_first(ch, "BesmeleVisible", "basmala"),
    )


def _verse(raw: dict, surah_id: int) -> Verse:
    arabic = _text(_first(raw, "arabic_script", "text_arabic", "arabic", "text"))
    tr = _text(_first(raw, "translation", "text_translation", "meal"))
    n = _int_or_none(_first(raw, "verse_id_in_surah", "verse_number", "ayet_no", "verse_id"))
    if n is None:
        raise ApiError(0, f"Ayet kaydında ayet numarası yok: {sorted(raw)[:10]}")
    return Verse(
        surah=_int_or_none(_first(raw, "surah_id", "sure_id")) or surah_id,
        n=n,
        arabic=arabic,
        translation=tr,
        page=_int_or_none(_first(raw, "page_number", "page")),
    )


def build_corpus(client: DiyanetClient, progress: Callable[[str], None] | None = None) -> Corpus:
    surahs = sorted((_chapter_meta(c) for c in client.chapters()), key=lambda s: s.id)
    for s in surahs:
        if progress:
            progress(f"{s.id:3d}/114 {s.name_tr}")
        seen: dict[int, Verse] = {}
        for raw in client.chapter_verses(s.id):
            v = _verse(raw, s.id)
            if v.surah != s.id:  # başka sureye ait kayıt karışmışsa atla
                continue
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
