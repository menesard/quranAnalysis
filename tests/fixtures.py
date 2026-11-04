"""Ağ gerektirmeyen test verisi: API yanıt biçimini taklit eder."""

CHAPTERS = {
    "data": [
        {"SureId": 112, "SureNameTurkish": "İhlâs", "SureNameArabic": "الإخلاص", "BesmeleVisible": True,
         "InisOrder": 22, "AyetCount": 4, "Cuz": 30, "FirstPage": 604, "MealInfo": "", "HeaderOnBackPage": False},
        {"SureId": 108, "SureNameTurkish": "Kevser", "SureNameArabic": "الكوثر", "BesmeleVisible": True,
         "InisOrder": 15, "AyetCount": 3, "Cuz": 30, "FirstPage": 602, "MealInfo": "", "HeaderOnBackPage": False},
    ],
    "meta": {"requested_language": "tr"},
}


def _v(sid, n, ar, tr, page):
    return {"page_number": page, "surah_id": sid, "verse_id_in_surah": n,
            "translation": {"text": tr}, "arabic_script": {"text_font_id": 1, "text": ar}}


VERSES = {
    112: {"data": [
        _v(112, 1, "قُلْ هُوَ ٱللَّهُ أَحَدٌ ١", "De ki: O, Allah birdir.", 604),
        _v(112, 2, "ٱللَّهُ ٱلصَّمَدُ ٢", "Allah Samed'dir.", 604),
        _v(112, 2, "ٱللَّهُ ٱلصَّمَدُ ٢", "Allah Samed'dir.", 604),  # API'deki tekrar
        _v(112, 3, "لَمْ يَلِدْ وَلَمْ يُولَدْ ٣", "O doğurmamış ve doğurulmamıştır.", 604),
        _v(112, 4, "وَلَمْ يَكُن لَّهُۥ كُفُوًا أَحَدٌۢ ٤", "Hiçbir şey O'na denk değildir.", 604),
    ]},
    108: {"data": [
        _v(108, 1, "إِنَّآ أَعْطَيْنَٰكَ ٱلْكَوْثَرَ ١", "Şüphesiz biz sana Kevser'i verdik.", 602),
        _v(108, 2, "فَصَلِّ لِرَبِّكَ وَٱنْحَرْ ٢", "Öyleyse Rabbin için namaz kıl ve kurban kes.", 602),
        _v(108, 3, "إِنَّ شَانِئَكَ هُوَ ٱلْأَبْتَرُ ٣", "Doğrusu sana buğzeden, soyu kesik olanın ta kendisidir.", 602),
    ]},
}


class FakeClient:
    base_url = "https://example.test"
    language = "tr"

    def chapters(self):
        return CHAPTERS["data"]

    def chapter_verses(self, sid):
        return VERSES[sid]["data"]
