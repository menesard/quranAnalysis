# Kur'an-ı Kerim Matematiksel ve Yapısal Analiz

Diyanet İşleri Başkanlığı'nın **Açık Kaynak Kur'an API**'sinden alınan veriyle
Kur'an-ı Kerim üzerinde sayım (sure, ayet, kelime, harf), sayısal örüntü
(19'a bölünebilirlik, asal sayılar, tek/çift, ebced) ve yapısal/istatistiksel
(mushaf sayfaları, cüzler, iniş sırası, Mekkî/Medenî, Zipf yasası, entropi)
analizler yapan bir Python projesi.

Harici bağımlılığı yoktur; yalnızca Python 3.10+ standart kütüphanesini kullanır.

## Kurulum

```bash
git clone https://github.com/menesard/quranAnalysis
cd quranAnalysis
cp .env.example .env      # sonra .env içine kendi token'ınızı yazın
```

`.env` dosyası `.gitignore` içindedir ve **asla commit edilmez**. Token almak için:
<https://acikkaynakkuran-dev.diyanet.gov.tr>

| Değişken | Açıklama | Varsayılan |
|---|---|---|
| `DIB_KURAN_API_TOKEN` | Diyanet API token'ı (zorunlu) | – |
| `DIB_KURAN_API_BASE_URL` | API kök adresi | `https://api.diyanet.gov.tr` |
| `DIB_KURAN_LANGUAGE` | Meal dili parametresi | `tr` |
| `QURAN_DATA_DIR` | Veri ve önbellek klasörü | `data` |

## Kullanım

```bash
python -m quran_analysis fetch                  # 114 sureyi indir -> data/quran.json
python -m quran_analysis summary                # toplam sure/ayet/kelime/harf/ebced
python -m quran_analysis surahs --csv sureler.csv
python -m quran_analysis word الله              # Arapça kelime sayımı (hareke yok sayılır)
python -m quran_analysis word الله --fold       # elif/hemze varyantlarını birleştirerek
python -m quran_analysis meal-word rahmet       # Türkçe meal metninde kelime sayımı
python -m quran_analysis divisible --by 19      # bölünebilirlik raporu
python -m quran_analysis stats                  # istatistik + yapı analizleri
```

İlk `fetch` her API yanıtını `data/cache/` altına kaydeder; sonraki çalıştırmalar
API'ye gitmez. Analizler yalnızca `data/quran.json` dosyasıyla çalışır.

### Sayım tercihleri

Kelime ve harf sayıları, metnin nasıl ele alındığına göre **değişir**. Bu yüzden
her tercih bir bayraktır ve rapor çıktısında `options` olarak yazdırılır:

- `--dagger-alif`: Üstün elifi (ٰ, ör. ٱلرَّحْمَٰنِ) ayrı harf olarak say.
- `--fold`: أ إ آ ٱ → ا, ة → ه, ى/ئ → ي gibi varyantları tek harfe indir.
- `--basmala`: Fatiha ve Tevbe dışındaki surelerin başındaki besmeleyi say.

Harekeler, Kur'an durak işaretleri ve ayet numaraları her zaman çıkarılır.
Kelimeler boşluklara göre ayrılır (ör. وَلَمْ tek kelime sayılır).

## Proje yapısı

```
quran_analysis/
  config.py          .env / ortam değişkenleri
  client.py          Diyanet API istemcisi (Bearer token, tekrar deneme, hız sınırı)
  cache.py           dosya tabanlı JSON önbellek
  corpus.py          API verisini kararlı bir şemaya dönüştürme ve kaydetme
  arabic.py          hareke temizleme, kelime/harf ayrıştırma, ebced
  analysis/
    counts.py        sure/ayet/kelime/harf sayımları, frekanslar, kelime arama
    numeric.py       bölünebilirlik, asal sayı, tek/çift testleri
    stats.py         betimsel istatistik, entropi, Zipf, permütasyon taban çizgisi
    structure.py     sayfa, cüz, iniş sırası, Mekkî/Medenî karşılaştırması
  cli.py             komut satırı arayüzü
tests/               ağ gerektirmeyen testler
```

## API

Uç noktalar Diyanet'in kendi açık kaynak istemcisinden
([diyanet-bid/Kuran](https://github.com/diyanet-bid/Kuran)) alınmıştır:

| Uç nokta | Açıklama |
|---|---|
| `GET /api/v1/chapters` | Sure listesi (`SureId`, `SureNameTurkish`, `SureNameArabic`, `AyetCount`, `InisOrder`, `Cuz`, `FirstPage`, `BesmeleVisible`) |
| `GET /api/v1/chapters/{id}` | Surenin ayetleri (`verse_id_in_surah`, `page_number`, `arabic_script.text`, `translation.text`) |
| `GET /api/v1/verses/page/{n}` | Mushaf sayfasındaki ayetler |

Kimlik doğrulama: `Authorization: Bearer <token>`.

## Yöntem notu

Kur'an'daki sayısal örüntü iddialarının çoğu, belirli bir imla ve sayma kuralı
seçimine bağlıdır. Bu proje iddiaları **tekrarlanabilir şekilde test etmek**
için tasarlandı: her sayım tercihi açıkça belirtilir ve `stats.permutation_baseline`
ile bir örüntünün tesadüfen ne sıklıkla ortaya çıkacağı tahmin edilebilir.

## Test

```bash
python -m unittest discover -s tests -t .
```
