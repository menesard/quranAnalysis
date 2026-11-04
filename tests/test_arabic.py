import unittest

from quran_analysis import arabic


class ArabicTests(unittest.TestCase):
    def test_strip_diacritics_and_verse_numbers(self):
        self.assertEqual(arabic.normalize("قُلْ هُوَ ٱللَّهُ أَحَدٌ ١"), "قل هو ٱلله أحد")

    def test_words(self):
        self.assertEqual(len(arabic.words("وَلَمْ يَكُن لَّهُۥ كُفُوًا أَحَدٌۢ ٤")), 5)

    def test_letters(self):
        self.assertEqual(len(arabic.letters("قُلْ هُوَ ٱللَّهُ أَحَدٌ")), 11)

    def test_dagger_alif_option(self):
        t = "ٱلرَّحْمَٰنِ"
        self.assertEqual(len(arabic.letters(t)), 6)
        self.assertEqual(len(arabic.letters(t, keep_dagger_alif=True)), 7)

    def test_fold(self):
        self.assertEqual(arabic.normalize("أَحَدٌ ٱللَّهُ", fold=True), "احد الله")

    def test_abjad(self):
        self.assertEqual(arabic.abjad_value("قُلْ"), 130)
        self.assertEqual(arabic.abjad_value("الله"), 66)

    def test_turkish_words(self):
        self.assertEqual(arabic.turkish_words("İnsan RAHMET"), ["insan", "rahmet"])


if __name__ == "__main__":
    unittest.main()
