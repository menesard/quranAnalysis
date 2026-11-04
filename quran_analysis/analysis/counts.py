"""Temel sayımlar: sure, ayet, kelime, harf ve frekanslar."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from .. import arabic
from ..corpus import Corpus, Surah


@dataclass(frozen=True)
class TextOptions:
    """Sayım tercihleri. Her raporda bu ayarlar yazdırılmalıdır."""
    keep_dagger_alif: bool = False   # üstün elifi harf say
    fold: bool = False               # أ إ آ ٱ -> ا, ة -> ه gibi varyantları birleştir
    include_basmala: bool = False    # Fatiha dışındaki surelerin başındaki besmeleyi ekle

    def kw(self) -> dict:
        return {"keep_dagger_alif": self.keep_dagger_alif, "fold": self.fold}


BASMALA = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"


@dataclass
class SurahCounts:
    id: int
    name: str
    place: str | None
    revelation_order: int | None
    verses: int
    words: int
    letters: int
    abjad: int


def has_extra_basmala(s: Surah, opts: TextOptions) -> bool:
    """Fatiha (besmele 1. ayettir) ve Tevbe (besmelesiz) dışında besmele eklenir mi?"""
    return opts.include_basmala and s.id not in (1, 9)


def surah_texts(s: Surah, opts: TextOptions) -> list[str]:
    texts = [v.arabic for v in s.verses]
    if has_extra_basmala(s, opts):
        texts = [BASMALA] + texts
    return texts


def _located_texts(c: Corpus, opts: TextOptions):
    """(sure, ayet, metin) üçlüleri; eklenen besmele ayet numarası 0 ile gelir."""
    for s in c.surahs:
        if has_extra_basmala(s, opts):
            yield s.id, 0, BASMALA
        for v in s.verses:
            yield s.id, v.n, v.arabic


def surah_counts(s: Surah, opts: TextOptions = TextOptions()) -> SurahCounts:
    kw = opts.kw()
    texts = surah_texts(s, opts)
    return SurahCounts(
        id=s.id,
        name=s.name_tr,
        place=s.revelation_place,
        revelation_order=s.revelation_order,
        verses=len(s.verses),
        words=sum(len(arabic.words(t, **kw)) for t in texts),
        letters=sum(len(arabic.letters(t, **kw)) for t in texts),
        abjad=sum(arabic.abjad_value(t, keep_dagger_alif=opts.keep_dagger_alif) for t in texts),
    )


def all_surah_counts(c: Corpus, opts: TextOptions = TextOptions()) -> list[SurahCounts]:
    return [surah_counts(s, opts) for s in c.surahs]


def totals(c: Corpus, opts: TextOptions = TextOptions()) -> dict:
    rows = all_surah_counts(c, opts)
    pages = {v.page for v in c.verses() if v.page}
    return {
        "surahs": len(rows),
        "verses": sum(r.verses for r in rows),
        "words": sum(r.words for r in rows),
        "letters": sum(r.letters for r in rows),
        "abjad": sum(r.abjad for r in rows),
        "pages": len(pages) or None,
        "options": asdict(opts),
    }


def word_frequency(c: Corpus, opts: TextOptions = TextOptions()) -> Counter:
    kw = opts.kw()
    cnt: Counter = Counter()
    for _, _, text in _located_texts(c, opts):
        cnt.update(arabic.words(text, **kw))
    return cnt


def letter_frequency(c: Corpus, opts: TextOptions = TextOptions()) -> Counter:
    kw = opts.kw()
    cnt: Counter = Counter()
    for _, _, text in _located_texts(c, opts):
        cnt.update(arabic.letters(text, **kw))
    return cnt


def count_word(c: Corpus, word: str, opts: TextOptions = TextOptions(), substring: bool = False) -> dict:
    """Bir kelimenin (hareke yok sayılarak) geçiş sayısı ve geçtiği ayetler.

    ``--basmala`` açıksa sure başı besmelelerdeki geçişler ayet no 0 ile listelenir.
    """
    kw = opts.kw()
    target = arabic.normalize(word, **kw)
    if not target or " " in target:
        raise ValueError(f"Tek bir Arapça kelime girin: {word!r}")
    hits = []
    total = 0
    for sid, n_verse, text in _located_texts(c, opts):
        ws = arabic.words(text, **kw)
        n = sum(1 for w in ws if (target in w if substring else w == target))
        if n:
            total += n
            hits.append((sid, n_verse, n))
    return {"word": target, "total": total, "verses": hits, "options": asdict(opts)}


def count_translation_word(c: Corpus, word: str, prefix: bool = False) -> dict:
    """Meal (Türkçe) metninde kelime sayımı.

    Varsayılan birebir kelime eşleşmesidir. ``prefix=True`` ile kelimeyle
    *başlayan* tüm biçimler sayılır (rahmet -> rahmeti, rahmetinden ...);
    Türkçe eklemeli bir dil olduğu için çoğu zaman istenen budur.
    """
    parts = arabic.turkish_words(word)
    if len(parts) != 1:
        raise ValueError(f"Tek bir Türkçe kelime girin: {word!r}")
    target = parts[0]
    total = 0
    hits = []
    forms: Counter = Counter()
    for v in c.verses():
        ws = arabic.turkish_words(v.translation)
        matched = [w for w in ws if (w.startswith(target) if prefix else w == target)]
        if matched:
            forms.update(matched)
            total += len(matched)
            hits.append((v.surah, v.n, len(matched)))
    return {"word": target, "prefix": prefix, "total": total, "forms": dict(forms.most_common()),
            "verses": hits}
