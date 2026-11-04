"""Arapça metin işleme: normalleştirme, kelime ve harf ayrıştırma, ebced.

ÖNEMLİ: Kelime/harf sayıları hangi imla (Osmanî resm, basit imla), hangi
işaretlerin harf sayıldığı ve kelime sınırlarının nasıl belirlendiğine göre
değişir. Bu modüldeki her tercih bir parametredir; raporlarda hangi ayarın
kullanıldığı mutlaka belirtilmelidir.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

# Harekeler ve Kur'an'a özgü okuma/durak işaretleri
HARAKAT = set(range(0x064B, 0x0660))          # fethatan .. hemze altı vb.
QURANIC_MARKS = set(range(0x06D6, 0x06EE))    # durak işaretleri, küçük harfler, ۝ ۞ ۩
DAGGER_ALIF = 0x0670                          # üstün elif (harf sayılıp sayılmayacağı tercihe bağlı)
TATWEEL = 0x0640
EXTRA_MARKS = {0x0610, 0x0611, 0x0612, 0x0613, 0x0614, 0x0615, 0x0616, 0x0617, 0x0618, 0x0619, 0x061A}

ARABIC_DIGITS = re.compile(r"[٠-٩۰-۹0-9]+")
VERSE_END = "۝"

# 28 temel harf + hemze ve varyantları
BASE_LETTERS = set(
    "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىي"
    "ٱ"  # elif-i vasl
)

# Varyantları temel harfe indirgeme (harf frekansı için isteğe bağlı)
FOLD_MAP = {
    "آ": "ا", "أ": "ا", "إ": "ا", "ٱ": "ا",
    "ؤ": "و", "ئ": "ي", "ى": "ي", "ة": "ه",
    "ی": "ي", "ک": "ك",
}

# Ebced (Doğu/Maşrikî sistemi)
ABJAD = {
    "ا": 1, "ب": 2, "ج": 3, "د": 4, "ه": 5, "و": 6, "ز": 7, "ح": 8, "ط": 9,
    "ي": 10, "ك": 20, "ل": 30, "م": 40, "ن": 50, "س": 60, "ع": 70, "ف": 80, "ص": 90,
    "ق": 100, "ر": 200, "ش": 300, "ت": 400, "ث": 500, "خ": 600, "ذ": 700, "ض": 800,
    "ظ": 900, "غ": 1000,
    # varyantların geleneksel değerleri
    "آ": 1, "أ": 1, "إ": 1, "ٱ": 1, "ء": 1, "ؤ": 6, "ئ": 10, "ى": 10, "ة": 5,
}


def strip_diacritics(text: str, keep_dagger_alif: bool = False) -> str:
    out = []
    for ch in unicodedata.normalize("NFC", text):
        cp = ord(ch)
        if cp == DAGGER_ALIF:
            if keep_dagger_alif:
                out.append("ا")
            continue
        if cp in HARAKAT or cp in QURANIC_MARKS or cp in EXTRA_MARKS or cp == TATWEEL:
            continue
        out.append(ch)
    return "".join(out)


def normalize(text: str, keep_dagger_alif: bool = False, fold: bool = False) -> str:
    t = strip_diacritics(text, keep_dagger_alif=keep_dagger_alif)
    t = ARABIC_DIGITS.sub(" ", t)
    t = re.sub(r"[^ء-يٱکی\s]", " ", t)
    if fold:
        t = "".join(FOLD_MAP.get(c, c) for c in t)
    return re.sub(r"\s+", " ", t).strip()


def words(text: str, **kw) -> list[str]:
    t = normalize(text, **kw)
    return t.split(" ") if t else []


def letters(text: str, **kw) -> list[str]:
    return [c for c in normalize(text, **kw) if not c.isspace()]


def letter_frequency(text: str, **kw) -> Counter:
    return Counter(letters(text, **kw))


def abjad_value(text: str, **kw) -> int:
    kw.setdefault("fold", False)
    return sum(ABJAD.get(c, 0) for c in letters(text, **kw))


def turkish_words(text: str) -> list[str]:
    """Meal metni için basit kelime ayrıştırıcı (Türkçe küçük harf kurallarıyla)."""
    t = text.replace("I", "ı").replace("İ", "i").lower()
    return re.findall(r"[a-zçğıöşüâîû]+", t)
