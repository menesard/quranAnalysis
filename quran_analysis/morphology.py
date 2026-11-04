"""Kök ve lemma bazlı sayım (Quranic Arabic Corpus morfoloji verisiyle).

Arapçada bir kökten (ör. ر ح م) onlarca kelime türer: رحمة، الرحمن، رحيم ...
Kelimeyi birebir aramak bu türevleri kaçırır. Güvenilir kök bilgisi, el ile
doğrulanmış Quranic Arabic Corpus (corpus.quran.com, Leeds Üniversitesi)
morfoloji dosyasından alınır. Dosya GNU GPL lisanslıdır ve bu depoya
eklenmez; şuradan indirilip ``data/`` altına konmalıdır:

    https://corpus.quran.com/download/  ->  quranic-corpus-morphology-0.4.txt

Dosya biçimi (sekme ile ayrılmış, ``#`` ile başlayan satırlar yorum):

    LOCATION    FORM    TAG    FEATURES
    (1:1:1:2)   somi    N      STEM|POS:N|LEM:{som|ROOT:smw|M|GEN

LOCATION = (sure:ayet:kelime:parça). Bir kelime birden çok parçadan (ön ek,
gövde, son ek) oluşur; kök bilgisi gövdededir. Sayım kelime başına yapılır:
aynı kelimede kök bir kez sayılır.

Not: Bu veri Tanzil Osmanî metnine dayanır; kelime sınırları Diyanet metninin
boşluk bazlı ayrımından farklı olabilir. Kök sayıları bu yüzden ``word``
komutunun sayılarıyla doğrudan karşılaştırılmamalıdır.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from . import arabic

# Quranic Arabic Corpus'un kullandığı genişletilmiş Buckwalter harf çevirisi
BUCKWALTER = {
    "'": "ء", ">": "أ", "&": "ؤ", "<": "إ", "}": "ئ", "A": "ا", "b": "ب", "p": "ة",
    "t": "ت", "v": "ث", "j": "ج", "H": "ح", "x": "خ", "d": "د", "*": "ذ", "r": "ر",
    "z": "ز", "s": "س", "$": "ش", "S": "ص", "D": "ض", "T": "ط", "Z": "ظ", "E": "ع",
    "g": "غ", "_": "ـ", "f": "ف", "q": "ق", "k": "ك", "l": "ل", "m": "م", "n": "ن",
    "h": "ه", "w": "و", "Y": "ى", "y": "ي", "F": "ً", "N": "ٌ", "K": "ٍ", "a": "َ",
    "u": "ُ", "i": "ِ", "~": "ّ", "o": "ْ", "`": "ٰ", "{": "ٱ", "|": "آ", "^": "ٓ",
    "#": "ٔ", ":": "ۜ", "@": "۟", '"': "۠", "[": "ۢ", ";": "ۣ", ",": "ۥ", ".": "ۦ",
    "!": "ۨ", "-": "۪", "+": "۫", "%": "۬", "]": "ۭ",
}

# Köklerde hemzenin tüm yazımları tek harf (ء) sayılır
_ROOT_FOLD = {"أ": "ء", "إ": "ء", "آ": "ء", "ؤ": "ء", "ئ": "ء", "ٱ": "ا", "ى": "ي"}

_LOCATION = re.compile(r"\((\d+):(\d+):(\d+):(\d+)\)")


def buckwalter_to_arabic(text: str) -> str:
    return "".join(BUCKWALTER.get(c, c) for c in text)


def normalize_root(root: str) -> str:
    """Arapça veya Buckwalter yazılmış kökü karşılaştırılabilir biçime getirir.

    ``رحم``, ``ر ح م``, ``رَحِمَ`` ve ``rHm`` aynı sonucu verir.
    """
    root = root.strip()
    if root and all(ord(c) < 128 for c in root.replace(" ", "")):
        root = buckwalter_to_arabic(root.replace(" ", ""))
    letters = arabic.letters(root)
    return "".join(_ROOT_FOLD.get(c, c) for c in letters)


@dataclass(frozen=True)
class MorphWord:
    surah: int
    verse: int
    word: int
    root: str | None   # Arapça harflerle, ör. "رحم"
    lemma: str | None  # Arapça harflerle (harekeli)
    pos: str | None    # gövdenin sözcük türü (N, V, PN, ADJ ...)


def parse(lines: Iterable[str]) -> list[MorphWord]:
    """Morfoloji satırlarını kelime düzeyinde birleştirir."""
    words: dict[tuple[int, int, int], dict] = {}
    for line in lines:
        line = line.rstrip("\n")
        if not line or line.startswith("#") or line.startswith("LOCATION"):
            continue
        cols = line.split("\t")
        if len(cols) < 4:
            continue
        m = _LOCATION.fullmatch(cols[0].strip())
        if not m:
            continue
        s, v, w, _ = (int(x) for x in m.groups())
        entry = words.setdefault((s, v, w), {"root": None, "lemma": None, "pos": None})
        feats = cols[3].split("|")
        is_stem = "STEM" in feats
        for f in feats:
            key, _, val = f.partition(":")
            if key == "ROOT" and val and entry["root"] is None:
                entry["root"] = normalize_root(val)
            elif key == "LEM" and val and (entry["lemma"] is None or is_stem):
                entry["lemma"] = buckwalter_to_arabic(val)
        if is_stem:
            entry["pos"] = cols[2].strip()
    return [MorphWord(s, v, w, **e) for (s, v, w), e in sorted(words.items())]


def load(path: str | Path) -> list[MorphWord]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(
            f"{p} bulunamadı. quranic-corpus-morphology-0.4.txt dosyasını "
            "https://corpus.quran.com/download/ adresinden indirip bu yola koyun."
        )
    with p.open(encoding="utf-8") as f:
        return parse(f)


def root_frequency(words: Iterable[MorphWord]) -> Counter:
    return Counter(w.root for w in words if w.root)


def lemma_frequency(words: Iterable[MorphWord]) -> Counter:
    return Counter(w.lemma for w in words if w.lemma)


def count_root(words: Iterable[MorphWord], root: str) -> dict:
    """Bir kökten türeyen kelimelerin sayısı, lemma dağılımı ve geçtiği yerler."""
    target = normalize_root(root)
    if not target:
        raise ValueError(f"Geçersiz kök: {root!r}")
    hits = [w for w in words if w.root == target]
    by_verse: dict[tuple[int, int], int] = defaultdict(int)
    for w in hits:
        by_verse[(w.surah, w.verse)] += 1
    by_surah = Counter(w.surah for w in hits)
    return {
        "root": target,
        "root_spaced": " ".join(target),
        "total": len(hits),
        "verse_count": len(by_verse),
        "surah_count": len(by_surah),
        "lemmas": dict(Counter(w.lemma for w in hits if w.lemma).most_common()),
        "by_surah": dict(sorted(by_surah.items())),
        "verses": [(s, v, n) for (s, v), n in sorted(by_verse.items())],
    }
