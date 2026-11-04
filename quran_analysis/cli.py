"""Komut satırı arayüzü.

    python -m quran_analysis fetch                 # API'den tüm Kur'an'ı indir ve kaydet
    python -m quran_analysis summary               # genel sayımlar
    python -m quran_analysis surahs --csv out.csv  # sure bazında tablo
    python -m quran_analysis word الله             # kelime sayımı
    python -m quran_analysis meal-word rahmet      # meal metninde kelime sayımı
    python -m quran_analysis divisible --by 19     # bölünebilirlik testi
    python -m quran_analysis stats                 # istatistik ve yapı analizleri
    python -m quran_analysis validate              # veriyi referans sayılarla doğrula
    python -m quran_analysis report                # HTML rapor (grafikli)
    python -m quran_analysis root رحم              # kök bazlı sayım (morfoloji dosyası gerekir)
    python -m quran_analysis roots --top 30        # en sık kökler
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import morphology, report
from .analysis import counts, numeric, stats, structure
from .analysis.counts import TextOptions
from .cache import JsonCache
from .client import ApiError, DiyanetClient
from .config import get_settings
from .corpus import Corpus, build_corpus


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _opts(a) -> TextOptions:
    return TextOptions(keep_dagger_alif=a.dagger_alif, fold=a.fold, include_basmala=a.basmala)


def _load(settings) -> Corpus:
    if not settings.corpus_path.is_file():
        sys.exit(f"{settings.corpus_path} bulunamadı. Önce: python -m quran_analysis fetch")
    return Corpus.load(settings.corpus_path)


def cmd_fetch(a, settings) -> int:
    if not settings.token:
        print("API token eksik. .env dosyasına DIB_KURAN_API_TOKEN değerini girin "
              "(bkz. .env.example).", file=sys.stderr)
        return 2
    client = DiyanetClient(
        settings.base_url,
        settings.token or "",
        cache=None if a.no_cache else JsonCache(settings.cache_dir),
        language=settings.language,
    )
    try:
        corpus = build_corpus(client, progress=lambda m: print(m, file=sys.stderr))
    except ApiError as e:
        print(f"API hatası: {e}", file=sys.stderr)
        return 1
    corpus.save(settings.corpus_path)
    t = counts.totals(corpus)
    print(f"Kaydedildi: {settings.corpus_path} ({t['surahs']} sure, {t['verses']} ayet)")
    issues = corpus.validate()
    for i in issues:
        print(f"UYARI: {i}", file=sys.stderr)
    return 0


def cmd_validate(a, settings) -> int:
    issues = _load(settings).validate()
    if not issues:
        print("Veri tutarlı: 114 sure, 6236 ayet, sure bazında ayet sayıları referansla aynı.")
        return 0
    for i in issues:
        print(i)
    return 1


def cmd_report(a, settings) -> int:
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.build_report(_load(settings), _opts(a), divisor=a.by), encoding="utf-8")
    print(f"Yazıldı: {out}")
    return 0


def _morph(a, settings):
    return morphology.load(a.morphology or settings.morphology_path)


def cmd_root(a, settings) -> int:
    res = morphology.count_root(_morph(a, settings), a.root)
    if not a.verbose:
        res["verses"] = len(res["verses"])
        res.pop("by_surah")
    _print(res)
    return 0


def cmd_roots(a, settings) -> int:
    words = _morph(a, settings)
    rf = morphology.root_frequency(words)
    _print({
        "words_with_root": sum(rf.values()),
        "unique_roots": len(rf),
        "top_roots": [(" ".join(r), n) for r, n in rf.most_common(a.top)],
    })
    return 0


def cmd_summary(a, settings) -> int:
    _print(counts.totals(_load(settings), _opts(a)))
    return 0


def cmd_surahs(a, settings) -> int:
    rows = [asdict(r) for r in counts.all_surah_counts(_load(settings), _opts(a))]
    if not rows:
        print("Veride sure yok.", file=sys.stderr)
        return 1
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"Yazıldı: {a.csv}")
    else:
        for r in rows:
            print(f"{r['id']:3d} {r['name']:<14} {r['place'] or '':<7} ayet={r['verses']:<4} "
                  f"kelime={r['words']:<5} harf={r['letters']:<6} ebced={r['abjad']}")
    return 0


def cmd_word(a, settings) -> int:
    res = counts.count_word(_load(settings), a.word, _opts(a), substring=a.substring)
    if not a.verbose:
        res["verses"] = len(res["verses"])
    _print(res)
    return 0


def cmd_meal_word(a, settings) -> int:
    res = counts.count_translation_word(_load(settings), a.word, prefix=a.prefix)
    if not a.verbose:
        res["verses"] = len(res["verses"])
    _print(res)
    return 0


def cmd_divisible(a, settings) -> int:
    _print(numeric.divisibility_report(_load(settings), a.by, _opts(a)))
    return 0


def cmd_stats(a, settings) -> int:
    c = _load(settings)
    o = _opts(a)
    rows = counts.all_surah_counts(c, o)
    wf = counts.word_frequency(c, o)
    lf = counts.letter_frequency(c, o)
    _print({
        "verses_per_surah": stats.describe([r.verses for r in rows]),
        "words_per_surah": stats.describe([r.words for r in rows]),
        "unique_words": len(wf),
        "top_words": wf.most_common(20),
        "letter_frequency": lf.most_common(),
        "letter_entropy_bits": round(stats.shannon_entropy(lf), 4),
        "word_entropy_bits": round(stats.shannon_entropy(wf), 4),
        "zipf": stats.zipf_fit(wf),
        "parity": numeric.parity_report(c),
        "structure": {
            "pages": structure.page_distribution(c),
            "juz": structure.juz_distribution(c),
            "order_correlation": structure.order_correlation(c, o),
            "meccan_medinan": structure.meccan_medinan(c, o),
        },
        "options": asdict(o),
    })
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quran-analysis", description="Kur'an-ı Kerim sayım ve analiz aracı")
    p.add_argument("--env", default=".env", help=".env dosya yolu")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dagger-alif", action="store_true", help="Üstün elifi (ٰ) harf olarak say")
    common.add_argument("--fold", action="store_true", help="Elif/hemze varyantlarını birleştir")
    common.add_argument("--basmala", action="store_true", help="Sure başı besmeleleri sayıma kat")

    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="API'den veriyi indir")
    f.add_argument("--no-cache", action="store_true")
    f.set_defaults(func=cmd_fetch)

    sub.add_parser("summary", parents=[common], help="Genel toplamlar").set_defaults(func=cmd_summary)

    s = sub.add_parser("surahs", parents=[common], help="Sure bazında sayımlar")
    s.add_argument("--csv")
    s.set_defaults(func=cmd_surahs)

    w = sub.add_parser("word", parents=[common], help="Arapça kelime sayımı")
    w.add_argument("word")
    w.add_argument("--substring", action="store_true", help="Kelime içinde geçişleri de say")
    w.add_argument("-v", "--verbose", action="store_true", help="Ayet listesini göster")
    w.set_defaults(func=cmd_word)

    m = sub.add_parser("meal-word", help="Türkçe meal metninde kelime sayımı")
    m.add_argument("word")
    m.add_argument("--prefix", action="store_true",
                   help="Kelimeyle başlayan tüm biçimleri say (rahmet -> rahmeti, rahmetinden)")
    m.add_argument("-v", "--verbose", action="store_true")
    m.set_defaults(func=cmd_meal_word)

    d = sub.add_parser("divisible", parents=[common], help="Bölünebilirlik testi")
    d.add_argument("--by", type=int, default=19)
    d.set_defaults(func=cmd_divisible)

    sub.add_parser("stats", parents=[common], help="İstatistik ve yapı analizleri").set_defaults(func=cmd_stats)

    sub.add_parser("validate", help="Veriyi referans ayet sayılarıyla doğrula").set_defaults(func=cmd_validate)

    r = sub.add_parser("report", parents=[common], help="Grafikli HTML rapor üret")
    r.add_argument("--out", default="reports/rapor.html")
    r.add_argument("--by", type=int, default=19, help="Bölünebilirlik testi için bölen")
    r.set_defaults(func=cmd_report)

    morph = argparse.ArgumentParser(add_help=False)
    morph.add_argument("--morphology", help="quranic-corpus-morphology-0.4.txt yolu")
    k = sub.add_parser("root", parents=[morph], help="Kök bazlı sayım (ör. رحم veya rHm)")
    k.add_argument("root")
    k.add_argument("-v", "--verbose", action="store_true", help="Sure ve ayet dağılımını göster")
    k.set_defaults(func=cmd_root)
    ks = sub.add_parser("roots", parents=[morph], help="En sık kökler")
    ks.add_argument("--top", type=int, default=30)
    ks.set_defaults(func=cmd_roots)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    settings = get_settings(a.env)
    try:
        return a.func(a, settings) or 0
    except (ValueError, FileNotFoundError, KeyError) as e:
        print(f"Hata: {e}", file=sys.stderr)
        return 2
