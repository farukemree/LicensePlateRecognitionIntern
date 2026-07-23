"""Çift kayıt bastırma — saha vakalarıyla."""
import ast, re, sys, os
from typing import Optional,List,Tuple
src=open("/home/faruk/Plaka_Tanıma_Ai/ai-service/main.py",encoding="utf-8").read()
ns={"re":re,"Optional":Optional,"List":List,"Tuple":Tuple,"os":__import__("os")}
for d in ast.parse(src).body:
    ad=d.name if isinstance(d,ast.FunctionDef) else (d.targets[0].id if isinstance(d,ast.Assign) and isinstance(d.targets[0],ast.Name) else None)
    if ad in {"ayni_arac_mi","AYNI_PLAKA_BEKLEME"}: exec(ast.get_source_segment(src,d),ns)
f=ns["ayni_arac_mi"]

# (aciklama, onceden_gonderilen, yeni_okuma, bastirilmali_mi)
VAKA=[
 ("aynı plaka tekrar",          {"34HRR696":100.0}, "34HRR696", True),
 ("sadece il kodu farklı (34/14)",{"34HRR696":100.0}, "14HRR696", True),
 ("sadece il kodu farklı (34/44)",{"34HRR696":100.0}, "44HRR696", True),
 ("FİLO: gövde son hane farklı", {"34POS625":100.0}, "34POS628", False),
 ("FİLO: gövde ortası farklı",   {"34POS625":100.0}, "34PDS625", False),
 ("harf bloğu farklı",           {"34RHL635":100.0}, "34MHL635", False),
 ("süre dolmuş (121 sn önce)",   {"34HRR696":-21.0}, "14HRR696", False),
 ("duran araç (83 sn önce)",     {"34HRR696":17.0},  "34HRR696", True),
 ("tamamen farklı araç",         {"34HRR696":100.0}, "50AEY034", False),
]
hata=0
print(f"{'vaka':<32} {'önceki':<10} {'yeni':<10} {'sonuç':<12} ok")
print("-"*72)
for ad,gonderilen,yeni,beklenen in VAKA:
    r=f(yeni,gonderilen,100.0)
    bastirildi = r is not None
    ok = bastirildi==beklenen
    hata += 0 if ok else 1
    print(f"{ad:<32} {list(gonderilen)[0]:<10} {yeni:<10} "
          f"{'BASTIRILDI' if bastirildi else 'gönderilir':<12} {'✓' if ok else '✗'}")
print(f"\n{'🎉 GEÇTİ' if hata==0 else f'❌ {hata} BAŞARISIZ'}")
sys.exit(1 if hata else 0)
