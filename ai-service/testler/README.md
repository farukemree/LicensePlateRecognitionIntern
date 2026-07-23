# Regresyon Testleri

Bu testler **sahadan gelen gerçek hata vakalarını** içerir. Her vaka, sistemin
canlıda gerçekten yanlış yaptığı ve düzeltildikten sonra bir daha yanlış
yapmaması gereken bir durumu temsil eder.

`main.py` içinde eşik/ceza değerlerine dokunmadan önce ve sonra çalıştır.

```bash
cd ai-service
python3 testler/test_gramer.py
python3 testler/test_oylama.py
python3 testler/test_ciftkayit.py
```

Model yüklemeye gerek yok — testler `main.py`'den yalnızca ilgili
fonksiyonları çıkarıp çalıştırır, saniyeler sürer.

## Testler ne koruyor

**test_gramer.py** — Türk plaka dilbilgisi çözümleyicisi.
- `B4CLY063` → `34CLY063` (il kodu geçerliliği belirsizliği çözer: `84` diye
  bir il yok, `34` var)
- `85BPJ875` → `35BPJ875` — *sahada 2026-07-23'te yanlış okundu.* Tek hatalı
  yorum (il kodunda bir rakam düzeltmesi), iki hatalı yorumu (karakter at +
  harfi rakam say) her zaman yenmeli.
- Belirsiz girdilerin (`84CLY063`) net okumalardan düşük skor alması.

**test_oylama.py** — Kare kare adaylardan sonuç üretme.
- `34MAA484` — *sahada yanlış gönderildi.* Tek çok net okuma (0.92), iki
  bulanık okumadan (0.61+0.55) daha güvenilirdir. Oylama kare SAYISINA değil
  KANIT AĞIRLIĞINA göre yapılmalı.
- `34SG948` — *sahada kamyonet KAPI YAZISINDAN uyduruldu.* Kanıtın yalnızca
  %28'ine sahip bir aday gönderilmemeli.
- Hızlı geçen araçta hiçbir kare anlaşmıyorsa susmalı.

**test_ciftkayit.py** — Aynı araç için birden fazla kayıt engelleme.
- Sadece il kodu farklı okumalar (`34HRR696` / `14HRR696`) aynı araç sayılır.
- ⚠️ **Gövdesi farklı olanlar AYRI araçtır.** Lojistik filosunda ardışık
  plakalar var: `34POS625` ve `34POS628` sahada iki farklı kamyondu.
  Gövdeye tolerans gösteren bir birleştirme veri kaybettirir.

## Görüntü tabanlı doğrulama

Kod değişikliğinin gerçek karelerde işe yaradığını görmek için
`/app/debug_kareler/orijinal/` altındaki kayıtlı kareler kullanılabilir
(`DEBUG_ORIJINAL_KARE_KAYDET=true` iken birikir). Yöntem: kareyi aç, plakayı
gözle oku, sistemin ne dediğiyle karşılaştır. Bu oturumdaki hataların hepsi
böyle bulundu.
