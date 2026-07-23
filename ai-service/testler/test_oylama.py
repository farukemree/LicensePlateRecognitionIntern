"""
SAHA REGRESYON TESTİ — 2026-07-23 canlı loglarından alınan gerçek episode'lar.
Her vaka, sistemin gerçekte ürettiği kare-kare adaylardan oluşuyor.
"""
import ast, re, sys, os
from typing import Optional, List, Tuple

KAYNAK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
GEREKLI = {"zamansal_mutabakat", "MIN_PLAKA_GUVENI", "MIN_MUTABAKAT_KARE",
           "TEK_KARE_KESIN_GUVEN", "TEK_KARE_MIN_PAY", "MIN_KANIT_PAYI"}
src = open(KAYNAK, encoding="utf-8").read()
agac = ast.parse(src)
ns = {"re": re, "Optional": Optional, "List": List, "Tuple": Tuple, "os": __import__("os")}
parcalar = []
for d in agac.body:
    ad = d.name if isinstance(d, ast.FunctionDef) else (
        d.targets[0].id if isinstance(d, ast.Assign) and isinstance(d.targets[0], ast.Name) else None)
    if ad in GEREKLI:
        parcalar.append(ast.get_source_segment(src, d))
exec("\n".join(parcalar), ns)

zamansal_mutabakat = ns["zamansal_mutabakat"]
def kanit_payi_yeterli(p): return p >= ns["MIN_KANIT_PAYI"]
MIN_GUVEN = ns["MIN_PLAKA_GUVENI"]
MIN_KARE = ns["MIN_MUTABAKAT_KARE"]
TEK_KARE_GUVEN = ns["TEK_KARE_KESIN_GUVEN"]
TEK_KARE_PAY = ns["TEK_KARE_MIN_PAY"]
MIN_PAY = ns["MIN_KANIT_PAYI"]
print(f"Eşikler: guven>={MIN_GUVEN} kare>={MIN_KARE} tek_kare_guven>={TEK_KARE_GUVEN} "
      f"tek_kare_pay>={TEK_KARE_PAY}\n")

# (ad, kare adayları, gerçek plaka | None, beklenen davranış)
#   "gonder"  -> doğru plakayı göndermeli
#   "elenmeli"-> hiçbir şey göndermemeli (yanlış cevap vermektense sessiz kal)
VAKALAR = [
    ("K2 34PKC775 (kolay)",
     [("24DEN12", 0.17), ("34PKC775", 0.91), ("34PKC775", 0.56),
      ("34PKC775", 0.97), ("34PKC775", 0.61), ("34PKC775", 0.98)],
     "34PKC775", "gonder"),

    ("K2 34HSE993 (kolay)",
     [("34HSE993", 0.90), ("34HSE993", 0.62), ("34HSE993", 0.68),
      ("34HSE993", 0.96), ("34BSE993", 0.67), ("34HSE993", 0.65)],
     "34HSE993", "gonder"),

    ("K2 50AEY034 (kolay)",
     [("50AEY034", 1.00), ("50AEY034", 1.00), ("50AEY034", 1.00),
      ("50AEY034", 0.99), ("50AEY034", 0.98), ("50AEV034", 0.97)],
     "50AEY034", "gonder"),

    # 🔴 GERİLEME VAKASI: eski oylama sayıyı mutlak öncelikli yaptığı için
    # 2 kez görülen YANLIŞ '34HAA484', 1 kez görülen ama çok daha güvenli
    # DOĞRU '34MAA484'ü yendi ve backend'e yanlış plaka gitti.
    ("K2 34MAA484 (M/H karışması — YANLIŞ GÖNDERİLMİŞTİ)",
     [("34MAA484", 0.92), ("34HAA484", 0.61), ("34HAA484", 0.55),
      ("34MA484", 0.59), ("60RSE548", 0.42), ("34KAA484", 0.44)],
     "34MAA484", "gonder"),

    # Hızlı geçen araç: doğru cevap (34HRP158) karelerden birinde var ama
    # düşük skorlu; hiçbir aday tekrar etmiyor. Emin olamadığımız için
    # susmak doğru davranış.
    ("K2 34HRP158 (hızlı araç, kaotik)",
     [("13AHR91", 0.49), ("34HRP10", 0.48), ("14HRP18", 0.64),
      ("14HRP10", 0.63), ("34HRP158", 0.47), ("14HRP150", 0.73)],
     "34HRP158", "elenmeli"),

    ("K1 06/16 karışması (gönderilmemişti)",
     [("06AKB337", 0.64), ("64KB337", 0.39)],
     "16AKB337", "elenmeli"),

    # 🔴 SAHA (2026-07-23): kamyonet KAPI YAZISINDAN uydurulan plaka.
    # 14 karenin 2'sinde göründü, kanıtın yalnızca %28'ine sahipti.
    ("K2 34SG948 (kapı yazısı - kaotik)",
     [("34SG948", 0.95), ("34SG948", 0.62), ("11AAA111", 0.80), ("22BBB222", 0.78),
      ("33CCC333", 0.75), ("44DDD444", 0.72), ("55EEE555", 0.70)],
     None, "elenmeli"),

    ("K1 34TY7350 (tek kare ama baskın)",
     [("05Z32288", 0.21), ("66AI0533", 0.46), ("34TY7350", 0.97), ("34JY750", 0.44)],
     "34TY7350", "gonder"),
]

hata = 0
print(f"{'vaka':<48} {'kazanan':<11} {'guv':<5} {'oy':<4} {'pay':<5} {'karar':<10} sonuc")
print("-" * 108)
for ad, adaylar, gercek, beklenen in VAKALAR:
    plaka, guven, destek, pay = zamansal_mutabakat(adaylar)
    yeterli = destek >= MIN_KARE or (guven >= TEK_KARE_GUVEN and pay >= TEK_KARE_PAY)
    gonderilir = guven >= MIN_GUVEN and kanit_payi_yeterli(pay) and yeterli
    karar = "GÖNDER" if gonderilir else "eleme"

    if beklenen == "gonder":
        ok = gonderilir and plaka == gercek
    else:
        ok = not gonderilir
    if not ok:
        hata += 1
    print(f"{ad:<48} {str(plaka):<11} {guven:<5.2f} {destek:<4} {pay:<5.2f} {karar:<10} "
          f"{'✓' if ok else '✗ BEKLENEN: ' + beklenen + (' ' + str(gercek) if gercek else '')}")

print(f"\n{'🎉 TÜM SAHA VAKALARI GEÇTİ' if hata == 0 else f'❌ {hata} VAKA BAŞARISIZ'}")
sys.exit(1 if hata else 0)
