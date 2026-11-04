"""Tek dosyalık HTML rapor: tablolar ve satır içi SVG grafikler (bağımlılıksız).

    python -m quran_analysis report --out reports/rapor.html

Grafikler üzerine gelindiğinde değerleri gösterir (SVG <title>), açık/koyu
temaya uyar ve her grafiğin altında aynı veriyi veren bir tablo bulunur.
"""

from __future__ import annotations

import html
import math
from dataclasses import asdict
from datetime import datetime, timezone

from . import __version__
from .analysis import counts, numeric, stats, structure
from .analysis.counts import TextOptions
from .corpus import Corpus

W, H = 760, 260
PAD_L, PAD_R, PAD_T, PAD_B = 48, 12, 12, 36

CSS = """
:root{--surface:#fcfcfb;--panel:#ffffff;--text:#0b0b0b;--text-2:#52514e;--muted:#8a8984;
--grid:#e6e5e0;--s1:#2a78d6;--s2:#eb6834;--line:#d9d8d2}
@media (prefers-color-scheme: dark){:root:where(:not([data-theme="light"])){--surface:#1a1a19;
--panel:#222220;--text:#f0efec;--text-2:#c3c2b7;--muted:#8f8e86;--grid:#33332f;--s1:#3987e5;
--s2:#d95926;--line:#3a3a36}}
:root[data-theme="dark"]{--surface:#1a1a19;--panel:#222220;--text:#f0efec;--text-2:#c3c2b7;
--muted:#8f8e86;--grid:#33332f;--s1:#3987e5;--s2:#d95926;--line:#3a3a36}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--text);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:40px 0 8px}
p.note,.meta{color:var(--text-2)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin:20px 0}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px}
.tile b{display:block;font-size:24px;font-variant-numeric:tabular-nums}
.tile span{color:var(--text-2);font-size:13px}
svg{width:100%;height:auto;display:block}
svg text{fill:var(--muted);font-size:11px}
svg .grid{stroke:var(--grid);stroke-width:1}
svg .s1{fill:var(--s1)}svg .s2{fill:var(--s2)}
svg .s1l{stroke:var(--s1);fill:none;stroke-width:2}
svg rect:hover,svg circle:hover{opacity:.75}
.legend{display:flex;gap:16px;color:var(--text-2);font-size:13px;margin:4px 0}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
details{margin:8px 0}summary{cursor:pointer;color:var(--text-2)}
.scroll{overflow-x:auto}
table{border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums;width:100%}
th,td{padding:4px 8px;border-bottom:1px solid var(--line);text-align:right}
th:first-child,td:first-child{text-align:left}
.ar{font-size:17px;direction:rtl}
"""


def _e(x) -> str:
    return html.escape(str(x))


def _fmt(x) -> str:
    if isinstance(x, float):
        return f"{x:,.3f}".replace(",", " ")
    if isinstance(x, int):
        return f"{x:,}".replace(",", " ")
    return _e(x)


def _nice_max(v: float) -> float:
    if v <= 0:
        return 1
    mag = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * mag:
            return m * mag
    return 10 * mag


def _axes(ymax: float, ticks: int = 4) -> str:
    out = []
    ih = H - PAD_T - PAD_B
    for i in range(ticks + 1):
        val = ymax * i / ticks
        y = PAD_T + ih - ih * i / ticks
        out.append(f'<line class="grid" x1="{PAD_L}" x2="{W - PAD_R}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text x="{PAD_L - 6}" y="{y + 4:.1f}" text-anchor="end">{_fmt(round(val))}</text>')
    return "".join(out)


def bar_chart(values: list[float], labels: list[str], classes: list[str] | None = None,
              tick_every: int = 1, title: str = "") -> str:
    """Dikey çubuk grafik. ``classes`` her çubuğun renk sınıfı (s1/s2)."""
    n = len(values)
    if not n:
        return ""
    ymax = _nice_max(max(values))
    iw, ih = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    step = iw / n
    gap = 2 if step > 4 else 0.5
    bw = max(step - gap, 0.5)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{_e(title)}">', _axes(ymax)]
    for i, (v, lab) in enumerate(zip(values, labels)):
        h = ih * v / ymax
        x = PAD_L + i * step + gap / 2
        y = PAD_T + ih - h
        cls = classes[i] if classes else "s1"
        r = min(4, bw / 2)
        parts.append(f'<rect class="{cls}" x="{x:.2f}" y="{y:.2f}" width="{bw:.2f}" height="{h:.2f}" '
                     f'rx="{r:.1f}"><title>{_e(lab)}: {_fmt(v)}</title></rect>')
        if i % tick_every == 0 or i == n - 1:
            parts.append(f'<text x="{x + bw / 2:.1f}" y="{H - PAD_B + 14}" text-anchor="middle">'
                         f'{_e(lab.split(" ")[0])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def loglog_chart(freqs: list[int], fit: dict, title: str = "") -> str:
    """Zipf grafiği: log(sıra) - log(frekans) noktaları ve uydurulan doğru."""
    if len(freqs) < 2:
        return ""
    xs = [math.log10(r) for r in range(1, len(freqs) + 1)]
    ys = [math.log10(f) for f in freqs]
    xmax, ymax = max(xs) or 1, max(ys) or 1
    iw, ih = W - PAD_L - PAD_R, H - PAD_T - PAD_B

    def px(x, y):
        return PAD_L + iw * x / xmax, PAD_T + ih - ih * y / ymax

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{_e(title)}">']
    for i in range(int(ymax) + 1):
        _, y = px(0, i)
        parts.append(f'<line class="grid" x1="{PAD_L}" x2="{W - PAD_R}" y1="{y:.1f}" y2="{y:.1f}"/>'
                     f'<text x="{PAD_L - 6}" y="{y + 4:.1f}" text-anchor="end">10^{i}</text>')
    for i in range(int(xmax) + 1):
        x, _ = px(i, 0)
        parts.append(f'<text x="{x:.1f}" y="{H - PAD_B + 14}" text-anchor="middle">10^{i}</text>')
    # Çok sayıda nokta olduğundan logaritmik aralıklarla örnekle
    shown, last = [], -1.0
    for i, (x, y) in enumerate(zip(xs, ys)):
        if x - last >= xmax / 300 or i < 20:
            shown.append((i + 1, x, y))
            last = x
    for rank, x, y in shown:
        cx, cy = px(x, y)
        parts.append(f'<circle class="s1" cx="{cx:.1f}" cy="{cy:.1f}" r="3">'
                     f'<title>sıra {rank}: {freqs[rank - 1]}</title></circle>')
    if "exponent" in fit and "intercept" in fit:
        slope, a = fit["exponent"], fit["intercept"] / math.log(10)
        x_end = min(xmax, a / slope) if slope > 0 else xmax
        x1, y1 = px(0, min(max(a, 0), ymax))
        x2, y2 = px(x_end, min(max(a - slope * x_end, 0), ymax))
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'style="stroke:var(--s2);stroke-width:2;stroke-dasharray:6 4"/>')
    parts.append("</svg>")
    return "".join(parts)


def _table(headers: list[str], rows: list[list], ar_cols: tuple[int, ...] = ()) -> str:
    th = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = []
    for r in rows:
        tds = "".join(
            f'<td class="ar">{_e(v)}</td>' if i in ar_cols else f"<td>{_fmt(v)}</td>"
            for i, v in enumerate(r)
        )
        body.append(f"<tr>{tds}</tr>")
    return f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _data_table(summary: str, headers, rows, ar_cols=()) -> str:
    return f"<details><summary>{_e(summary)}</summary>{_table(headers, rows, ar_cols)}</details>"


def build_report(c: Corpus, opts: TextOptions = TextOptions(), divisor: int = 19) -> str:
    rows = counts.all_surah_counts(c, opts)
    t = counts.totals(c, opts)
    wf = counts.word_frequency(c, opts)
    lf = counts.letter_frequency(c, opts)
    zipf = stats.zipf_fit(wf)
    div = numeric.divisibility_report(c, divisor, opts)
    mm = structure.meccan_medinan(c, opts)
    corr = structure.order_correlation(c, opts)
    issues = c.validate()

    out = [f"<!doctype html><html lang='tr'><head><meta charset='utf-8'>"
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Kur'an Analiz Raporu</title><style>{CSS}</style></head><body><main>"]
    out.append("<h1>Kur'an-ı Kerim sayım ve istatistik raporu</h1>")
    src = c.source or {}
    out.append(f"<p class='meta'>Kaynak: {_e(src.get('api', '?'))} · indirildi: {_e(src.get('fetched_at', '?'))}"
               f" · rapor: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · quran-analysis {__version__}</p>")
    opt_txt = ", ".join(f"{k}={v}" for k, v in asdict(opts).items())
    out.append(f"<p class='note'>Sayım tercihleri: <code>{_e(opt_txt)}</code>. Harekeler, durak işaretleri "
               "ve ayet numaraları çıkarılmıştır; kelimeler boşluklara göre ayrılır.</p>")
    if issues:
        items = "".join(f"<li>{_e(i)}</li>" for i in issues[:20])
        out.append(f"<p class='note'><b>Veri doğrulama uyarıları ({len(issues)}):</b></p><ul>{items}</ul>")

    out.append("<div class='tiles'>")
    for label, key in (("Sure", "surahs"), ("Ayet", "verses"), ("Kelime", "words"),
                       ("Harf", "letters"), ("Ebced", "abjad"), ("Sayfa", "pages")):
        out.append(f"<div class='tile'><b>{_fmt(t[key]) if t[key] is not None else '–'}</b><span>{label}</span></div>")
    out.append(f"<div class='tile'><b>{_fmt(len(wf))}</b><span>Farklı kelime</span></div></div>")

    # Sure uzunlukları
    labels = [f"{r.id} {r.name}" for r in rows]
    classes = ["s2" if r.place == "medeni" else "s1" for r in rows]
    legend = ("<div class='legend'><span><i style='background:var(--s1)'></i>Mekkî</span>"
              "<span><i style='background:var(--s2)'></i>Medenî</span></div>")
    out.append("<h2>Sure başına ayet sayısı</h2>" + legend)
    out.append(bar_chart([r.verses for r in rows], labels, classes, tick_every=10, title="Sure başına ayet sayısı"))
    out.append("<h2>Sure başına kelime sayısı</h2>" + legend)
    out.append(bar_chart([r.words for r in rows], labels, classes, tick_every=10, title="Sure başına kelime sayısı"))
    out.append(_data_table("Sure tablosu", ["No", "Sure", "Yer", "İniş", "Ayet", "Kelime", "Harf", "Ebced"],
                           [[r.id, r.name, r.place or "", r.revelation_order or "", r.verses, r.words,
                             r.letters, r.abjad] for r in rows]))

    # Harf frekansı
    lfs = lf.most_common()
    total_letters = sum(lf.values()) or 1
    out.append("<h2>Harf frekansı</h2>")
    out.append(f"<p class='note'>Harf entropisi: {stats.shannon_entropy(lf):.3f} bit.</p>")
    out.append(bar_chart([n for _, n in lfs], [ch for ch, _ in lfs], title="Harf frekansı"))
    out.append(_data_table("Harf tablosu", ["Harf", "Sayı", "%"],
                           [[ch, n, round(100 * n / total_letters, 2)] for ch, n in lfs], ar_cols=(0,)))

    # Zipf
    out.append("<h2>Kelime frekansı ve Zipf yasası</h2>")
    out.append(f"<p class='note'>Log-log eğim (Zipf üssü) s = {zipf.get('exponent')}, R² = {zipf.get('r_squared')}. "
               "Doğal dillerde s ≈ 1 beklenir. Kesikli çizgi uydurulan doğrudur.</p>")
    out.append(loglog_chart([n for _, n in wf.most_common()], zipf, title="Zipf grafiği"))
    out.append(_data_table("En sık 50 kelime", ["Kelime", "Sayı"],
                           [[w, n] for w, n in wf.most_common(50)], ar_cols=(0,)))

    # Mekkî / Medenî
    out.append("<h2>Mekkî ve Medenî sureler</h2>")
    mm_rows = [[place, d["surahs"], d["words_per_verse"].get("n"), d["words_per_verse"].get("mean"),
                d["words_per_verse"].get("median")] for place, d in mm.items()]
    out.append(_table(["Grup", "Sure", "Ayet", "Ort. kelime/ayet", "Medyan"], mm_rows))
    out.append("<p class='note'>Korelasyonlar (Pearson / Spearman): mushaf sırası–iniş sırası "
               f"{corr['mushaf_vs_revelation']}; mushaf sırası–ayet sayısı {corr['mushaf_vs_verse_count']} / "
               f"{corr['mushaf_vs_verse_count_spearman']}; iniş sırası–ayet sayısı "
               f"{corr['revelation_vs_verse_count']} / {corr['revelation_vs_verse_count_spearman']}.</p>")

    # Bölünebilirlik
    out.append(f"<h2>{divisor} ile bölünebilirlik</h2>")
    out.append(_table(["Toplam", "Değer", "Kalan", "Bölünür mü"],
                      [[k, v["value"], v["remainder"], "evet" if v["divisible"] else "hayır"]
                       for k, v in div["totals"].items()]))
    out.append("<p class='note'>Sure bazında: bölünebilen sure sayısı, tesadüf beklentisi ve tek yönlü binom "
               "p-değeri. p küçükse (ör. &lt; 0,05) sonuç tesadüfle açıklanması zor bir sapmadır; çok sayıda "
               "test yapıldığında bazılarının tesadüfen küçük çıkacağını unutmayın.</p>")
    out.append(_table(["Ölçü", "Bölünebilen", "Beklenen", "p"],
                      [[k, v["divisible_count"], v["expected_by_chance"], v["p_value"]]
                       for k, v in div["per_surah"].items()]))
    out.append("</main></body></html>")
    return "".join(out)
