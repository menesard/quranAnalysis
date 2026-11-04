"""Fiziksel/yapısal analizler: mushaf sayfaları, cüzler, iniş sırası, Mekkî/Medenî."""

from __future__ import annotations

from collections import Counter, defaultdict

from .. import arabic
from ..corpus import Corpus
from .counts import TextOptions
from .stats import describe, pearson, spearman


def page_distribution(c: Corpus) -> dict:
    per_page = Counter(v.page for v in c.verses() if v.page)
    if not per_page:
        return {"pages": 0}
    return {"pages": len(per_page), "verses_per_page": describe(list(per_page.values()))}


def juz_distribution(c: Corpus) -> dict:
    by_juz: dict[int, list[int]] = defaultdict(list)
    for s in c.surahs:
        if s.juz:
            by_juz[int(s.juz)].append(s.id)
    return {"juz_count": len(by_juz), "surahs_starting_in_juz": dict(sorted(by_juz.items()))}


def order_correlation(c: Corpus, opts: TextOptions = TextOptions()) -> dict:
    """Mushaf sırası ile iniş sırası ve sure uzunluğu arasındaki ilişki."""
    rows = [s for s in c.surahs if s.revelation_order]
    mushaf = [s.id for s in rows]
    nuzul = [int(s.revelation_order) for s in rows]
    lengths = [len(s.verses) for s in rows]
    all_ids = [s.id for s in c.surahs]
    all_len = [len(s.verses) for s in c.surahs]
    return {
        "n": len(rows),
        "mushaf_vs_revelation": pearson(mushaf, nuzul),
        "mushaf_vs_verse_count": pearson(all_ids, all_len),
        "mushaf_vs_verse_count_spearman": spearman(all_ids, all_len),
        "revelation_vs_verse_count": pearson(nuzul, lengths),
        "revelation_vs_verse_count_spearman": spearman(nuzul, lengths),
    }


def meccan_medinan(c: Corpus, opts: TextOptions = TextOptions()) -> dict:
    """Mekkî ve Medenî surelerde ayet uzunluğu (kelime) karşılaştırması."""
    kw = opts.kw()
    groups: dict[str, list[int]] = defaultdict(list)
    surah_counts: Counter = Counter()
    for s in c.surahs:
        place = s.revelation_place or "bilinmiyor"
        surah_counts[place] += 1
        groups[place].extend(len(arabic.words(v.arabic, **kw)) for v in s.verses)
    return {
        place: {"surahs": surah_counts[place], "words_per_verse": describe(vals)}
        for place, vals in groups.items()
    }
