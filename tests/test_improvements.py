"""Hata düzeltmeleri ve yeni özellikler için testler (ağ gerektirmez)."""

import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from quran_analysis import arabic, cli, config, morphology, reference, report
from quran_analysis.analysis import counts, numeric, stats
from quran_analysis.analysis.counts import TextOptions
from quran_analysis.client import ApiError, DiyanetClient, _unwrap
from quran_analysis.corpus import Corpus, Surah, Verse, _chapter_meta, _verse, build_corpus
from tests.fixtures import FakeClient


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _full_corpus() -> Corpus:
    """Referans ayet sayılarına uyan sahte tam corpus."""
    surahs = []
    for sid, n in enumerate(reference.VERSE_COUNTS, start=1):
        s = Surah(id=sid, name_tr=f"S{sid}", name_ar="", verse_count=n, revelation_order=sid)
        s.verses = [Verse(sid, i, "قُلْ هُوَ ٱللَّهُ", "De ki", page=1 + sid * 5 % 604) for i in range(1, n + 1)]
        surahs.append(s)
    return Corpus(surahs=surahs)


class ArabicFixes(unittest.TestCase):
    def test_invisible_and_unlisted_marks_do_not_split_words(self):
        self.assertEqual(arabic.words("كُفُو‌ًا"), ["كفوا"])
        self.assertEqual(arabic.words("أَحࣰَدٌ"), ["أحد"])

    def test_persian_letter_abjad(self):
        self.assertEqual(arabic.abjad_value("ک"), 20)


class CountsFixes(unittest.TestCase):
    def setUp(self):
        self.c = build_corpus(FakeClient())

    def test_frequencies_respect_basmala_option(self):
        o = TextOptions(include_basmala=True)
        self.assertEqual(sum(counts.word_frequency(self.c, o).values()), counts.totals(self.c, o)["words"])
        self.assertEqual(sum(counts.letter_frequency(self.c, o).values()), counts.totals(self.c, o)["letters"])

    def test_count_word_in_basmala_uses_verse_zero(self):
        res = counts.count_word(self.c, "ٱلرَّحِيمِ", TextOptions(include_basmala=True))
        self.assertEqual(res["total"], 2)
        self.assertTrue(all(v == 0 for _, v, _ in res["verses"]))

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            counts.count_word(self.c, "123")
        with self.assertRaises(ValueError):
            counts.count_translation_word(self.c, "  ")

    def test_meal_prefix(self):
        exact = counts.count_translation_word(self.c, "doğ")
        pref = counts.count_translation_word(self.c, "doğ", prefix=True)
        self.assertEqual(exact["total"], 0)
        self.assertEqual(pref["total"], 3)  # doğurmamış, doğurulmamıştır, doğrusu
        self.assertIn("doğrusu", pref["forms"])


class NumericFixes(unittest.TestCase):
    def test_binomial_tail(self):
        self.assertAlmostEqual(stats.binomial_tail(0, 10, 0.5), 1.0)
        self.assertAlmostEqual(stats.binomial_tail(10, 10, 0.5), 1 / 1024)
        self.assertEqual(stats.binomial_tail(11, 10, 0.5), 0.0)

    def test_divisibility_p_value_and_validation(self):
        c = build_corpus(FakeClient())
        rep = numeric.divisibility_report(c, 2)
        self.assertIn("p_value", rep["per_surah"]["verses"])
        self.assertIn("abjad", rep["per_surah"])
        with self.assertRaises(ValueError):
            numeric.divisibility_report(c, 0)


class CorpusFixes(unittest.TestCase):
    def test_validate_reports_missing(self):
        issues = build_corpus(FakeClient()).validate()
        self.assertTrue(any("Eksik sureler" in i for i in issues))

    def test_validate_full_corpus_ok(self):
        self.assertEqual(_full_corpus().validate(), [])

    def test_validate_detects_wrong_count(self):
        c = _full_corpus()
        c.surah(2).verses.pop()
        self.assertEqual(len(c.validate()), 1)

    def test_tolerant_field_names(self):
        s = _chapter_meta({"id": "5", "name": "Mâide", "verses_count": "120", "InisOrder": "112"})
        self.assertEqual((s.id, s.verse_count, s.revelation_order), (5, 120, 112))
        v = _verse({"verse_number": 3, "text_arabic": "قُلْ", "translation": "De ki", "page": "2"}, 5)
        self.assertEqual((v.surah, v.n, v.arabic, v.translation, v.page), (5, 3, "قُلْ", "De ki", 2))
        with self.assertRaises(ApiError):
            _verse({"text": "x"}, 1)

    def test_surah_lookup_error(self):
        with self.assertRaises(KeyError):
            build_corpus(FakeClient()).surah(1)


class ClientFixes(unittest.TestCase):
    def _client(self, **kw):
        return DiyanetClient("https://x.test", "secret", min_interval=0, backoff=0, **kw)

    def test_retry_on_503_then_success(self):
        calls = []

        def fake(req, timeout):
            calls.append(1)
            if len(calls) == 1:
                raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, io.BytesIO(b""))
            return _Resp(b'{"data": []}')

        with mock.patch("urllib.request.urlopen", fake):
            self.assertEqual(self._client().chapters(), [])
        self.assertEqual(len(calls), 2)

    def test_timeout_is_retried_then_reported(self):
        def fake(req, timeout):
            raise TimeoutError("timed out")

        with mock.patch("urllib.request.urlopen", fake), self.assertRaises(ApiError) as cm:
            self._client(retries=2).chapters()
        self.assertIn("2 deneme", str(cm.exception))

    def test_unauthorized_message(self):
        def fake(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b"bad token"))

        with mock.patch("urllib.request.urlopen", fake), self.assertRaises(ApiError) as cm:
            self._client().chapters()
        self.assertEqual(cm.exception.status, 401)
        self.assertIn("token", str(cm.exception))

    def test_non_json_response(self):
        with mock.patch("urllib.request.urlopen", lambda req, timeout: _Resp(b"<html>")):
            with self.assertRaises(ApiError):
                self._client().chapters()

    def test_unwrap_nested(self):
        self.assertEqual(_unwrap({"data": {"verses": [{"a": 1}]}}), [{"a": 1}])
        with self.assertRaises(ApiError):
            _unwrap({"error": "x"})


MORPH_SAMPLE = """# yorum satırı
LOCATION\tFORM\tTAG\tFEATURES
(1:1:1:1)\tbi\tP\tPREFIX|bi+
(1:1:1:2)\tsomi\tN\tSTEM|POS:N|LEM:{som|ROOT:smw|M|GEN
(1:1:2:1)\t{ll~ahi\tPN\tSTEM|POS:PN|LEM:{ll~ah|ROOT:Alh|GEN
(1:1:3:1)\t{l\tDET\tPREFIX|Al+
(1:1:3:2)\trr~aHoma`ni\tADJ\tSTEM|POS:ADJ|LEM:r~aHoma`n|ROOT:rHm|MS|GEN
(1:1:4:1)\t{l\tDET\tPREFIX|Al+
(1:1:4:2)\trr~aHiymi\tADJ\tSTEM|POS:ADJ|LEM:r~aHiym|ROOT:rHm|MS|GEN
(2:3:1:1)\t{l~a*iyna\tREL\tSTEM|POS:REL|LEM:{l~a*iY|MP
(2:3:2:1)\tyu&ominuwna\tV\tPREFIX|y|STEM|POS:V|IMPF|(IV)|LEM:'aAmana|ROOT:'mn|3MP
"""


class MorphologyTests(unittest.TestCase):
    def setUp(self):
        self.words = morphology.parse(MORPH_SAMPLE.splitlines())

    def test_parse_word_level(self):
        self.assertEqual(len(self.words), 6)
        self.assertEqual(self.words[0].root, "سمو")
        self.assertIsNone(self.words[4].root)

    def test_count_root_arabic_and_buckwalter(self):
        a = morphology.count_root(self.words, "رَحِمَ")
        b = morphology.count_root(self.words, "rHm")
        c = morphology.count_root(self.words, "ر ح م")
        self.assertEqual(a["total"], 2)
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.assertEqual(a["verses"], [(1, 1, 2)])
        self.assertEqual(len(a["lemmas"]), 2)

    def test_hamza_root_folding(self):
        self.assertEqual(morphology.count_root(self.words, "أمن")["total"], 1)

    def test_frequency_and_missing_file(self):
        self.assertEqual(morphology.root_frequency(self.words)["رحم"], 2)
        with self.assertRaises(FileNotFoundError):
            morphology.load("/yok/dosya.txt")


class ReportAndCliTests(unittest.TestCase):
    def test_report_html(self):
        page = report.build_report(_full_corpus())
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertIn("<svg", page)
        self.assertIn("6 236", page)

    def test_config_inline_comment(self):
        with tempfile.TemporaryDirectory() as d:
            env = Path(d) / ".env"
            env.write_text('A_TEST_X=abc # yorum\nA_TEST_Y="a # b"\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=False):
                config.load_dotenv(env)
                self.assertEqual(os.environ["A_TEST_X"], "abc")
                self.assertEqual(os.environ["A_TEST_Y"], "a # b")

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            _full_corpus().save(Path(d) / "quran.json")
            (Path(d) / "m.txt").write_text(MORPH_SAMPLE, encoding="utf-8")
            env = {"QURAN_DATA_DIR": d, "DIB_KURAN_API_TOKEN": ""}
            with mock.patch.dict(os.environ, env):
                def run(*args):
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                        code = cli.main(["--env", "/yok/.env", *args])
                    return code, buf.getvalue()

                self.assertEqual(json.loads(run("summary")[1])["verses"], 6236)
                self.assertEqual(run("validate")[0], 0)
                out = Path(d) / "r.html"
                self.assertEqual(run("report", "--out", str(out))[0], 0)
                self.assertTrue(out.is_file())
                code, txt = run("root", "rHm", "--morphology", str(Path(d) / "m.txt"))
                self.assertEqual(json.loads(txt)["total"], 2)
                self.assertEqual(run("fetch")[0], 2)  # token yok -> düzgün hata
                self.assertEqual(run("word", "123")[0], 2)


if __name__ == "__main__":
    unittest.main()
