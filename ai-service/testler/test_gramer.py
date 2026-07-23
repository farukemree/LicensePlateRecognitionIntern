"""main.py'deki gramer çözümleyicisini, modelleri yüklemeden izole test eder."""
import ast, re, sys, os
from typing import Optional, List, Tuple

KAYNAK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
GEREKLI = {
    "IL_KODLARI", "PLAKA_HARFLERI", "RAKAMLAR", "RAKAMA_DONUSUM", "HARFE_DONUSUM",
    "GUCLU_KARISTIRMA", "CEZA_GUCLU", "CEZA_ZAYIF", "BLOK_SEMALARI",
    "TR_BANDI_DESENLERI", "RAKAM_ICI_KARISTIRMA", "CEZA_IL_KURTARMA", "KAPSAMA_CEZASI",
    "_il_hane_adaylari", "_il_kodu_coz",
    "_karakteri_uyarla", "plaka_cozumle", "plaka_format_gecerli_mi",
    "plaka_temizle", "parcalari_birlestir", "zamansal_mutabakat",
}

src = open(KAYNAK, encoding="utf-8").read()
agac = ast.parse(src)
ns = {"re": re, "Optional": Optional, "List": List, "Tuple": Tuple}
parcalar = []
for dugum in agac.body:
    ad = None
    if isinstance(dugum, (ast.FunctionDef,)):
        ad = dugum.name
    elif isinstance(dugum, ast.Assign) and isinstance(dugum.targets[0], ast.Name):
        ad = dugum.targets[0].id
    if ad in GEREKLI:
        parcalar.append(ast.get_source_segment(src, dugum))
exec("\n".join(parcalar), ns)

plaka_cozumle = ns["plaka_cozumle"]
plaka_format_gecerli_mi = ns["plaka_format_gecerli_mi"]
parcalari_birlestir = ns["parcalari_birlestir"]
zamansal_mutabakat = ns["zamansal_mutabakat"]

print(f"✓ {len(parcalar)} tanım çıkarıldı\n")

# ---------------------------------------------------------------- 1) GRAMER
# Sahadaki loglardan alınan GERÇEK ham OCR çıktıları. Doğru plaka: 34CLY063
VAKALAR = [
    # (ham OCR metni, beklenen plaka)
    ("34CLY063",   "34CLY063"),   # temiz okuma
    ("B4CLY063",   "34CLY063"),   # 3->B karıştırması (loglarda en sık)
    ("84CLY063",   "BELIRSIZ"),   # 84 geçersiz VE belirsiz (34/64/81?) -> net bir okumadan düşük skorlu olmalı
    ("B4CLY", None),                # eksik, çözümlenemez
    ("TR34CLY063", "34CLY063"),   # mavi TR bandı önde
    ("134CLY063",  "34CLY063"),   # başta çöp karakter
    ("34CLY0G3",   "34CLY063"),   # 6->G
    ("34CIY063",   "34CIY063"),   # CIY de geçerli harf dizisi (düzeltme yok)
    ("340LY063",   "34OLY063"),   # 0->O harf konumunda
    ("3ACLY063",   "34CLY063"),   # A->4 rakam konumunda
    ("34CLY06",    "34CLY06"),    # 3 harf + 2 rakam = geçerli
    ("99CLY063",   "BELIRSIZ"),   # 99 geçersiz ve belirsiz
    ("34ABC12",    "34ABC12"),
    ("06BW1234",   None),          # W plakada yok
    ("34A12345",   "34A12345"),   # 1 harf + 5 rakam

    # 🔴 SAHA REGRESYONU (2026-07-23, canlı test): gerçek plaka 35 BPJ 875.
    # OCR parçaları doğruydu ('85'+'BPJ'+'875'), sadece il kodunun ilk hanesi
    # 8 okunmuştu = TEK hata. Çözümleyici İKİ hatalı '58PJ875'i seçiyordu
    # (baştaki karakteri at + 'B' harfini 8 rakamı say). Tek hatalı yorum
    # her zaman kazanmalı.
    ("85BPJ875",   "35BPJ875"),
    ("135BPJ875",  "35BPJ875"),   # il parçası fazladan haneyle okundu
    ("835BPJ875",  "35BPJ875"),
]

print("=== 1) GRAMER ÇÖZÜMLEYİCİ ===")
hata = 0
for ham, beklenen in VAKALAR:
    sonuc, skor = plaka_cozumle(ham, 1.0)
    if beklenen == "BELIRSIZ":
        # Girdi gerçekten belirsiz (birden fazla geçerli il kodu mümkün).
        # Doğru davranış: net bir okumadan (>=0.88) belirgin şekilde düşük
        # skor vermek — böylece tek başına değil, ancak karelerin
        # mutabakatıyla kabul edilebilir.
        ok = skor <= 0.65
    else:
        ok = (sonuc == beklenen)
    if not ok:
        hata += 1
    print(f"  {'✓' if ok else '✗'} {ham:<12} -> {str(sonuc):<10} (skor {skor:.2f})"
          f"{'' if ok else '   BEKLENEN: ' + str(beklenen)}")

# --------------------------------------------------- 2) PARÇA BİRLEŞTİRME
print("\n=== 2) PARÇA BİRLEŞTİRME (gerçek EasyOCR çıktısı biçiminde) ===")


def bbox(x1, y1, x2, y2):
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


# Loglardan: '34' (0.95) + 'CLY063' (0.99) aynı satırda
ocr1 = [(bbox(10, 20, 60, 70), "34", 0.95), (bbox(70, 20, 220, 70), "CLY063", 0.99)]
# Loglardan: 'TR' bandı + '134' + 'CLY063'
ocr2 = [(bbox(0, 22, 25, 68), "TR", 0.98), (bbox(30, 20, 80, 70), "134", 0.79),
        (bbox(85, 20, 230, 70), "CLY063", 0.72)]
# Farklı satırda firma yazısı olan durum
ocr3 = [(bbox(10, 20, 60, 70), "34", 0.9), (bbox(70, 20, 220, 70), "CLY063", 0.9),
        (bbox(10, 150, 200, 190), "GERGAL", 0.8)]

for ad, ocr in [("34+CLY063", ocr1), ("TR+134+CLY063", ocr2), ("34+CLY063+altsatir", ocr3)]:
    adaylar = parcalari_birlestir(ocr)
    en_iyi, en_skor = None, 0.0
    for metin, guven in adaylar:
        p, s = plaka_cozumle(metin, guven)
        if p and s > en_skor:
            en_iyi, en_skor = p, s
    ok = en_iyi == "34CLY063"
    if not ok:
        hata += 1
    print(f"  {'✓' if ok else '✗'} {ad:<22} -> {en_iyi} (skor {en_skor:.2f})  adaylar={[a[0] for a in adaylar][:4]}")

# ------------------------------------------------------ 3) ZAMANSAL MUTABAKAT
print("\n=== 3) ZAMANSAL MUTABAKAT (tek karelik hata bastırılıyor mu?) ===")
senaryolar = [
    ("4 doğru + 1 uydurma", [("34CLY063", 0.96), ("34CLY063", 0.97), ("34CLY063", 0.95),
                             ("34CLY063", 0.93), ("44LYO63", 0.51)], "34CLY063"),
    ("sadece 1 uydurma",    [("44LYO63", 0.51)], "44LYO63"),
    ("2-2 berabere",        [("34CLY063", 0.90), ("34CLY063", 0.88),
                             ("34CLY06", 0.60), ("34CLY06", 0.58)], "34CLY063"),
]
for ad, adaylar, beklenen in senaryolar:
    p, g, d, pay = zamansal_mutabakat(adaylar)
    ok = p == beklenen
    if not ok:
        hata += 1
    print(f"  {'✓' if ok else '✗'} {ad:<22} -> {p} (güven {g:.2f}, {d} kare destek)")

# 'sadece 1 uydurma' vakası: kabul kriterlerini de uygula
print("\n=== 4) KABUL KRİTERLERİ (uydurma sonuç backend'e gidebilir mi?) ===")
MIN_PLAKA_GUVENI, MIN_MUTABAKAT_KARE, TEK_KARE_KESIN_GUVEN, TEK_KARE_MIN_PAY = 0.55, 2, 0.88, 0.35
for ad, adaylar, _ in senaryolar:
    p, g, d, pay = zamansal_mutabakat(adaylar)
    yeterli = d >= MIN_MUTABAKAT_KARE or (g >= TEK_KARE_KESIN_GUVEN and pay >= TEK_KARE_MIN_PAY)
    gonderilir = (g >= MIN_PLAKA_GUVENI) and yeterli
    print(f"  {ad:<22} -> {p:<10} güven={g:.2f} destek={d}  GÖNDERİLİR mi: {'EVET' if gonderilir else 'HAYIR (elendi)'}")

print(f"\n{'🎉 TÜM TESTLER GEÇTİ' if hata == 0 else f'❌ {hata} TEST BAŞARISIZ'}")
sys.exit(1 if hata else 0)
