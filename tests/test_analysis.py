import tempfile
import unittest
from pathlib import Path

from quran_analysis.analysis import counts, numeric, stats, structure
from quran_analysis.analysis.counts import TextOptions
from quran_analysis.corpus import Corpus, build_corpus
from tests.fixtures import FakeClient


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.c = build_corpus(FakeClient())

    def test_corpus_dedup_and_order(self):
        self.assertEqual([s.id for s in self.c.surahs], [108, 112])
        self.assertEqual(len(self.c.surah(112).verses), 4)

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "q.json"
            self.c.save(p)
            c2 = Corpus.load(p)
        self.assertEqual(counts.totals(c2), counts.totals(self.c))

    def test_ikhlas_word_count(self):
        self.assertEqual(counts.surah_counts(self.c.surah(112)).words, 15)

    def test_kawthar_word_count(self):
        self.assertEqual(counts.surah_counts(self.c.surah(108)).words, 10)

    def test_basmala_option(self):
        r = counts.surah_counts(self.c.surah(112), TextOptions(include_basmala=True))
        self.assertEqual(r.words, 19)

    def test_count_word(self):
        res = counts.count_word(self.c, "ٱللَّهُ")
        self.assertEqual(res["total"], 2)
        self.assertEqual(counts.count_word(self.c, "احد", TextOptions(fold=True))["total"], 2)

    def test_meal_word(self):
        self.assertEqual(counts.count_translation_word(self.c, "Allah")["total"], 2)

    def test_divisibility(self):
        rep = numeric.divisibility_report(self.c, 7)
        self.assertEqual(rep["totals"]["verses"]["value"], 7)
        self.assertTrue(rep["totals"]["verses"]["divisible"])

    def test_primes(self):
        self.assertEqual(numeric.prime_report([1, 2, 19, 21])["primes"], [2, 19])

    def test_stats(self):
        wf = counts.word_frequency(self.c)
        self.assertGreater(stats.shannon_entropy(wf), 0)
        self.assertIn("exponent", stats.zipf_fit(wf))
        pb = stats.permutation_baseline([7, 19, 38], lambda v: sum(x % 19 == 0 for x in v), trials=200)
        self.assertTrue(0 < pb["p_value"] <= 1)

    def test_structure(self):
        self.assertEqual(structure.page_distribution(self.c)["pages"], 2)
        self.assertIn("mekki", structure.meccan_medinan(self.c))


if __name__ == "__main__":
    unittest.main()
