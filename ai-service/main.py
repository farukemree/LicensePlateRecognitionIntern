from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import uvicorn
import requests
import time
import os
import re
import json
import base64
import threading
from urllib.parse import quote

# 🚨 OpenCV'yi TCP'ye zorlayacak çevresel değişkeni cv2'den ÖNCE set ediyoruz!
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

import cv2  # 👈 Çevresel değişken ayarlandıktan hemen sonra import ediliyor!
from datetime import datetime
import torch

# 🔓 PyTorch 2.6+ weights_only bypass (kendi güvenilir .pt dosyamız için)
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

from ultralytics import YOLO   # 👈 patch'ten SONRA import edilmeli
import easyocr
import torch.nn as nn

app = FastAPI(title="Lojistik Plaka Tanıma AI Servisi", version="1.2")

# Yeniden eğitim için veri setinin birikeceği klasörü oluşturuyoruz
RETRAIN_DIR = "/app/dataset/retrain"
os.makedirs(RETRAIN_DIR, exist_ok=True)

# 🐞 TEŞHİS MODU: Açıksa, YOLO'nun kırptığı HER HAM kareyi (hiçbir işleme
# tabi tutulmadan) diske kaydeder. "Hiçbir varyantta metin okunamadı" gibi
# toplu başarısızlıklarda gerçekte ne görüldüğünü gözle kontrol etmek için.
DEBUG_KARE_KAYDET = os.getenv("DEBUG_KARE_KAYDET", "false").lower() == "true"
DEBUG_KARE_DIR = "/app/debug_kareler"
if DEBUG_KARE_KAYDET:
    os.makedirs(DEBUG_KARE_DIR, exist_ok=True)
    print(f"🐞 TEŞHİS MODU AKTİF: Ham kareler '{DEBUG_KARE_DIR}' klasörüne kaydedilecek.")

# 🐞 ORİJİNAL KARE TEŞHİS MODU: Açıksa, her araç episode'unda en yüksek
# skorlu karenin TAM görüntüsünü (YOLO'nun çizdiği kutuyla birlikte) diske
# kaydeder. Amaç: kameranın gerçekte neyi "plaka" sandığını (sabit tabela,
# tarih/saat filigranı, kamyon üstü "kör nokta" uyarı yazısı vb.) gözle
# doğrulamak — böylece ileride bir ROI (ilgi alanı) tanımlanacaksa
# koordinatlar buradan çıkarılabilir.
DEBUG_ORIJINAL_KARE_KAYDET = os.getenv("DEBUG_ORIJINAL_KARE_KAYDET", "false").lower() == "true"
# 👇 Varsayılan olarak DEBUG_KARE_DIR'in (/app/debug_kareler) ALTINDA bir alt
# klasör kullanıyoruz — bu sayede ekstra bir "-v" bind-mount eklemene gerek
# kalmadan, zaten docker run komutunda mount'lu olan
# /home/faruk/dhl-plaka/debug:/app/debug_kareler ile otomatik olarak host'a
# yansır. (Not: önceki sürümde buraya yanlışlıkla bir HOST yolu yazılmıştı —
# konteyner içinde o yol mount'suz olduğu için kayıtlar hiçbir yere
# yazılmayacaktı. Bu düzeltilmiş hâli.)
DEBUG_ORIJINAL_KARE_DIR = os.getenv("DEBUG_ORIJINAL_KARE_DIR", os.path.join(DEBUG_KARE_DIR, "orijinal"))
if DEBUG_ORIJINAL_KARE_KAYDET:
    os.makedirs(DEBUG_ORIJINAL_KARE_DIR, exist_ok=True)
    print(f"🐞 ORİJİNAL KARE TEŞHİS MODU AKTİF: Tam kareler (YOLO kutusu çizili) '{DEBUG_ORIJINAL_KARE_DIR}' klasörüne kaydedilecek.")

print("🧠 YOLOv8 ve EasyOCR modelleri belleğe yükleniyor...")
model = YOLO("license_plate_detector.pt")  # Plaka tespiti
detection_model = YOLO("yolov8m.pt")       # Araç/İnsan tespiti (COCO dataset)

# 🎯 --- TESPİT KALİTESİ AYARLARI ---
# Bu değerleri .env üzerinden değiştirebilirsin, deploy gerekmez.
# PLAKA_CONF_ESIGI: plaka dedektörünün confidence eşiği. Önceden HİÇ eşik
# yoktu (Ultralytics varsayılanı 0.25 kullanılıyordu) — bu da düşük güvenli/
# gürültülü kutuların (yanlış pozitiflerin) OCR'a kadar sızmasına izin
# veriyordu. 0.4 civarı, çoğu senaryoda iyi bir denge noktasıdır.
PLAKA_CONF_ESIGI = float(os.getenv("PLAKA_CONF_ESIGI", "0.4"))
# PLAKA_IMGSZ: YOLO'nun inference çözünürlüğü. Varsayılan 640 küçük/uzak
# plakalarda karakterleri kaybettirebiliyor. 1280 yapmak, biraz daha yavaş
# ama gözle görülür şekilde daha isabetli tespit sağlar.
PLAKA_IMGSZ = int(os.getenv("PLAKA_IMGSZ", "1280"))

# 🚗 COCO Veri Seti Sınıfları
COCO_CLASSES = {
    0: "insan", 2: "araba", 3: "motosiklet", 5: "otobüs", 7: "kamyon",
    15: "kedi", 16: "köpek"  # bonus
}

easyocr_cache_dir = os.getenv("EASYOCR_MODULE_DATA_DIR", "/app/.easyocr")
gpu_kullanilabilir = torch.cuda.is_available()
print(f"🖥️ GPU durumu: {'AKTİF ✅' if gpu_kullanilabilir else 'PASİF (CPU üzerinde çalışılıyor) ⚠️'}")
reader = easyocr.Reader(['tr', 'en'], gpu=gpu_kullanilabilir, model_storage_directory=easyocr_cache_dir)
# ⚠️ Not: 'detail' ve 'paragraph' Reader()'ın değil reader.readtext()'in
# parametreleridir. Kod içindeki tüm readtext() çağrıları zaten varsayılan
# detail=1, paragraph=False ile çağrılıyor — bu da (bbox, text, prob)
# üçlüsünü döndürür ve parcalari_plaka_olarak_birlestir() fonksiyonunun
# beklediği format tam olarak budur. paragraph=True verilirse readtext()
# confidence değerini KALDIRIR ((bbox, text) döner) ve aşağıdaki tüm
# unpacking mantığı kırılır — o yüzden bilerek eklemiyoruz.
print("✅ Modeller başarıyla yüklendi, sistem tetikte!")

# 📷 PLAKA OKUMASINI İYİLEŞTİREN PREPROCESSING FONKSİYONU
def plaka_ocr_preprocessing(plaka_gorsel):
    """Kırpılan plaka görseline contrast + sharpness ekle"""
    import numpy as np
    
    # 1️⃣ Contrast Enhancement (CLAHE)
    lab = cv2.cvtColor(plaka_gorsel, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge([l, a, b])
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    
    # 2️⃣ Resize (Daha büyük → OCR daha iyi)
    h, w = enhanced.shape[:2]
    if w < 400:
        scale = 400 / w
        enhanced = cv2.resize(enhanced, (int(w * scale), int(h * scale)), 
                              interpolation=cv2.INTER_CUBIC)
    
    # 3️⃣ Bilateral Filter (Noise azalt, kenarlar koruyarak)
    enhanced = cv2.bilateralFilter(enhanced, 9, 75, 75)
    
    return enhanced

# --- 📋 VERİ YAPILARI ---
class KameraIstek(BaseModel):
    kamera_id: int
    depo_id: int
    rtsp_url: str
    yon: Optional[str] = "bilinmiyor"   # "giris" / "cikis" — manuel testler için opsiyonel
    aktif_mi: Optional[bool] = True

class PlakaVeriPaketi(BaseModel):
    kamera_id: int
    depo_id: int
    yon: str            # "giris" veya "cikis" — .NET tarafının hangi kapıdan geçtiğini ayırt etmesi için
    plaka_metni: str
    arac_tipi: str      # "araba", "kamyon", "otobüs" vb.
    guven_skoru: float
    tarih_saat: str
    plaka_gorseli_base64: Optional[str] = None  # 🖼️ Okunan plakanın kırpılmış görseli (JPEG, base64)
    tam_kare_gorseli_base64: Optional[str] = None  # 🖼️ Aracın tam kare görseli (YOLO kutusu ile), opsiyonel

class PlakaDuzeltmeIstek(BaseModel):
    kamera_id: int      # Hangi kameranın görüntüsü düzeltilecek (giriş mi çıkış mı)
    yanlis_plaka: str
    dogru_plaka: str

# 🎥 --- SABİT KAMERA TANIMLARI (GEBZE) ---
# Servis ayağa kalktığında Swagger'dan elle tetiklemeye gerek kalmadan bu
# kameralar otomatik olarak izlemeye başlar. Şifredeki '@' karakteri URL
# içinde ayraç anlamına geldiği için mutlaka %40 olarak encode edilmeli
# (quote() bunu garantiye alıyor, elle yazılmış URL'lerdeki tutarsızlığı önler).
_GEBZE_SIFRE_ENCODED = quote("center@dhl99", safe="")

# 📡 RTSP PROFİL SEÇİMİ: IP kameralarda genelde profile1 = ana akış (yüksek
# çözünürlük), profile2/profile3 = alt akış (düşük çözünürlük, önizleme/
# mobil için tasarlanmıştır). Önceden profile2 kullanılıyordu — bu, plaka
# karakterlerinin OCR için yetersiz piksel çözünürlüğüne düşmesine ve
# "hiçbir varyantta metin okunamadı" hatalarına yol açan en olası sebepti.
# RTSP_PROFIL ile .env üzerinden geri alınabilir (bant genişliği sorunu
# yaşarsan "profile2" yaparak eski davranışa dönebilirsin).
RTSP_PROFIL = os.getenv("RTSP_PROFIL", "profile1")

GEBZE_KAMERALARI = [
    {
        "kamera_id": 1,
        "depo_id": 1,
        "yon": "giris",
        "isim": "Gebze Giriş Kamerası",
        "rtsp_url": f"rtsp://admin:{_GEBZE_SIFRE_ENCODED}@2.200.168.165:8001/{RTSP_PROFIL}/media.smp",
    },
    {
        "kamera_id": 2,
        "depo_id": 1,
        "yon": "cikis",
        "isim": "Gebze Çıkış Kamerası",
        "rtsp_url": f"rtsp://admin:{_GEBZE_SIFRE_ENCODED}@2.200.168.165:8003/{RTSP_PROFIL}/media.smp",
    },
]

# 💡 Global değişkenlerde son işlenen kareyi ve okunan plakayı tutuyoruz
# 💡 Kamera başına ayrı tutuluyor (dict) — birden fazla kamera (giriş/çıkış)
# AYNI ANDA çalıştığı için, tek bir global değişken kameralar arasında
# görüntü karışmasına yol açardı. Anahtar: kamera_id
son_yakalanan_goruntuler = {}
son_okunan_plaka_global = ""

# 🧠 --- KENDİ KENDİNE ÖĞRENME: DÜZELTME HAFIZASI ---
# Güvenlik görevlisi bir plakayı düzelttiğinde (yanlis -> dogru), bu eşleşme
# kalıcı bir JSON dosyasına yazılır. Canlı akışta OCR'ın ürettiği sonuç, daha
# önce yapılmış düzeltmelerle (tam veya yakın eşleşme) karşılaştırılır; bir
# eşleşme bulunursa sonuç otomatik olarak düzeltilir. Bu, gerçek bir model
# eğitimi (retraining) DEĞİLDİR — anlık, hafif bir "öğrenilmiş düzeltme" katmanıdır.
# Gerçek model fine-tuning'i için RETRAIN_DIR'de biriken etiketli görseller
# kullanılır (bkz. sohbetin sonundaki yol haritası açıklaması).
DUZELTME_HAFIZASI_YOLU = os.path.join(os.path.dirname(RETRAIN_DIR), "duzeltme_hafizasi.json")


def duzeltme_hafizasini_yukle():
    if os.path.exists(DUZELTME_HAFIZASI_YOLU):
        try:
            with open(DUZELTME_HAFIZASI_YOLU, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Düzeltme hafızası okunamadı, boş başlatılıyor: {e}")
    return {}


def duzeltme_hafizasini_kaydet(hafiza: dict):
    try:
        with open(DUZELTME_HAFIZASI_YOLU, "w", encoding="utf-8") as f:
            json.dump(hafiza, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Düzeltme hafızası diske kaydedilemedi: {e}")


DUZELTME_HAFIZASI = duzeltme_hafizasini_yukle()
print(f"🧠 Düzeltme hafızası yüklendi: {len(DUZELTME_HAFIZASI)} kayıtlı düzeltme mevcut.")


def levenshtein_mesafesi(a: str, b: str) -> int:
    """ İki string arasındaki düzenleme (edit distance) mesafesini hesaplar """
    if a == b:
        return 0
    if len(a) == 0:
        return len(b)
    if len(b) == 0:
        return len(a)

    onceki_satir = list(range(len(b) + 1))
    for i, karakter_a in enumerate(a, start=1):
        simdiki_satir = [i] + [0] * len(b)
        for j, karakter_b in enumerate(b, start=1):
            ekleme = onceki_satir[j] + 1
            silme = simdiki_satir[j - 1] + 1
            degistirme = onceki_satir[j - 1] + (karakter_a != karakter_b)
            simdiki_satir[j] = min(ekleme, silme, degistirme)
        onceki_satir = simdiki_satir
    return onceki_satir[-1]


def hafizadan_duzelt(plaka: str, esik_mesafe: int = 2):
    """
    OCR'dan gelen plakayı, daha önce güvenlik görevlisi tarafından yapılmış
    düzeltmelerle karşılaştırır. Tam eşleşme varsa direkt, yakın eşleşme
    varsa (edit distance <= esik_mesafe, aynı uzunlukta) en yakın olanı döner.
    Eşleşme yoksa plakayı olduğu gibi (degismedi=False) döner.
    """
    if plaka in DUZELTME_HAFIZASI:
        return DUZELTME_HAFIZASI[plaka], True

    en_yakin_dogru, en_yakin_mesafe = None, esik_mesafe + 1
    for yanlis, dogru in DUZELTME_HAFIZASI.items():
        if len(yanlis) != len(plaka):
            continue
        mesafe = levenshtein_mesafesi(plaka, yanlis)
        if mesafe < en_yakin_mesafe:
            en_yakin_mesafe = mesafe
            en_yakin_dogru = dogru

    if en_yakin_dogru is not None:
        return en_yakin_dogru, True

    return plaka, False

# 💡 .NET API URL'si
DOTNET_API_URL = "http://192.168.1.141:5000/api/v1/plates/detected"

# --- 🎯 TÜRK PLAKA FORMAT DOĞRULAMA ---
# Türk plakalarında Q, W, X harfleri kullanılmaz
IL_KODU = r'(0[1-9]|[1-7][0-9]|8[01])'
PLAKA_PATTERNS = [
    re.compile(rf'^{IL_KODU}[A-PR-VYZ]{{1}}[0-9]{{4,5}}$'),   # 34A1234 / 34A12345
    re.compile(rf'^{IL_KODU}[A-PR-VYZ]{{2}}[0-9]{{3,4}}$'),   # 34AB123 / 34AB1234
    re.compile(rf'^{IL_KODU}[A-PR-VYZ]{{3}}[0-9]{{2,3}}$'),   # 34ABC12 / 34ABC123
]

EASYOCR_ALLOWLIST = "ABCDEFGHIJKLMNOPRSTUVYZ0123456789"

# --- 🚫 SABİT TABELA / FİLİGRAN KARA LİSTESİ ---
# Kameranın gördüğü alanda hep aynı yerde duran, plaka OLMAYAN ama OCR'ın
# yüksek güvenle okuduğu metinler: kamera üzerine yazılmış "GEBZE GİRİŞ/ÇIKIŞ"
# etiketi, kamyonların üzerindeki "ANGLES MORTS" (kör nokta) uyarı çıkartması,
# firma/kargo yazıları vb. Format regex'i (plaka_format_gecerli_mi) bunların
# çoğunu zaten eler çünkü il koduyla başlamıyorlar, ama parça harfleri sayısal
# filigranla (tarih/saat damgası) yan yana gelip yanlışlıkla geçerli bir
# formata benzeyebiliyor. Bu yüzden OCR parçalarını birleştirmeden ÖNCE,
# bilinen bu metinleri tamamen eliyoruz — böylece en iyi 5 kare arasına bile
# giremiyorlar.
YASAKLI_KELIMELER = {
    "GEBZE", "GIRIS", "CIKIS", "ANGLES", "MORTS", "ANGLESMORTS",
    "CARGO", "B2CARGO", "DEPO", "KAMERA", "WAREHOUSE", "WATERMARK",
}


def yasakli_metin_mi(temiz_text: str) -> bool:
    """
    Temizlenmiş bir OCR parçasının, bilinen sabit tabela/filigran
    kara listesiyle (elle girilmiş VEYA kendiliğinden öğrenilmiş) eşleşip
    eşleşmediğini kontrol eder. Hem tam eşleşmeyi hem de kısmi (substring)
    eşleşmeyi yakalar, çünkü OCR bazen kelimenin sadece bir kısmını
    ("ANGLE" yerine "ANGLES", "GIRIS" yerine "GIRI" gibi) okuyabiliyor.
    """
    if not temiz_text or len(temiz_text) < 3:
        return False
    tum_yasakli = YASAKLI_KELIMELER | OTO_YASAKLI_KELIMELER
    for kelime in tum_yasakli:
        if kelime in temiz_text or temiz_text in kelime:
            return True
    return False


# --- 🧠 KENDİ KENDİNE ÖĞRENEN KARA LİSTE ---
# Elle yazdığımız YASAKLI_KELIMELER listesi sabit — yeni bir tabela ya da
# kamyon çıkartması gördükçe kodu elden geçirip yeniden deploy etmek pratik
# değil. Bunun yerine: her araç episode'unda, OCR'ın okuduğu ama TEK BAŞINA
# hiçbir zaman geçerli plaka formatına uymayan (harf içeren, en az 4
# karakterlik) parçaları not ediyoruz. Aynı parça yeterince FARKLI araç
# geçişinde (aynı episode içinde değil!) tekrar ederse, bu kesin bir sabit
# tabela/filigran/çıkartma yazısıdır — otomatik olarak kara listeye eklenir
# ve kalıcı bir JSON dosyasına yazılır, böylece konteyner yeniden başlasa
# bile öğrenilen kelimeler kaybolmaz.
OTO_KARA_LISTE_DOSYASI = os.path.join(os.path.dirname(RETRAIN_DIR), "oto_kara_listesi.json")
OTO_KARA_LISTE_ESIK = int(os.getenv("OTO_KARA_LISTE_ESIK", "3"))  # kaç FARKLI araçta görülünce eklensin


def oto_kara_listesini_yukle():
    if os.path.exists(OTO_KARA_LISTE_DOSYASI):
        try:
            with open(OTO_KARA_LISTE_DOSYASI, "r", encoding="utf-8") as f:
                veri = json.load(f)
                return set(veri.get("kelimeler", [])), veri.get("sayaclar", {})
        except Exception as e:
            print(f"⚠️ Otomatik kara liste okunamadı, boş başlatılıyor: {e}")
    return set(), {}


def oto_kara_listesini_kaydet():
    try:
        with open(OTO_KARA_LISTE_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(
                {"kelimeler": sorted(OTO_YASAKLI_KELIMELER), "sayaclar": OTO_KELIME_SAYAC},
                f, ensure_ascii=False, indent=2
            )
    except Exception as e:
        print(f"⚠️ Otomatik kara liste diske kaydedilemedi: {e}")


OTO_YASAKLI_KELIMELER, OTO_KELIME_SAYAC = oto_kara_listesini_yukle()
print(f"🧠 Otomatik kara liste yüklendi: {len(OTO_YASAKLI_KELIMELER)} öğrenilmiş kelime, {len(OTO_KELIME_SAYAC)} takip edilen aday.")


def episode_junk_kelimelerini_degerlendir(bu_episode_kelimeleri: set):
    """
    Bir araç episode'u bitince çağrılır. O episode'da görülen ama plaka
    formatına asla uymayan benzersiz metin parçalarının sayacını bir
    artırır (aynı episode içinde 10 kere görülse bile sadece +1 — çünkü
    sabit bir tabela zaten TEK bir araç geçişinde bile onlarca karede
    görünür; asıl kanıt, FARKLI araç geçişlerinde de tekrar etmesidir).
    Eşiği aşan kelime otomatik olarak kara listeye alınır ve diske yazılır.
    """
    global OTO_YASAKLI_KELIMELER, OTO_KELIME_SAYAC
    degisiklik_oldu = False
    for kelime in bu_episode_kelimeleri:
        if kelime in YASAKLI_KELIMELER or kelime in OTO_YASAKLI_KELIMELER:
            continue
        OTO_KELIME_SAYAC[kelime] = OTO_KELIME_SAYAC.get(kelime, 0) + 1
        degisiklik_oldu = True
        if OTO_KELIME_SAYAC[kelime] >= OTO_KARA_LISTE_ESIK:
            OTO_YASAKLI_KELIMELER.add(kelime)
            print(f"🧠 [OTOMATİK KARA LİSTE] '{kelime}' {OTO_KELIME_SAYAC[kelime]} farklı araç geçişinde tekrar etti — otomatik olarak kara listeye eklendi.")
    if degisiklik_oldu:
        oto_kara_listesini_kaydet()


def plaka_format_gecerli_mi(plaka: str) -> bool:
    """ Metnin standart Türk plaka formatına uyup uymadığını kontrol eder """
    return any(p.match(plaka) for p in PLAKA_PATTERNS)


def plaka_temizle(text):
    """ EasyOCR'dan gelen metni temizler, sadece A-Z0-9 bırakır """
    text = text.upper().replace(" ", "").strip()
    # Türkçe karakter -> Latin karşılığı (OCR bazen İ/Ö/Ü gibi okuyabiliyor)
    tr_map = str.maketrans("İIÖÜÇŞĞ", "IIOUCSG")
    text = text.translate(tr_map)
    cleaned = re.sub(r'[^A-Z0-9]', '', text)
    return cleaned

def parcalari_plaka_olarak_birlestir(ocr_results):
    """
    EasyOCR'dan gelen (bbox, text, prob) parçalarını x-koordinatına göre
    soldan sağa sıralar, ardışık alt-dizileri dener ve geçerli TR plaka
    formatına uyan, en yüksek ortalama güvene sahip kombinasyonu döner.
    Geçerli bir kombinasyon yoksa (None, 0.0) döner.

    🆕 Y-EKSENİ TUTARLILIK KONTROLÜ: Parçaları birleştirirken sadece
    x-koordinatına bakmak yeterli değil — plaka üstündeki farklı bir
    satırda duran metin (firma yazısı, filigran, ikinci satır il/ilçe
    kodu vb.) x eksininde plakayla çakışabilir ama y ekseninde belirgin
    şekilde farklı bir yükseklikte olur. Bu yüzden bir sonraki parçayı
    zincire eklemeden önce, önceki parçayla dikey merkez farkının parça
    yüksekliğine oranla makul olup olmadığını kontrol ediyoruz.
    """
    parcalar = []
    for bbox, text, prob in ocr_results:
        # 📊 Çok düşük güven parçaları hemen atla
        if prob < 0.25:  # %25'ten az güven = çöp (False positive)
            continue
        
        temiz = plaka_temizle(text)
        if not temiz:
            continue
        if yasakli_metin_mi(temiz):
            print(f"   🚫 [Kara Liste] '{temiz}' parçası elendi (plaka olamayacak sabit metin).")
            continue

        # bbox 4 nokta: [ [x1,y1], [x2,y2], [x3,y3], [x4,y4] ]
        x_min = min(nokta[0] for nokta in bbox)
        y_coords = [nokta[1] for nokta in bbox]
        y_min, y_max = min(y_coords), max(y_coords)
        y_center = (y_min + y_max) / 2
        yukseklik = max(y_max - y_min, 1)  # 0'a bölünmeyi önlemek için min 1

        parcalar.append({
            "text": temiz, "prob": prob, "x": x_min,
            "y_center": y_center, "yukseklik": yukseklik
        })

    parcalar.sort(key=lambda p: p["x"])
    n = len(parcalar)
    adaylar = []

    # 🔧 Aynı satırda sayılabilmek için: iki parçanın y_center farkı,
    # ikisinin ortalama yüksekliğinin şu katsayısını aşmamalı.
    Y_TUTARLILIK_KATSAYISI = 0.6

    for i in range(n):
        birlesik, problar = "", []
        onceki_parca = None

        for j in range(i, n):
            simdiki_parca = parcalar[j]

            if onceki_parca is not None:
                y_farki = abs(simdiki_parca["y_center"] - onceki_parca["y_center"])
                ort_yukseklik = (simdiki_parca["yukseklik"] + onceki_parca["yukseklik"]) / 2
                if y_farki > ort_yukseklik * Y_TUTARLILIK_KATSAYISI:
                    # Bu parça farklı bir satırda/yükseklikte — zinciri burada kes,
                    # bu j'den sonrasını bu başlangıç (i) için denemeyi bırak
                    break

            birlesik += simdiki_parca["text"]
            problar.append(simdiki_parca["prob"])
            onceki_parca = simdiki_parca

            if plaka_format_gecerli_mi(birlesik):
                adaylar.append((birlesik, sum(problar) / len(problar)))
                
                # 🔄 ALTERNATIF PLAKALARI DENE: 1↔I, 0↔O vb. (OCR karıştırması çok yaygın)
                for katiksiz, katikli in [("1", "I"), ("I", "1"), ("0", "O"), ("O", "0")]:
                    alternatif = birlesik.replace(katiksiz, katikli)
                    if alternatif != birlesik and plaka_format_gecerli_mi(alternatif):
                        adaylar.append((alternatif, sum(problar) / len(problar) * 0.95))  # Düşük güven, alternattif olduğu için

    if not adaylar:
        return None, 0.0

    adaylar.sort(key=lambda x: x[1], reverse=True)
    return adaylar[0]


def esnek_plaka_ara(ocr_results):
    """
    🩹 FALLBACK EŞLEŞTİRİCİ: parcalari_plaka_olarak_birlestir() KATI bir
    zincirleme yapar — parçalar arasında y ekseninde uyumsuz TEK bir
    gürültü/bozuk-okuma parçası bile (örn. "50" yerine "0506" gibi bozuk
    okunmuş bir bölge) zinciri kırıp, aslında doğru okunmuş komşu
    parçaların (örn. "AFM", "568") hiç birleştirilememesine yol açabiliyor.

    Bu fonksiyon çok daha gevşek çalışır: TÜM parçaları (y ekseni kontrolü
    YAPMADAN) x koordinatına göre sırayla yapıştırır, ortaya çıkan uzun
    string içinde regex ile geçerli bir TR plaka alt-dizisi arar. Daha
    toleranslı ama yanlış pozitif riski biraz daha yüksek olduğu için
    SADECE birincil (katı) yöntem hiçbir sonuç veremediğinde, ikincil bir
    kaynak olarak kullanılır — güveni de bilerek biraz düşürülür.
    """
    parcalar = []
    for bbox, text, prob in ocr_results:
        if prob < 0.20:
            continue
        temiz = plaka_temizle(text)
        if not temiz or yasakli_metin_mi(temiz):
            continue
        x_min = min(nokta[0] for nokta in bbox)
        parcalar.append((x_min, temiz, prob))

    if not parcalar:
        return None, 0.0

    parcalar.sort(key=lambda p: p[0])
    birlesik = "".join(p[1] for p in parcalar)
    ortalama_guven = sum(p[2] for p in parcalar) / len(parcalar)

    # Türk plakaları 7 ya da 8 karakter uzunluğunda (il kodu + harf + rakam)
    for uzunluk in (8, 7):
        for basla in range(0, max(0, len(birlesik) - uzunluk + 1)):
            aday = birlesik[basla:basla + uzunluk]
            if plaka_format_gecerli_mi(aday):
                # Fallback olduğu için güveni %85'e çarpıyoruz — birincil
                # yöntemden gelen bir adayla eşitse birincil yöntem kazansın.
                return aday, ortalama_guven * 0.85

    return None, 0.0


def plakayi_izole_et(crop_bgr):
    """
    YOLO'nun geniş kestiği alandan gerçek plaka dikdörtgenini bulup
    daha sıkı kırpar. Bulunamazsa orijinal crop'u fallback olarak döner.
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return crop_bgr

    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    konturlar, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    h_crop, w_crop = gray.shape[:2]
    en_iyi_kontur, en_iyi_skor = None, 0

    for kontur in konturlar:
        x, y, w, h = cv2.boundingRect(kontur)
        if w < 40 or h < 12:
            continue
        aspect = w / float(h)
        alan_orani = (w * h) / float(w_crop * h_crop)

        if 3.5 <= aspect <= 6.0 and 0.15 <= alan_orani <= 0.95:
            if alan_orani > en_iyi_skor:
                en_iyi_skor = alan_orani
                en_iyi_kontur = (x, y, w, h)

    if en_iyi_kontur is not None:
        x, y, w, h = en_iyi_kontur
        pad = 10  # 📐 Daha geniş padding (hareketi olan araçlar için)
        y1, y2 = max(0, y - pad), min(h_crop, y + h + pad)
        x1, x2 = max(0, x - pad), min(w_crop, x + w + pad)
        izole = crop_bgr[y1:y2, x1:x2]
        if izole.size > 0:
            return izole

    return crop_bgr  # kontur bulunamadıysa orijinali dön


def on_isleme_varyantlari(crop_bgr):
    """
    Tek bir sert (global OTSU) binarizasyon yerine, farklı ışık/kontrast
    koşullarına dayanıklı birden fazla varyant üretir. Gölgeli, parlak
    yansımalı veya düşük kontrastlı karelerde global OTSU metni tamamen
    silebiliyor; bu yüzden EasyOCR'a sırayla birkaç versiyon denetiyoruz.
    """
    resized = cv2.resize(crop_bgr, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    varyantlar = []

    # 1) CLAHE ile kontrast güçlendirilmiş gri görsel (binarizasyon YOK)
    #    Çoğu durumda en güvenilir varyant budur çünkü ince karakter
    #    detaylarını kaybetmez.
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    clahe_gray = clahe.apply(gray)
    varyantlar.append(clahe_gray)

    # 2) Adaptif (bölgesel) eşikleme — sabit global eşik yerine, plaka
    #    üzerindeki gölge/parlama farklılıklarına yerel olarak uyum sağlar
    adaptif = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 10
    )
    varyantlar.append(adaptif)

    # 3) Global OTSU (eski yöntem) — bazı temiz, düz ışıklı karelerde
    #    hâlâ en iyi sonucu verebiliyor, bu yüzden fallback olarak tutuyoruz
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    varyantlar.append(otsu)

    # 4) Unsharp mask (keskinleştirme) + CLAHE — uzak/küçük plakalarda 3x
    #    büyütme sırasında oluşan hafif bulanıklığı telafi etmeye çalışır.
    #    Harflerin birbirine karışıp (örn. "AFM" yerine "AFY"/"TMG" gibi
    #    tutarsız okumalara) yol açan durumları azaltması beklenir.
    bulanik = cv2.GaussianBlur(clahe_gray, (0, 0), sigmaX=2.0)
    keskin = cv2.addWeighted(clahe_gray, 1.6, bulanik, -0.6, 0)
    varyantlar.append(keskin)

    return varyantlar


def kareyi_oku(best_crop):
    """
    Bir plaka karesini izole eder, birden fazla ön-işleme varyantıyla
    OCR dener ve TÜM varyantlar arasından en yüksek ortalama güvene sahip,
    formatı doğrulanmış plakayı döner. Hiçbiri geçerli değilse (None, 0.0, []) döner.
    """
    if best_crop is None or best_crop.size == 0:
        print("   ⚠️ [Teşhis] Gelen kare boş/None — YOLO kutusu geçersiz olabilir.")
        return None, 0.0, []

    h, w = best_crop.shape[:2]
    if w < 15 or h < 8:
        print(f"   ⚠️ [Teşhis] Kare çok küçük ({w}x{h}px) — OCR için yetersiz çözünürlük.")

    # 📷 PREPROCESSING: Contrast artır, noise azalt, resize yap
    best_crop = plaka_ocr_preprocessing(best_crop)
    
    izole_edilmis = plakayi_izole_et(best_crop)
    varyantlar = on_isleme_varyantlari(izole_edilmis)

    en_iyi_plaka, en_iyi_guven = None, 0.0
    tum_ham_parcalar = []

    for v_idx, varyant in enumerate(varyantlar):
        ocr_results = reader.readtext(varyant, allowlist=EASYOCR_ALLOWLIST)

        if not ocr_results:
            continue

        for (bbox, text, prob) in ocr_results:
            tum_ham_parcalar.append((v_idx, text, prob))

        plaka, ortalama_guven = parcalari_plaka_olarak_birlestir(ocr_results)

        # 🩹 Katı zincirleme bu varyantta hiçbir aday üretemediyse, daha
        # toleranslı fallback'i dene. Bu, "50" gibi bozuk okunan tek bir
        # parça yüzünden aslında doğru okunmuş "AFM"+"568" gibi komşu
        # parçaların çöpe gitmesini engelliyor.
        if plaka is None:
            plaka, ortalama_guven = esnek_plaka_ara(ocr_results)
            if plaka is not None:
                print(f"   🩹 [Esnek Eşleştirme] Katı zincirleme başarısız oldu ama fallback bir aday buldu: '{plaka}' (Güven: {ortalama_guven:.2f})")

        if plaka is not None and ortalama_guven > en_iyi_guven:
            en_iyi_plaka, en_iyi_guven = plaka, ortalama_guven

    return en_iyi_plaka, en_iyi_guven, tum_ham_parcalar


def keskinlik_skoru(gorsel_bgr):
    """ Laplacian varyansı ile görüntü netliğini ölçer (yüksek değer = daha net/az bulanık) """
    try:
        gray = cv2.cvtColor(gorsel_bgr, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var()
    except Exception:
        return 0.0


def oylama_ile_konsensus(adaylar):
    if not adaylar:
        return None, 0.0

    uzunluk_gruplari = {}
    for plaka, guven in adaylar:
        uzunluk_gruplari.setdefault(len(plaka), []).append((plaka, guven))

    en_iyi_uzunluk = max(uzunluk_gruplari, key=lambda L: sum(g for _, g in uzunluk_gruplari[L]))
    grup = uzunluk_gruplari[en_iyi_uzunluk]

    # 🔑 Tek aday varsa oylamaya hiç girmeden direkt onu dön —
    # normalize edilmiş "sahte 1.0" güven üretmesin
    if len(grup) == 1:
        return grup[0]

    konsensus_karakterler = []
    pozisyon_guvenleri = []
    for pos in range(en_iyi_uzunluk):
        oy_agirliklari = {}
        for plaka, guven in grup:
            karakter = plaka[pos]
            oy_agirliklari[karakter] = oy_agirliklari.get(karakter, 0.0) + guven
        en_iyi_karakter = max(oy_agirliklari, key=oy_agirliklari.get)
        konsensus_karakterler.append(en_iyi_karakter)
        toplam_agirlik = sum(oy_agirliklari.values())
        pozisyon_guveni = oy_agirliklari[en_iyi_karakter] / toplam_agirlik if toplam_agirlik > 0 else 0.0
        pozisyon_guvenleri.append(pozisyon_guveni)

    konsensus_plaka = "".join(konsensus_karakterler)
    # Konsensüs güvenini, oy sayısından bağımsız gerçek ortalamayla harmanla
    ham_ortalama = sum(g for _, g in grup) / len(grup)
    konsensus_guven = (sum(pozisyon_guvenleri) / len(pozisyon_guvenleri)) * 0.5 + ham_ortalama * 0.5

    if not plaka_format_gecerli_mi(konsensus_plaka):
        grup_sirali = sorted(grup, key=lambda x: x[1], reverse=True)
        return grup_sirali[0]

    return konsensus_plaka, konsensus_guven


def kutu_ortusme_orani(kutu_a, kutu_b):
    """ İki (x1,y1,x2,y2) kutusu arasındaki IoU (kesişim/birleşim) oranını hesaplar """
    ax1, ay1, ax2, ay2 = kutu_a
    bx1, by1, bx2, by2 = kutu_b

    kesisim_x1, kesisim_y1 = max(ax1, bx1), max(ay1, by1)
    kesisim_x2, kesisim_y2 = min(ax2, bx2), min(ay2, by2)

    kesisim_w = max(0, kesisim_x2 - kesisim_x1)
    kesisim_h = max(0, kesisim_y2 - kesisim_y1)
    kesisim_alan = kesisim_w * kesisim_h

    a_alan = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    b_alan = max(0, bx2 - bx1) * max(0, by2 - by1)
    birlesim_alan = a_alan + b_alan - kesisim_alan

    if birlesim_alan <= 0:
        return 0.0
    return kesisim_alan / birlesim_alan


def gorseli_base64_kodla(gorsel_bgr, jpeg_kalite: int = 85):
    """
    Bir OpenCV (BGR, numpy) görselini JPEG'e sıkıştırıp base64 string'e
    çevirir. .NET API'sine gerçek görseli (sadece metadata değil) taşımak
    için kullanılır. Encode başarısız olursa None döner (backend gönderimini
    engellemesin diye exception fırlatmaz).
    """
    try:
        basarili, buffer = cv2.imencode(".jpg", gorsel_bgr, [cv2.IMWRITE_JPEG_QUALITY, jpeg_kalite])
        if not basarili:
            return None
        return base64.b64encode(buffer).decode("utf-8")
    except Exception as e:
        print(f"⚠️ Görsel base64'e çevrilemedi: {e}")
        return None


def send_plate_to_dotnet_sync(paket: PlakaVeriPaketi):
    """ Arka plan thread'lerinden .NET API'sine güvenli ve senkron veri yollayan webhook """
    try:
        print(f"🔗 [.NET POST] Gönderilen plaka: {paket.plaka_metni}")
        # ⏱️ Timeout'u artırdık: base64 görsel gövdeye eklenince payload
        # büyüyor (JPEG ~85 kalite + orta boy crop genelde birkaç yüz KB),
        # 2 saniyelik eski limit yavaş ağlarda gereksiz timeout'lara yol açabilir.
        response = requests.post(DOTNET_API_URL, json=paket.model_dump(), timeout=5.0)
        if response.status_code == 200:
            print(f"✅ .NET API veriyi aldı: Başarılı (200)")
        else:
            print(f"⚠️ .NET API beklenmeyen bir kod döndü: {response.status_code}")
    except Exception as exc:
        print(f"❌ .NET API'sine ulaşılamadı (Backend kapalı olabilir): {exc}")


# --- 📹 GERÇEK YAPAY ZEKA VE KAMERA AKIŞ MOTORU ---
def gercek_yolo_ocr_pipeline(kamera_id: int, depo_id: int, rtsp_url: str, yon: str = "bilinmiyor"):
    global son_yakalanan_goruntuler, son_okunan_plaka_global
    print(f"🔌 [{yon.upper()}] {rtsp_url} adresi için OpenCV video yakalayıcı hazırlanıyor...")

    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print(f"❌ Kamera akışı açılamadı! RTSP adresi yanlış veya ağda erişim yok: {rtsp_url}")
        return

    print(f"🎥 [{yon.upper()}] Kamera {kamera_id} akışı canlı olarak işleniyor...")

    son_okunan_plaka = ""
    son_gonderim_zamani = 0.0

    # ⏳ AKILLI ARAÇ/PLAKA TAMPON MEKANİZMASI DEĞİŞKENLERİ
    arac_algilandi_mi = False
    arac_baslangic_zamani = 0.0
    son_tespit_zamani = 0.0   # bu episode'da aracın EN SON görüldüğü an
    episode_arac_tipi = "bilinmiyor"  # 🚗 Bu episode'da tespit edilen araç tipi
    kare_havuzu = []
    episode_junk_kelimeleri = set()  # bu episode'da görülen, plaka olamayacak metin parçaları

    # 🚗 Artık sabit bir "2 saniye topla, işle" penceresi YOK. Bunun yerine
    # araç kadrajda kaldığı SÜRECE kare toplamaya devam ediyoruz; sadece
    # gerçekten ayrıldığında (ARAC_AYRILMA_BOSLUGU kadar tespitsiz kaldığında)
    # ya da güvenlik amaçlı azami süreyi (MAKS_TOPLAMA_SANIYESI) aştığında
    # işliyoruz. Böylece yavaş geçen / kadrajda 2 saniyeden uzun kalan TEK bir
    # araç, birbirinden habersiz birden fazla episode'a bölünüp "Araç
    # algılandı" mesajını ve OCR analizini gereksiz yere tekrar tekrar
    # tetiklemiyor.
    ARAC_AYRILMA_BOSLUGU = 1.2     # saniye — bu kadar süre tespit gelmezse araç gerçekten ayrılmış sayılır
    MAKS_TOPLAMA_SANIYESI = 6.0    # saniye — güvenlik amaçlı azami toplama süresi
    MIN_ISLEME_KARE_SAYISI = 2     # 🎯 Hareket eden araçlar için düşürüldü (eski: 3)

    # 🧊 COOLDOWN: Aynı konumdaki (örn. arka planda park halinde duran) bir
    # nesnenin art arda tekrar tekrar yanlış okunmasını engellemek için
    # son işlenen kutunun konumunu ve zamanını takip ediyoruz.
    son_islenen_kutu = None
    son_islenen_zaman = 0.0
    episod_kutu = None
    COOLDOWN_SANIYE = 8.0
    COOLDOWN_IOU_ESIGI = 0.7

    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"⚠️ Kamera {kamera_id} akışından kare alınamadı, 5 saniye sonra yeniden deniyor...")
            time.sleep(5)
            cap.open(rtsp_url)
            continue

        # 🚫 Kameranın en üst %12'lik filigran/yazı alanını siyaha boya
        # (kamera üstündeki "GEBZE GİRİŞ/ÇIKIŞ" yazısı, tarih/saat damgası
        # gibi sabit metinler YOLO ve OCR'ı hiç yanıltmasın diye)
        h_f, w_f = frame.shape[:2]
        frame[0:int(h_f * 0.12), 0:w_f] = (0, 0, 0)

        simdi = time.time()
        if simdi - son_gonderim_zamani < 0.05:  # 20 FPS sınırlayıcı
            continue
        son_gonderim_zamani = simdi

        ai_device = 0 if torch.cuda.is_available() else "cpu"
        
        # 🚗 ADIM 1: Önce araç/insan tespiti yap (filtreleme)
        detection_results = detection_model(frame, device=ai_device, verbose=False, conf=0.5)
        
        # İnsan algılandıysa bu kareyi atla (plaka işleme yapma)
        insan_bulundu = False
        arac_tipi = "bilinmiyor"
        arac_kutusu = None  # 🆕 plaka aramasını araç kutusuyla sınırlamak için

        for det_result in detection_results:
            det_boxes = det_result.boxes
            for det_box in det_boxes:
                class_id = int(det_box.cls[0])
                
                if class_id == 0:  # İnsan
                    insan_bulundu = True
                    break
                
                if class_id in COCO_CLASSES and class_id != 0:
                    arac_tipi = COCO_CLASSES[class_id]
                    axyxy = det_box.xyxy[0].cpu().numpy()
                    arac_kutusu = tuple(map(int, axyxy))
            
            if insan_bulundu:
                break
        
        # İnsan varsa bu kareyi işleme
        if insan_bulundu:
            continue
        
        # 🔍 ADIM 2: Şimdi plaka tespiti yap
        # 🆕 İKİ AŞAMALI TESPİT: Eğer bir araç kutusu bulunduysa, plaka
        # dedektörünü TÜM kareye değil, araç kutusuna (biraz paylı) kısıtlı
        # bir bölgede çalıştırıyoruz. Bu sayede:
        #  1) Plaka, bakılan alana oranla çok daha büyük olur -> OCR kalitesi artar
        #  2) Arka plandaki sabit tabela/filigran gibi false-positive'ler
        #     büyük ölçüde elenir (araç kutusunun dışında kalıyorlar)
        # Araç kutusu yoksa (COCO tespiti bu karede başarısızsa) eskisi gibi
        # tüm karede aramaya devam ediyoruz (fallback) — bu davranışı bozmuyoruz.
        arama_karesi = frame
        ofset_x, ofset_y = 0, 0
        if arac_kutusu is not None:
            ax1, ay1, ax2, ay2 = arac_kutusu
            pay = int((ay2 - ay1) * 0.15)
            ax1 = max(0, ax1 - pay)
            ay1 = max(0, ay1 - pay)
            ax2 = min(frame.shape[1], ax2 + pay)
            ay2 = min(frame.shape[0], ay2 + pay)
            if ax2 > ax1 and ay2 > ay1:
                arama_karesi = frame[ay1:ay2, ax1:ax2]
                ofset_x, ofset_y = ax1, ay1

        results = model(arama_karesi, device=ai_device, verbose=False,
                         conf=PLAKA_CONF_ESIGI, imgsz=PLAKA_IMGSZ)

        plaka_bulundu_bu_karede = False
        en_iyi_kutu = None
        en_buyuk_alan = 0

        for result in results:
            boxes = result.boxes
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                # 🆕 Aramayı araç kutusuna kısıtladıysak, koordinatları tekrar
                # TAM KAREYE göre offsetliyoruz — sonrasındaki kırpma/kayıt
                # işlemleri hep tam kare üzerinden yapıldığı için bu şart.
                x1, y1, x2, y2 = map(int, xyxy)
                x1, y1, x2, y2 = x1 + ofset_x, y1 + ofset_y, x2 + ofset_x, y2 + ofset_y

                genislik = x2 - x1
                yukseklik = y2 - y1
                alan = genislik * yukseklik

                if genislik < 20 or yukseklik < 20:
                    continue

                plaka_bulundu_bu_karede = True
                if alan > en_buyuk_alan:
                    en_buyuk_alan = alan
                    # 📐 YOLO bounding box'ını genişlet (padding = bounding box yüksekliğinin %20'si)
                    bbox_yukseklik = y2 - y1
                    padding = int(bbox_yukseklik * 0.2)
                    x1_padded = max(0, x1 - padding)
                    y1_padded = max(0, y1 - padding)
                    x2_padded = min(frame.shape[1], x2 + padding)
                    y2_padded = min(frame.shape[0], y2 + padding)
                    en_iyi_kutu = (x1_padded, y1_padded, x2_padded, y2_padded)

        # 🚀 AKILLI TAMPON MANTIĞI
        if plaka_bulundu_bu_karede and en_iyi_kutu is not None:
            x1, y1, x2, y2 = en_iyi_kutu
            cropped_plate = frame[y1:y2, x1:x2]

            if cropped_plate.size > 0:
                if not arac_algilandi_mi:
                    # 🧊 Cooldown kontrolü: bu konum, kısa süre önce zaten
                    # işlediğimiz bir kutuyla büyük ölçüde örtüşüyor mu?
                    # (arka planda duran, sürekli "araç" olarak algılanan
                    # sabit bir nesneyi tekrar tekrar işlemeyi engeller)
                    simdiki_kutu = (x1, y1, x2, y2)
                    if (son_islenen_kutu is not None
                            and (time.time() - son_islenen_zaman) < COOLDOWN_SANIYE
                            and kutu_ortusme_orani(simdiki_kutu, son_islenen_kutu) > COOLDOWN_IOU_ESIGI):
                        continue  # aynı nesne muhtemelen hâlâ orada duruyor, atla

                    arac_algilandi_mi = True
                    arac_baslangic_zamani = time.time()
                    kare_havuzu = []
                    episode_junk_kelimeleri = set()
                    episode_arac_tipi = arac_tipi  # 🚗 Bu episode'daki araç tipini sakla
                    print(f"🚗 Araç algılandı ({arac_tipi}). Kadrajda kaldığı sürece kare toplanıyor...")

                # Her tespitte "son görülme zamanı"nı güncelliyoruz — bu,
                # aracın HÂLÂ kadrajda olduğunun kanıtı. Aynı araç 2
                # saniyeden uzun sürse bile bu sayede episode bölünmüyor.
                son_tespit_zamani = time.time()
                episod_kutu = (x1, y1, x2, y2)

                # 📸 Keskinlik filtresi: motion blur'lu kareleri atla
                kare_keskinligi = keskinlik_skoru(cropped_plate)
                if kare_keskinligi < 100:  # Çok bulanık → atla
                    print(f"   🏃 [Blur Filtresi] Kare çok bulanık (keskinlik={kare_keskinligi:.1f}), atlandı.")
                else:
                    kare_havuzu.append({
                        "gorsel": cropped_plate,
                        "alan": en_buyuk_alan,
                        "keskinlik": kare_keskinligi,
                        "tam_kare": frame.copy() if DEBUG_ORIJINAL_KARE_KAYDET else None,
                        "kutu": (x1, y1, x2, y2),
                    })

                # 🐞 Teşhis modu açıksa, YOLO'nun kırptığı HAM görüntüyü
                # (hiçbir işleme sokmadan) diske kaydet
                if DEBUG_KARE_KAYDET:
                    debug_dosya_adi = f"kam{kamera_id}_{int(time.time()*1000)}.jpg"
                    cv2.imwrite(os.path.join(DEBUG_KARE_DIR, debug_dosya_adi), cropped_plate)

        # 🏁 EPISODE SONLANDIRMA: araç ya gerçekten kadrajdan ayrıldı
        # (ARAC_AYRILMA_BOSLUGU kadar süredir hiç tespit yok) ya da güvenlik
        # amaçlı azami toplama süresi doldu. İkisi de olmadan episode'u KESİP
        # ATMIYORUZ artık — aynı araç kadrajda kaldığı sürece üstteki blok
        # kare toplamaya devam ediyor.
        if arac_algilandi_mi:
            simdi2 = time.time()
            arac_ayrildi_mi = (simdi2 - son_tespit_zamani) >= ARAC_AYRILMA_BOSLUGU
            zaman_asimi_mi = (simdi2 - arac_baslangic_zamani) >= MAKS_TOPLAMA_SANIYESI

            if arac_ayrildi_mi or zaman_asimi_mi:
                sebep = "araç kadrajdan ayrıldı" if arac_ayrildi_mi else "azami toplama süresi doldu (araç hâlâ kadrajda olabilir)"
                print(f"⏱️ Toplama tamamlandı ({sebep}). Toplam {len(kare_havuzu)} kare arasından en net olanı analiz ediliyor...")

                if len(kare_havuzu) < MIN_ISLEME_KARE_SAYISI:
                    print(f"⚠️ Sadece {len(kare_havuzu)} kare toplandı (min {MIN_ISLEME_KARE_SAYISI}) — muhtemelen anlık bir yanlış algılama, OCR'a hiç sokulmuyor.")
                else:
                    # 🎯 Sadece boyuta göre değil, boyut + netlik (Laplacian varyansı)
                    # karışık skoruna göre en iyi kareleri seçiyoruz. Bulanık/hareket
                    # blur'lu büyük bir kare, net ama biraz küçük bir kareden daha
                    # kötü olabilir.
                    max_alan = max(k["alan"] for k in kare_havuzu) or 1
                    max_keskinlik = max(k["keskinlik"] for k in kare_havuzu) or 1
                    for k in kare_havuzu:
                        k["skor"] = 0.5 * (k["alan"] / max_alan) + 0.5 * (k["keskinlik"] / max_keskinlik)

                    kare_havuzu.sort(key=lambda x: x["skor"], reverse=True)
                    EN_IYI_KARE_SAYISI = 5
                    en_iyi_kareler = [item["gorsel"] for item in kare_havuzu[:EN_IYI_KARE_SAYISI]]

                    # 🐞 Orijinal kare teşhis modu: bu episode'daki en yüksek skorlu
                    # karenin TAM görüntüsünü, YOLO'nun çizdiği kutuyla birlikte
                    # kaydediyoruz. Amaç: kameranın gerçekte neyi "plaka" sandığını
                    # (sabit tabela, filigran, kamyon üstü yazı vb.) gözle görmek.
                    if DEBUG_ORIJINAL_KARE_KAYDET:
                        en_iyi_ham = kare_havuzu[0]
                        tam_kare_kopya = en_iyi_ham.get("tam_kare")
                        if tam_kare_kopya is not None:
                            bx1, by1, bx2, by2 = en_iyi_ham["kutu"]
                            cv2.rectangle(tam_kare_kopya, (bx1, by1), (bx2, by2), (0, 255, 0), 3)
                            debug_dosya_adi = f"kam{kamera_id}_{yon}_{int(time.time()*1000)}.jpg"
                            cv2.imwrite(os.path.join(DEBUG_ORIJINAL_KARE_DIR, debug_dosya_adi), tam_kare_kopya)
                            print(f"🐞 [Orijinal Kare] Tam kare (YOLO kutusu çizili) kaydedildi: {debug_dosya_adi}")

                    # Her kareden en iyi tekil adayı topluyoruz; sonra hepsini
                    # birlikte karakter-bazlı oylamaya (konsensüs) sokacağız
                    tum_adaylar = []
                    # 🖼️ Backend'e gönderilecek "kanıt" görseli: en yüksek
                    # skorlu (en net + en büyük) kırpılmış plaka karesi.
                    # Bunu en başta, kare_havuzu sıralı haliyle sabitliyoruz;
                    # OCR hangi kareden başarılı sonuç üretirse üretsin,
                    # backend'e giden görsel hep episode'un en iyi karesidir.
                    en_iyi_gonderim_goruntusu = kare_havuzu[0]["gorsel"] if kare_havuzu else None

                    for idx, best_crop in enumerate(en_iyi_kareler):
                        # Teşhis için son görsel referansını, bu KAMERAYA özel olarak güncelliyoruz
                        son_yakalanan_goruntuler[kamera_id] = best_crop.copy()

                        plaka, ortalama_guven, ham_parcalar = kareyi_oku(best_crop)

                        if not ham_parcalar:
                            print(f"🔍 [Kare {idx+1} Analizi] Hiçbir varyantta metin okunamadı.")
                        else:
                            for (v_idx, text, prob) in ham_parcalar:
                                print(f"🔍 [Kare {idx+1} / Varyant {v_idx+1} Ham Parça] '{text}' (Güven: {prob:.2f})")

                                # 🧠 Bu parça hiçbir zaman tek başına geçerli bir
                                # plaka formatı oluşturmuyor ama harf içeriyor ve
                                # yeterince uzun — muhtemelen sabit bir tabela/
                                # filigran/çıkartma. Otomatik kara liste adayı
                                # olarak not ediyoruz (episode başına 1 kere sayılır).
                                temiz_kelime = plaka_temizle(text)
                                if (temiz_kelime and len(temiz_kelime) >= 4
                                        and any(karakter.isalpha() for karakter in temiz_kelime)
                                        and not plaka_format_gecerli_mi(temiz_kelime)):
                                    episode_junk_kelimeleri.add(temiz_kelime)

                        if plaka is None:
                            print(f"⚠️ [Kare {idx+1}] Geçerli formatta plaka bulunamadı.")
                            continue

                        print(f"   -> [Kare {idx+1}] Aday: '{plaka}' (Ort. Güven: {ortalama_guven:.2f})")
                        tum_adaylar.append((plaka, ortalama_guven))

                    # 🧠 Bu episode'da tekrar eden "sabit metin" adaylarını
                    # otomatik kara liste sayacına işle (yeterince FARKLI
                    # araç geçişinde tekrar ederse otomatik olarak eklenir)
                    if episode_junk_kelimeleri:
                        episode_junk_kelimelerini_degerlendir(episode_junk_kelimeleri)

                    # 🗳️ Tüm karelerin adaylarını karakter-bazlı oylamayla birleştir
                    genel_en_iyi_plaka, genel_en_iyi_guven = oylama_ile_konsensus(tum_adaylar)

                    if genel_en_iyi_plaka is not None and len(tum_adaylar) > 1:
                        print(f"🗳️ [Konsensüs] {len(tum_adaylar)} aday arasından oylama sonucu: '{genel_en_iyi_plaka}' (Güven: {genel_en_iyi_guven:.2f})")

                    # 🧠 Hafıza düzeltmesi: bu okuma, daha önce güvenlik görevlisinin
                    # düzelttiği bilinen bir yanlış okumaya benziyor mu?
                    if genel_en_iyi_plaka is not None:
                        duzeltilmis_plaka, hafizadan_geldi_mi = hafizadan_duzelt(genel_en_iyi_plaka)
                        if hafizadan_geldi_mi and duzeltilmis_plaka != genel_en_iyi_plaka:
                            print(f"🧠 [HAFIZA DÜZELTMESİ] '{genel_en_iyi_plaka}' -> '{duzeltilmis_plaka}' (geçmiş bir düzeltmeye göre otomatik değiştirildi)")
                            genel_en_iyi_plaka = duzeltilmis_plaka
                            genel_en_iyi_guven = max(genel_en_iyi_guven, 0.90)

                    MIN_GUVEN_ESIGI = 0.35  # 📉 Biraz daha toleranslı (eski: 0.40)

                    if genel_en_iyi_plaka is None:
                        print("⚠️ Bu araç için hiçbir karede geçerli formatta plaka bulunamadı.")
                    elif genel_en_iyi_guven < MIN_GUVEN_ESIGI:
                        print(f"⚠️ En iyi aday '{genel_en_iyi_plaka}' düşük güven skoru yüzünden elendi ({genel_en_iyi_guven:.2f}).")
                    elif genel_en_iyi_plaka == son_okunan_plaka:
                        print(f"⚠️ [Filtre] '{genel_en_iyi_plaka}' az önce gönderildi, tekrar gönderilmiyor.")
                    else:
                        son_okunan_plaka = genel_en_iyi_plaka
                        son_okunan_plaka_global = genel_en_iyi_plaka
                        print(f"🎯 [{yon.upper()}] Doğrulanmış Plaka Okundu! -> {genel_en_iyi_plaka} (Ort. Güven: {genel_en_iyi_guven:.2f})")

                        # 🖼️ Kırpılmış plaka görselini (ve varsa kutu çizili tam
                        # kareyi) base64'e çevirip pakete ekliyoruz — .NET
                        # tarafı artık sadece metni değil, kanıt görselini de
                        # kaydedebilir/gösterebilir.
                        plaka_gorseli_b64 = None
                        if en_iyi_gonderim_goruntusu is not None:
                            plaka_gorseli_b64 = gorseli_base64_kodla(en_iyi_gonderim_goruntusu)

                        tam_kare_b64 = None
                        if DEBUG_ORIJINAL_KARE_KAYDET and kare_havuzu:
                            en_iyi_ham_tam = kare_havuzu[0].get("tam_kare")
                            if en_iyi_ham_tam is not None:
                                bx1, by1, bx2, by2 = kare_havuzu[0]["kutu"]
                                tam_kare_kopya2 = en_iyi_ham_tam.copy()
                                cv2.rectangle(tam_kare_kopya2, (bx1, by1), (bx2, by2), (0, 255, 0), 3)
                                tam_kare_b64 = gorseli_base64_kodla(tam_kare_kopya2)

                        veri_paketi = PlakaVeriPaketi(
                            kamera_id=kamera_id,
                            depo_id=depo_id,
                            yon=yon,
                            plaka_metni=genel_en_iyi_plaka,
                            arac_tipi=episode_arac_tipi,  # 🚗 Araç tipi ekle
                            guven_skoru=float(genel_en_iyi_guven),
                            tarih_saat=datetime.utcnow().isoformat(),
                            plaka_gorseli_base64=plaka_gorseli_b64,
                            tam_kare_gorseli_base64=tam_kare_b64,
                        )

                        send_plate_to_dotnet_sync(veri_paketi)

                # 🧊 Bu episode'u işledik (başarılı olsun olmasın) — konumunu ve
                # zamanını cooldown için kaydediyoruz
                if episod_kutu is not None:
                    son_islenen_kutu = episod_kutu
                    son_islenen_zaman = time.time()

                arac_algilandi_mi = False
                kare_havuzu = []
                episod_kutu = None
                episode_junk_kelimeleri = set()

    cap.release()


# --- 🎛️ ENDPOINTS ---
@app.get("/")
async def root():
    return {"durum": "AI Servisi Canlı Akış Modunda Ayakta"}


@app.post("/api/v1/plaka/duzelt")
async def plaka_duzelt(istek: PlakaDuzeltmeIstek):
    """
    Güvenlik görevlisi hatalı okunan plakayı arayüzden düzelttiğinde tetiklenecek webhook.
    1) Son yakalanan görseli doğru etiketle diske kaydeder (ileride gerçek model
       fine-tuning'i için biriktirilen veri seti).
    2) Düzeltmeyi hafıza dosyasına yazar; böylece aynı/benzer yanlış okuma
       gelecekte canlı akışta otomatik olarak düzeltilir (bkz. hafizadan_duzelt).
    """
    global son_yakalanan_goruntuler, DUZELTME_HAFIZASI
    try:
        gorsel = son_yakalanan_goruntuler.get(istek.kamera_id)
        if gorsel is None:
            raise HTTPException(
                status_code=400,
                detail=f"Kamera {istek.kamera_id} için diske yazılacak son aktif görsel bulunamadı."
            )

        yanlis_plaka_temiz = plaka_temizle(istek.yanlis_plaka)
        dogru_plaka_temiz = plaka_temizle(istek.dogru_plaka)

        dosya_adi = f"kam{istek.kamera_id}_{dogru_plaka_temiz}_{int(time.time())}.jpg"
        hedef_yol = os.path.join(RETRAIN_DIR, dosya_adi)

        cv2.imwrite(hedef_yol, gorsel)
        print(f"💾 [VERİ SETİ] Görsel kaydedildi: {hedef_yol} ({yanlis_plaka_temiz} -> {dogru_plaka_temiz})")

        # 🧠 Self-learning: hafızaya ekle ve kalıcı dosyaya yaz
        DUZELTME_HAFIZASI[yanlis_plaka_temiz] = dogru_plaka_temiz
        duzeltme_hafizasini_kaydet(DUZELTME_HAFIZASI)
        print(f"🧠 [ÖĞRENME] Hafızaya eklendi: '{yanlis_plaka_temiz}' -> '{dogru_plaka_temiz}' (toplam {len(DUZELTME_HAFIZASI)} kayıt)")

        return {
            "durum": "basarili",
            "mesaj": f"Görsel '{dogru_plaka_temiz}' etiketiyle veri setine eklendi ve düzeltme hafızaya kaydedildi.",
            "toplam_hafiza_kaydi": len(DUZELTME_HAFIZASI)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/plaka/duzeltme-hafizasi")
async def duzeltme_hafizasi_goruntule():
    """ Öğrenilmiş düzeltmelerin tamamını döner (izleme/teşhis amaçlı) """
    return {
        "toplam_kayit": len(DUZELTME_HAFIZASI),
        "hafiza": DUZELTME_HAFIZASI
    }


@app.delete("/api/v1/plaka/duzeltme-hafizasi/{yanlis_plaka}")
async def duzeltme_hafizasindan_sil(yanlis_plaka: str):
    """ Hatalı girilmiş bir düzeltme kaydını hafızadan siler """
    global DUZELTME_HAFIZASI
    yanlis_plaka_temiz = plaka_temizle(yanlis_plaka)
    if yanlis_plaka_temiz not in DUZELTME_HAFIZASI:
        raise HTTPException(status_code=404, detail="Bu plaka hafızada bulunamadı.")
    silinen = DUZELTME_HAFIZASI.pop(yanlis_plaka_temiz)
    duzeltme_hafizasini_kaydet(DUZELTME_HAFIZASI)
    return {"durum": "basarili", "mesaj": f"'{yanlis_plaka_temiz} -> {silinen}' kaydı silindi."}


@app.get("/api/v1/plaka/kara-liste")
async def kara_liste_goruntule():
    """
    Elle tanımlanmış SABİT kara liste ile, sistemin kendiliğinden
    öğrendiği OTOMATİK kara listeyi ve hâlâ eşiği aşmamış (takip
    edilmekte olan) adayların sayaçlarını döner.
    """
    return {
        "sabit_kara_liste": sorted(YASAKLI_KELIMELER),
        "otomatik_kara_liste": sorted(OTO_YASAKLI_KELIMELER),
        "takip_edilen_adaylar": OTO_KELIME_SAYAC,
        "esik": OTO_KARA_LISTE_ESIK,
    }


@app.post("/api/v1/plaka/kara-liste/{kelime}")
async def kara_listeye_manuel_ekle(kelime: str):
    """
    Eşiğin dolmasını beklemeden bir kelimeyi anında otomatik kara listeye
    ekler (örn. teşhis loglarında yeni bir sabit tabela/çıkartma yazısı
    fark ettiğinde hemen devreye alabilmen için).
    """
    global OTO_YASAKLI_KELIMELER
    temiz_kelime = plaka_temizle(kelime)
    if not temiz_kelime or len(temiz_kelime) < 2:
        raise HTTPException(status_code=400, detail="Geçerli bir kelime girmelisin.")
    OTO_YASAKLI_KELIMELER.add(temiz_kelime)
    OTO_KELIME_SAYAC[temiz_kelime] = OTO_KARA_LISTE_ESIK
    oto_kara_listesini_kaydet()
    return {"durum": "basarili", "mesaj": f"'{temiz_kelime}' kara listeye eklendi.", "toplam_otomatik": len(OTO_YASAKLI_KELIMELER)}


@app.delete("/api/v1/plaka/kara-liste/{kelime}")
async def kara_listeden_sil(kelime: str):
    """
    Otomatik öğrenilen kara listeden bir kelimeyi siler (yanlışlıkla
    eklenmiş bir kelimeyi düzeltmek için). Elle yazılmış SABİT kara
    liste (YASAKLI_KELIMELER) koddan geldiği için buradan silinemez —
    onu değiştirmek için kod güncellemesi gerekir.
    """
    global OTO_YASAKLI_KELIMELER, OTO_KELIME_SAYAC
    temiz_kelime = plaka_temizle(kelime)
    if temiz_kelime in YASAKLI_KELIMELER:
        raise HTTPException(status_code=400, detail="Bu kelime kodda sabit olarak tanımlı, API üzerinden silinemez.")
    if temiz_kelime not in OTO_YASAKLI_KELIMELER:
        raise HTTPException(status_code=404, detail="Bu kelime otomatik kara listede bulunamadı.")
    OTO_YASAKLI_KELIMELER.discard(temiz_kelime)
    OTO_KELIME_SAYAC.pop(temiz_kelime, None)
    oto_kara_listesini_kaydet()
    return {"durum": "basarili", "mesaj": f"'{temiz_kelime}' otomatik kara listeden silindi."}


@app.post("/api/v1/kamera/baslat")
async def kamera_baslat(istek: KameraIstek, background_tasks: BackgroundTasks):
    """
    Manuel/ad-hoc kamera başlatma. Gebze giriş/çıkış kameraları için buna
    gerek YOK — onlar servis ayağa kalktığında otomatik başlıyor
    (bkz. @app.on_event("startup")). Bu endpoint yeni/test kameraları için.
    """
    try:
        if not istek.rtsp_url or istek.rtsp_url == "string":
            raise HTTPException(status_code=400, detail="Geçerli bir RTSP URL'si girmelisin!")

        print(f"🎥 Kamera {istek.kamera_id} için gerçek akış başlatma emri alındı.")
        background_tasks.add_task(
            gercek_yolo_ocr_pipeline,
            istek.kamera_id, istek.depo_id, istek.rtsp_url, istek.yon
        )

        return {
            "durum": "basarili",
            "mesaj": f"{istek.kamera_id} numaralı kamera için GERÇEK AI Pipeline arka planda tetiklendi."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/kamera/durum")
async def kamera_durum():
    """ Otomatik başlatılan sabit kameraların listesini ve durumunu döner """
    return {
        "otomatik_baslatilan_kameralar": [
            {
                "kamera_id": k["kamera_id"],
                "isim": k["isim"],
                "yon": k["yon"],
                "depo_id": k["depo_id"],
            }
            for k in GEBZE_KAMERALARI
        ]
    }


# 🚀 --- OTOMATİK BAŞLATMA ---
# Servis (uvicorn) ayağa kalktığı anda, Swagger'dan elle "kamera/baslat"
# çağırmaya gerek kalmadan Gebze giriş ve çıkış kameraları otomatik olarak
# arka planda izlemeye başlar.
@app.on_event("startup")
async def kameralari_otomatik_baslat():
    for kamera in GEBZE_KAMERALARI:
        print(f"🚀 [OTOMATİK BAŞLATMA] {kamera['isim']} (id={kamera['kamera_id']}, yön={kamera['yon']}) başlatılıyor...")
        thread = threading.Thread(
            target=gercek_yolo_ocr_pipeline,
            args=(kamera["kamera_id"], kamera["depo_id"], kamera["rtsp_url"], kamera["yon"]),
            daemon=True,
            name=f"kamera-{kamera['kamera_id']}-{kamera['yon']}"
        )
        thread.start()


if __name__ == "__main__":
    # ⚠️ reload=True KASTEN KALDIRILDI: Bu sadece geliştirme (dev) ortamı
    # içindir. Uygulama çalışırken /app/dataset/retrain ve /app/debug_kareler
    # gibi klasörlere dosya yazıyoruz — reload=True bunu "kod değişti" sanıp
    # uygulamayı sürekli yeniden başlatır ve arka plandaki kamera thread'lerini
    # öldürür. Üretimde (production) reload KAPALI olmalı.
    uvicorn.run("main:app", host="0.0.0.0", port=8000)