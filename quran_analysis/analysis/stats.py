"""İstatistiksel analizler: dağılımlar, entropi, Zipf yasası, rastgele taban çizgisi."""

from __future__ import annotations

import math
import random
import statistics
from collections import Counter
from typing import Callable, Sequence


def describe(values: Sequence[float]) -> dict:
    vals = list(values)
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "min": min(vals),
        "max": max(vals),
        "mean": round(statistics.fmean(vals), 3),
        "median": statistics.median(vals),
        "stdev": round(statistics.pstdev(vals), 3),
    }


def shannon_entropy(freq: Counter) -> float:
    """Bit cinsinden Shannon entropisi."""
    total = sum(freq.values())
    if not total:
        return 0.0
    return -sum((n / total) * math.log2(n / total) for n in freq.values() if n)


def zipf_fit(freq: Counter, top: int | None = None) -> dict:
    """log(frekans) = a - s*log(sıra) doğrusal regresyonu. Doğal dillerde s ≈ 1."""
    counts = sorted(freq.values(), reverse=True)
    if top:
        counts = counts[:top]
    if len(counts) < 2:
        return {"n": len(counts)}
    xs = [math.log(r) for r in range(1, len(counts) + 1)]
    ys = [math.log(c) for c in counts]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    return {
        "n": len(counts),
        "exponent": round(-slope, 4),
        "intercept": round(intercept, 4),  # doğal logaritma cinsinden
        "r_squared": round(1 - ss_res / ss_tot, 4) if ss_tot else None,
    }


def binomial_tail(k: int, n: int, p: float) -> float:
    """P(X >= k), X ~ Binom(n, p). Örüntünün tesadüfen bu kadar sık görülme olasılığı."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return min(1.0, sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Sıra korelasyonu (doğrusal olmayan ama tekdüze ilişkiler için)."""
    if len(xs) < 2:
        return None
    try:
        return round(statistics.correlation(xs, ys, method="ranked"), 4)
    except (statistics.StatisticsError, TypeError):
        return None


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) < 2:
        return None
    try:
        return round(statistics.correlation(xs, ys), 4)
    except statistics.StatisticsError:
        return None


def permutation_baseline(
    values: Sequence[int],
    statistic: Callable[[Sequence[int]], float],
    trials: int = 10_000,
    seed: int = 19,
    jitter: Callable[[int, random.Random], int] | None = None,
) -> dict:
    """Gözlenen istatistiği, verinin rastgele bozulmuş sürümleriyle karşılaştırır.

    Varsayılan olarak her değeri ±%5 aralığında rastgele değiştirir; böylece ör.
    "19'a bölünebilen sure sayısı" gibi bir örüntünün tesadüfen ne sıklıkla
    ortaya çıkacağı tahmin edilir. p-değeri = rastgele >= gözlenen oranı.
    """
    rng = random.Random(seed)
    jitter = jitter or (lambda v, r: max(1, v + r.randint(-max(1, v // 20), max(1, v // 20))))
    observed = statistic(values)
    ge = 0
    for _ in range(trials):
        sample = [jitter(v, rng) for v in values]
        if statistic(sample) >= observed:
            ge += 1
    return {"observed": observed, "trials": trials, "p_value": (ge + 1) / (trials + 1)}
