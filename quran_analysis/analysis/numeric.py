"""Sayısal örüntü testleri (ör. 19'a bölünebilirlik, asal sayılar, tek/çift).

Bu fonksiyonlar iddiaları *doğrulamak veya yanlışlamak* için tasarlanmıştır.
Bir örüntünün anlamlı olup olmadığını değerlendirmek için `stats.permutation_baseline`
ile rastgele beklentiyle karşılaştırın.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from ..corpus import Corpus
from .counts import TextOptions, all_surah_counts, totals


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def divisibility_report(c: Corpus, divisor: int = 19, opts: TextOptions = TextOptions()) -> dict:
    """Toplamlar ve sure bazında sayımların verilen sayıya bölünebilirliği."""
    t = totals(c, opts)
    total_checks = {
        k: {"value": t[k], "divisible": t[k] % divisor == 0, "remainder": t[k] % divisor}
        for k in ("surahs", "verses", "words", "letters", "abjad")
        if isinstance(t[k], int)
    }
    rows = all_surah_counts(c, opts)
    per_field = {}
    for f in ("verses", "words", "letters"):
        divisible = [r.id for r in rows if getattr(r, f) % divisor == 0]
        per_field[f] = {
            "divisible_count": len(divisible),
            "expected_by_chance": round(len(rows) / divisor, 2),
            "surahs": divisible,
        }
    return {"divisor": divisor, "totals": total_checks, "per_surah": per_field, "options": asdict(opts)}


def prime_report(values: Iterable[int]) -> dict:
    vals = list(values)
    primes = [v for v in vals if is_prime(v)]
    return {"n": len(vals), "prime_count": len(primes), "primes": primes}


def parity_report(c: Corpus) -> dict:
    """Sure numarası ile ayet sayısının tek/çift uyumu (sık iddia edilen bir örüntü)."""
    same = []
    for s in c.surahs:
        if (s.id % 2) == (len(s.verses) % 2):
            same.append(s.id)
    return {
        "same_parity": len(same),
        "different_parity": len(c.surahs) - len(same),
        "sum_id_plus_verses": sum(s.id + len(s.verses) for s in c.surahs),
    }
