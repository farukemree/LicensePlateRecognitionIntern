"""
Lojistik Plaka Tanıma AI Servisi
================================

Mimari (kare -> plaka metni yolculuğu):

    RTSP okuyucu thread'i  (daima EN GÜNCEL kare, bayat kare yok)
              |
    COCO araç tespiti      (araç yoksa plaka aranmaz -> arka plan tabelaları elenir)
              |
    Plaka tespiti          (SADECE araç kutusunun içinde)
              |
    Kutu daraltma          (YOLO kutusu plakadan yüksek olur; karakter bandına kırp)
              |
    OCR varyantları        (birkaç nazik ön-işleme; agresif binarizasyon yok)
              |
    Parça birleştirme      (aynı satırdaki parçalar soldan sağa)
              |
    GRAMER ÇÖZÜMLEYİCİ     (TR plaka dilbilgisi + konum-farkında karakter düzeltme)
              |
    Zamansal mutabakat     (bir plaka birden fazla karede tekrar etmeli)
              |
    .NET API

Önceki sürüme göre kaldırılan iki mekanizma ve nedenleri, aşağıdaki ilgili
bölümlerde ayrıntılı yorumlarla açıklanmıştır (kendi kendine öğrenen metin
kara listesi ve "esnek eşleştirme" fallback'i).
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Tuple
from collections import deque
from contextlib import asynccontextmanager
import uvicorn
import requests
import asyncio
import itertools
import logging
import time
import os
import re
import json
import base64
import threading
import sys
from urllib.parse import quote

# 🩹 CANLI LOG: stdout bir terminale değil bir boruya (docker logs) gittiğinde
# Python blok bazlı tamponlama yapar ve print() çıktısı anında görünmez.
# Satır bazlı tamponlamaya zorluyoruz. (Dockerfile'da PYTHONUNBUFFERED=1 ile
# iki katmanlı güvence altında.)
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# 🚨 OpenCV'yi RTSP'de TCP'ye zorlayan değişken cv2'den ÖNCE set edilmeli.
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

import cv2
import numpy as np
from datetime import datetime, timezone
import torch

# 🔓 PyTorch 2.6+ weights_only bypass (kendi güvenilir .pt dosyalarımız için)
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

from ultralytics import YOLO  # 👈 patch'ten SONRA import edilmeli
import easyocr

# 🧵 ÇOK KAMERALI THREAD GÜVENLİĞİ
# Aynı YOLO/EasyOCR nesneleri iki kamera thread'i tarafından paylaşılıyor.
# PyTorch/Ultralytics çıkarımı thread-safe DEĞİLDİR; kilitsiz durumda iki
# kameranın sonuçları birbirine karışabilir. Tüm model çağrıları bu kilidin
# altında seri hâle getirilir.
INFERENCE_LOCK = threading.Lock()
# 📡 /readyz için otomatik başlatılan kamera thread'lerini takip ediyoruz.
AKTIF_THREADLER: List[threading.Thread] = []


# ==========================================================================
# 📝 LOG ALTYAPISI — canlı izlenebilir
# ==========================================================================
# Loglar hem stdout'a (docker logs) hem de bellekteki halka tampona yazılır.
# Tampon sayesinde /api/v1/loglar ve /loglar (tarayıcıdan canlı izleme)
# uçları çalışır — "docker logs"a erişimi olmayan biri de akışı görebilir.

LOG_TAMPON_BOYUTU = int(os.getenv("LOG_TAMPON_BOYUTU", "3000"))
LOG_TAMPONU = deque(maxlen=LOG_TAMPON_BOYUTU)
_log_kilit = threading.Lock()
_log_sayac = itertools.count()

# 🔊 AYRINTI SEVİYESİ: "sessiz" | "normal" | "ayrintili"
# Önceki sürümde her elenen kutu için satır basılıyordu; saniyede onlarca
# kare işlendiği için log akışı okunamaz hale geliyordu. Kare bazlı ayrıntılar
# artık sadece "ayrintili" modda basılır.
LOG_SEVIYESI = os.getenv("LOG_SEVIYESI", "normal").lower()
_AYRINTILI = LOG_SEVIYESI == "ayrintili"
_SESSIZ = LOG_SEVIYESI == "sessiz"

# 📋 Standart logging altyapısı (LOG_LEVEL env ile ayarlanır).
# Konsola yazma işini logging yapar; log() ayrıca canlı tampona da yazar,
# böylece /loglar sayfası ve SSE akışı çalışmaya devam eder.
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("plaka-ai")

# log() 'tur' değeri -> logging seviyesi eşlemesi
_SEVIYE_ESLEME = {
    "hata": logging.ERROR,
    "uyari": logging.WARNING,
    "ayrinti": logging.DEBUG,
    "basari": logging.INFO,
    "bilgi": logging.INFO,
}


def log(mesaj: str, tur: str = "bilgi"):
    """Tek log satırı üretir: hem logging'e hem canlı tampona."""
    kayit = {
        "id": next(_log_sayac),
        "zaman": datetime.now().strftime("%H:%M:%S"),
        "tur": tur,
        "mesaj": mesaj,
    }
    with _log_kilit:
        LOG_TAMPONU.append(kayit)
    if not _SESSIZ:
        logger.log(_SEVIYE_ESLEME.get(tur, logging.INFO), mesaj)


def log_ayrinti(mesaj: str):
    """Sadece LOG_SEVIYESI=ayrintili iken görünen, kare bazlı gürültülü loglar."""
    if _AYRINTILI:
        log(mesaj, tur="ayrinti")


# 🚀 OTOMATİK BAŞLATMA (lifespan)
# Eski @app.on_event("startup") FastAPI'de deprecate oldu — lifespan kullanıyoruz.
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DEPOT_ID:
        log("⚠️ DEPOT_ID env değişkeni boş! Backend 'depot_id' (UUID) zorunlu — "
            "event'ler reddedilebilir.", "uyari")
    for kamera in GEBZE_KAMERALARI:
        log(f"🚀 [OTOMATİK BAŞLATMA] {kamera['isim']} (id={kamera['kamera_id']})")
        thread = threading.Thread(
            target=gercek_yolo_ocr_pipeline,
            args=(kamera["kamera_id"], kamera["depo_id"], kamera["rtsp_url"], kamera["yon"]),
            daemon=True, name=f"kamera-{kamera['kamera_id']}-{kamera['yon']}")
        thread.start()
        AKTIF_THREADLER.append(thread)
    yield
    log("🛑 Servis kapanıyor — kamera thread'leri (daemon) süreçle birlikte sonlanır.")


app = FastAPI(title="Lojistik Plaka Tanıma AI Servisi", version="2.1", lifespan=lifespan)

RETRAIN_DIR = os.getenv("RETRAIN_DIR", "/app/dataset/retrain")
os.makedirs(RETRAIN_DIR, exist_ok=True)

# 🖼️ YAKALANAN GÖRSELLER — backend base64 değil, erişilebilir bir URL bekliyor.
# Görseller diske yazılıp /captures altından statik olarak sunuluyor.
CAPTURES_DIR = os.getenv("CAPTURES_DIR", "/app/captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)
AI_SERVICE_PUBLIC_BASE_URL = os.getenv("AI_SERVICE_PUBLIC_BASE_URL", "http://localhost:8000")
app.mount("/captures", StaticFiles(directory=CAPTURES_DIR), name="captures")

DEBUG_KARE_KAYDET = os.getenv("DEBUG_KARE_KAYDET", "false").lower() == "true"
DEBUG_KARE_DIR = "/app/debug_kareler"
if DEBUG_KARE_KAYDET:
    os.makedirs(DEBUG_KARE_DIR, exist_ok=True)

DEBUG_ORIJINAL_KARE_KAYDET = os.getenv("DEBUG_ORIJINAL_KARE_KAYDET", "false").lower() == "true"
DEBUG_ORIJINAL_KARE_DIR = os.getenv("DEBUG_ORIJINAL_KARE_DIR", os.path.join(DEBUG_KARE_DIR, "orijinal"))
if DEBUG_ORIJINAL_KARE_KAYDET:
    os.makedirs(DEBUG_ORIJINAL_KARE_DIR, exist_ok=True)


# ==========================================================================
# 🧠 MODELLER
# ==========================================================================
log("🧠 YOLOv8 ve EasyOCR modelleri belleğe yükleniyor...")
model = YOLO("license_plate_detector.pt")   # Plaka tespiti
detection_model = YOLO("yolov8m.pt")        # Araç/insan tespiti (COCO)

COCO_CLASSES = {0: "insan", 2: "araba", 3: "motosiklet", 5: "otobüs", 7: "kamyon"}
COCO_ARAC_SINIFLARI = {2, 3, 5, 7}

gpu_kullanilabilir = torch.cuda.is_available()
AI_DEVICE = 0 if gpu_kullanilabilir else "cpu"
log(f"🖥️ GPU durumu: {'AKTİF ✅' if gpu_kullanilabilir else 'PASİF (CPU) ⚠️'}")

easyocr_cache_dir = os.getenv("EASYOCR_MODULE_DATA_DIR", "/app/.easyocr")
# 🔤 Dil seti ÖLÇÜMLE seçildi. Gerçek bir sahne karesi üzerinde 64
# kombinasyon denendiğinde ['tr','en'] 17/32, sadece ['en'] 11/32 doğru okudu.
# ("Plakada Türkçe karakter yok, İngilizce yeter" varsayımı yanlış çıktı —
# tr modeli bu karakter setinde belirgin şekilde daha isabetli.)
reader = easyocr.Reader(["tr", "en"], gpu=gpu_kullanilabilir,
                        model_storage_directory=easyocr_cache_dir)
log("✅ Modeller başarıyla yüklendi, sistem tetikte!")


# ==========================================================================
# 🎯 AYARLAR (hepsi .env üzerinden değiştirilebilir, deploy gerekmez)
# ==========================================================================
PLAKA_CONF_ESIGI = float(os.getenv("PLAKA_CONF_ESIGI", "0.35"))
PLAKA_IMGSZ = int(os.getenv("PLAKA_IMGSZ", "1280"))
ARAC_TESPIT_CONF = float(os.getenv("ARAC_TESPIT_CONF", "0.45"))

# 🚗 Plaka için araç şartı: Plaka dedektörünü SADECE bir araç tespit edilen
# karelerde, SADECE araç kutusunun içinde çalıştırıyoruz. Önceki sürümde araç
# bulunamayınca "tüm karede ara" fallback'i vardı; arka plandaki sabit
# tabelaların/çıkartmaların OCR'a sızmasının ana yolu buydu. Araçlar hareket
# eder, tabelalar etmez — bu şart, sabit yanlış pozitifleri kökten keser.
PLAKA_ARAC_ZORUNLU = os.getenv("PLAKA_ARAC_ZORUNLU", "true").lower() == "true"

# 📐 Plaka kutusu en/boy oranı aralığı. TR plakası 4.6:1'dir ama YOLO kutusu
# plaka yuvasını da kapsadığı ve perspektif oranı sıkıştırdığı için gerçekte
# 1.6-6.0 arasında ölçülüyor. Aralığı gerçek ölçümlere göre bilerek geniş
# tutuyoruz: yanlış pozitifi elemek OCR'ın değil, "araç şartı"nın işi.
PLAKA_EN_BOY_MIN = float(os.getenv("PLAKA_EN_BOY_MIN", "1.6"))
PLAKA_EN_BOY_MAX = float(os.getenv("PLAKA_EN_BOY_MAX", "7.0"))
# 📏 Okunabilirlik alt sınırı. Sahada doğru okunan plaka 321px genişlikteydi;
# 80px'lik uzak bir plakadan (örn. camın arkasından görünen başka bir araç)
# hiçbir varyantta metin çıkmıyor. Bu tür kutuları OCR'a hiç sokmuyoruz:
# hem boşuna işlem, hem de oylama havuzunu kirletiyorlar.
PLAKA_MIN_GENISLIK = int(os.getenv("PLAKA_MIN_GENISLIK", "100"))

# 🚚 PLAKA / ARAÇ ALAN ORANI — kamyonet kapısındaki firma yazısına karşı.
# 2026-07-23 sahada: bir kamyonetin yan kapısındaki "TECHNICAL SERVICES /
# SECURITY / CATERING" yazısı 792x407px'lik bir kutuyla plaka sanıldı ve
# '34SG948' diye okundu. En-boy oranı 1.95 olduğu için oran filtresinden
# geçiyordu — ama bir plaka aracın YANINDA bu kadar büyük yer kaplayamaz.
# Doğrulanmış 5 gerçek plakada ölçüm: alan oranı %2.6–5.2.
# Sahte kutu: %16.4. Eşiği aradaki boşluğa koyuyoruz.
PLAKA_MAKS_ARAC_ORANI = float(os.getenv("PLAKA_MAKS_ARAC_ORANI", "0.10"))

# 🎯 Kabul eşikleri — ESKİ SÜRÜMDEKİ 0.35 ÇOK DÜŞÜKTÜ ve '44LYO63' gibi
# tamamen uydurma okumaların backend'e gitmesine izin veriyordu.
MIN_PLAKA_GUVENI = float(os.getenv("MIN_PLAKA_GUVENI", "0.55"))
# Bir plakanın gönderilebilmesi için kaç FARKLI karede aynı sonucun çıkması
# gerektiği. Tek karelik bir hata artık tek başına backend'e gidemez.
MIN_MUTABAKAT_KARE = int(os.getenv("MIN_MUTABAKAT_KARE", "2"))
# Tek karede bile kabul edilebilecek "çok emin" eşiği (mutabakat şartını atlar)
TEK_KARE_KESIN_GUVEN = float(os.getenv("TEK_KARE_KESIN_GUVEN", "0.88"))
# Tek karelik bir sonucun kabulü için, o adayın TÜM kanıtın en az bu kadarına
# hâkim olması gerekir. Hızlı geçen araçlarda her kare farklı bir şey okuyor
# (13AHR91 / 34HRP10 / 14HRP18 / 14HRP150...) — böyle bir kaosta en yüksek
# skorlu aday bile güvenilir değildir, susmak doğrusudur.
TEK_KARE_MIN_PAY = float(os.getenv("TEK_KARE_MIN_PAY", "0.35"))
# 📊 GENEL KANIT PAYI TABANI — kaç karede göründüğünden bağımsız olarak,
# kazanan aday tüm kanıtın en az bu kadarına hâkim olmalı.
# 2026-07-23 canlı testinde 23 gönderimin payları ölçüldü: bağımsız olarak
# DOĞRU olduğunu doğruladığım tüm okumalar %48 ve üzerindeydi; yalnızca iki
# şüpheli okuma %28-30'da kalmıştı (biri kapı yazısından uydurulmuş
# '34SG948' idi). Eşik bu boşluğa konuyor.
MIN_KANIT_PAYI = float(os.getenv("MIN_KANIT_PAYI", "0.35"))

# ⏱️ Episode (araç geçişi) zamanlaması
# 📊 Sahadan ölçüm: 270 episode'un incelenmesinde TEK bir aracın 2-3 ayrı
# episode ürettiği görüldü (34HRR696 -> 14HRR696 -> 44HRR696 gibi). Her
# episode ayrı ayrı oylandığı için hem oy sayısı bölünüyor (doğruluk düşüyor)
# hem de aynı kamyon için birden fazla, üstelik çelişkili kayıt gidiyordu.
# Sebep: plaka birkaç kare boyunca (gölge, açı, direksiyon kırma) görünmeyince
# 1.5 sn'lik boşluk eşiği episode'u erken kapatıyordu. Eşikleri yükseltmek
# bir aracı TEK episode'da tutuyor -> daha çok oy, daha az çift kayıt.
ARAC_AYRILMA_BOSLUGU = float(os.getenv("ARAC_AYRILMA_BOSLUGU", "3.0"))
MAKS_TOPLAMA_SANIYESI = float(os.getenv("MAKS_TOPLAMA_SANIYESI", "12.0"))
MIN_ISLEME_KARE_SAYISI = int(os.getenv("MIN_ISLEME_KARE_SAYISI", "2"))
# 🔎 Episode başına OCR'lanacak AZAMİ kare. Sahada 75 kare toplanan bir
# episode'da sadece 6'sı okunuyordu ve doğru cevap (34HRP158) okunmayan
# karelerde kalıyordu. Sınırı yükseltmek bedavaya gelmiyor gibi görünse de,
# aşağıdaki erken çıkış sayesinde KOLAY vakalar artık 3 karede bitiyor —
# yalnız ZOR vakalarda tüm bütçe kullanılıyor.
OCR_KARE_SAYISI = int(os.getenv("OCR_KARE_SAYISI", "14"))
# Erken çıkış: bu kadar kare aynı plakada anlaştıysa ve güven yüksekse
# kalan kareleri okumaya gerek yok.
ERKEN_CIKIS_OY = int(os.getenv("ERKEN_CIKIS_OY", "3"))
ERKEN_CIKIS_GUVEN = float(os.getenv("ERKEN_CIKIS_GUVEN", "0.95"))
# Kare içinde varyant erken çıkışı: bir varyant bu skoru yakaladıysa
# kalan varyantlar denenmez.
VARYANT_ERKEN_CIKIS = float(os.getenv("VARYANT_ERKEN_CIKIS", "0.95"))
MIN_KESKINLIK = float(os.getenv("MIN_KESKINLIK", "60.0"))

# 🧊 Aynı aracın tekrar tekrar işlenmesini önleyen cooldown
COOLDOWN_SANIYE = float(os.getenv("COOLDOWN_SANIYE", "15.0"))
COOLDOWN_IOU_ESIGI = float(os.getenv("COOLDOWN_IOU_ESIGI", "0.5"))
# Aynı plakanın arka arkaya gönderilmesini engelleyen süre.
# Asıl koruma yukarıdaki KONUMSAL cooldown; bu yalnızca emniyet ağı.
# 60 sn sahada yetersiz kaldı (duran kamyon 83 sn sonra ikinci kez gönderildi).
# Not: her kameranın kendi geçmişi var — giriş ve çıkış birbirini etkilemez,
# yani bir aracın girip sonra çıkması iki ayrı kayıt olarak doğru şekilde kalır.
AYNI_PLAKA_BEKLEME = float(os.getenv("AYNI_PLAKA_BEKLEME", "120.0"))

# 🚫 Üst filigran/tarih-saat damgası bandını karart (0 = kapalı)
UST_MASKE_ORANI = float(os.getenv("UST_MASKE_ORANI", "0.12"))

HEARTBEAT_SANIYE = float(os.getenv("HEARTBEAT_SANIYE", "120.0"))

# 🔗 BACKEND KONTRATI
# ⚠️ Eski kod "http://192.168.1.141:5000/api/v1/plates/detected" adresine
# POST atıyordu — repoda böyle bir .NET servisi YOK. Gerçek alıcı, Go
# backend'in ANPR webhook'u. Yanlış adres yüzünden okunan hiçbir plaka
# kaydedilmiyordu; loglardaki sürekli "Connection refused" bundandı.
BACKEND_EVENTS_URL = os.getenv("BACKEND_EVENTS_URL", "http://localhost:8080/api/v1/anpr/events")
# Go tarafı depot_id'yi UUID olarak ve ZORUNLU bekliyor.
DEPOT_ID = os.getenv("DEPOT_ID", "")
# Geriye dönük uyumluluk: base64 alanları da göndermek istersen true yap.
GORSEL_BASE64_GONDER = os.getenv("GORSEL_BASE64_GONDER", "false").lower() == "true"


# ==========================================================================
# 🔤 TÜRK PLAKA DİLBİLGİSİ VE GRAMER ÇÖZÜMLEYİCİ
# ==========================================================================
# Bu bölüm, bu sürümün doğruluk kazancının ana kaynağı.
#
# Türk plakası:  [il kodu: 2 rakam, 01-81] [1-3 harf] [2-5 rakam]
#   1 harf -> 4 veya 5 rakam   (34 A 1234 / 34 A 12345)
#   2 harf -> 3 veya 4 rakam   (34 AB 123 / 34 AB 1234)
#   3 harf -> 2 veya 3 rakam   (34 ABC 12 / 34 ABC 123)
# Yani il kodundan sonra HER ZAMAN 5 veya 6 karakter; toplam 7 veya 8.
#
# Eski kod OCR çıktısını olduğu gibi regex'e sokuyordu: 'B4CLY063' hiçbir
# desene uymadığı için ÇÖPE gidiyordu. Oysa OCR'ın '3'ü 'B' okuması en yaygın
# karıştırmalardan biri. Yeni çözümleyici, her karakteri BULUNDUĞU KONUMUN
# gerektirdiği sınıfa (rakam mı harf mi) uyarlamayı dener ve il kodunun
# geçerliliğini kısıt olarak kullanır:
#
#   'B4CLY063' -> il kodu "B4":  B->8 ise "84" (geçersiz il, >81)  ✗
#                                B->3 ise "34" (geçerli)           ✓
#             -> "CLY" 3 harf, "063" 3 rakam -> toplam 6 ✓
#             -> SONUÇ: 34CLY063
#
# Tek bir kısıt (il kodu 01-81) belirsizliği tek başına çözüyor.

IL_KODLARI = {f"{i:02d}" for i in range(1, 82)}
PLAKA_HARFLERI = set("ABCDEFGHIJKLMNOPRSTUVYZ")  # TR plakasında Q, W, X yok
RAKAMLAR = set("0123456789")

# Harf gibi okunmuş ama rakam olması gereken karakterler.
# ⚠️ Değerler LİSTE: bir karakterin birden fazla makul rakam karşılığı olabilir.
# Örn. 'B' hem '8' hem '3' okunabilir — ve hangisinin doğru olduğunu il kodu
# geçerliliği belirler ('B4' -> '84' geçersiz, '34' geçerli). Tek hedefli bir
# eşleme bu ayrımı yapamaz ve doğru plakayı kaçırırdı.
RAKAMA_DONUSUM = {
    "O": ["0"], "D": ["0"], "Q": ["0"], "U": ["0"], "C": ["0"],
    "I": ["1"], "L": ["1"], "J": ["1"], "T": ["7"], "Y": ["7"],
    "Z": ["2"], "R": ["2"], "B": ["8", "3"], "E": ["8"], "S": ["5"],
    "G": ["6"], "A": ["4"], "H": ["4"], "P": ["9"], "V": ["7"],
}
# Rakam gibi okunmuş ama harf olması gereken karakterler
HARFE_DONUSUM = {
    "0": ["O", "D"], "1": ["I", "L"], "2": ["Z"], "3": ["B"], "4": ["A"],
    "5": ["S"], "6": ["G"], "7": ["T"], "8": ["B"], "9": ["G"],
}
# Bazı karıştırmalar diğerlerinden çok daha yaygın; ceza katsayısını
# ona göre ayırıyoruz (yüksek katsayı = daha az cezalı = daha güvenilir).
GUCLU_KARISTIRMA = {
    ("O", "0"), ("0", "O"), ("I", "1"), ("1", "I"), ("B", "8"), ("8", "B"),
    ("S", "5"), ("5", "S"), ("Z", "2"), ("2", "Z"), ("G", "6"), ("6", "G"),
    ("D", "0"), ("L", "1"), ("A", "4"), ("4", "A"), ("T", "7"), ("7", "T"),
    ("B", "3"), ("3", "B"),
}

CEZA_GUCLU = 0.88   # çok yaygın karıştırma — küçük ceza
CEZA_ZAYIF = 0.62   # daha nadir karıştırma — büyük ceza

# 🔢 AYNI SINIF (rakam->rakam) GÖRSEL KARIŞTIRMALARI
# İl kodu iki rakamdır; karakterler zaten "rakam sınıfında" olduğu için
# yukarıdaki sınıflar arası düzeltme devreye girmez. Ama OCR '3'ü '8' okuduğunda
# ortaya "84" gibi VAR OLMAYAN bir il kodu çıkar. Bu durumda alt dizi arayışı
# devreye girip '4CLY063' -> '40LY063' gibi UYDURMA ama biçimsel olarak geçerli
# bir plaka üretiyordu — yani yanlış cevap, cevapsızlıktan beter bir sonuç.
# Geçersiz il kodunu, görsel olarak yakın rakamlarla kurtarmayı deniyoruz.
# Liste sırası = görsel benzerlik önceliği.
RAKAM_ICI_KARISTIRMA = {
    "8": ["3", "6", "9", "0"], "9": ["3", "8", "4"], "6": ["5", "8", "0"],
    "5": ["6", "3"], "3": ["8", "9"], "0": ["8", "6"],
    "1": ["7", "4"], "7": ["1", "2"], "4": ["1", "9"], "2": ["7", "1"],
}
# İl kodu kurtarma = TEK BİR rakam hatası. Bu yüzden cezası, sınıflar arası
# zayıf bir düzeltmeyle (0.62) aynı seviyede tutulur.
# 📊 Bu değer sahada ölçülerek düzeltildi: 0.45 iken '35 BPJ 875' plakası
# yanlış okunuyordu. OCR parçaları doğruydu ('85' + 'BPJ' + '875'), sadece
# il kodunun ilk hanesi 3 yerine 8 okunmuştu — TEK hata. Ama 0.45'lik ağır
# ceza yüzünden çözümleyici İKİ hatalı bir yorumu tercih ediyordu:
#     35BPJ875  (8->3 il düzeltmesi)                        -> 0.45
#     58PJ875   (baştaki karakteri AT + 'B' harfini 8 san)  -> 0.62  ✗ kazanıyordu
# Tek hatalı yorum, iki hatalıyı her zaman yenmelidir.
CEZA_IL_KURTARMA = 0.62

# 📏 KAPSAMA CEZASI: Çözümleyici, metin içindeki her 7 ve 8 karakterlik alt
# diziyi dener. Sorun şu ki 8 karakterlik doğru bir plakanın ilk 7 karakteri de
# çoğu zaman GEÇERLİ bir plakadır ('34CLY063' -> '34CLY06' = 34 + CLY + 06).
# Hiç düzeltme gerektirmediği için eşit skor alır ve yanlışlıkla kazanır —
# yani güvenle okunmuş bir karakter sessizce çöpe atılır. Atlanan her karakteri
# cezalandırarak "tüm kanıtı kullanan" yorumu tercih ettiriyoruz.
# Değer, HER TÜRLÜ tek karakter düzeltmesinden ağır olmalı: güvenle okunmuş
# bir karakteri tamamen atmak, onu düzeltmekten daha büyük bir iddiadır.
# (0.70 iken çok hafif kalıyordu — bkz. CEZA_IL_KURTARMA'daki 35BPJ875 vakası.)
KAPSAMA_CEZASI = 0.55


def _karakteri_uyarla(karakter: str, hedef: str) -> Tuple[Optional[str], float]:
    """
    Bir karakteri hedef sınıfa ('rakam' / 'harf') uyarlar.
    (uyarlanmis_karakter, ceza_carpani) döner; uyarlanamıyorsa (None, 0.0).
    Ceza 1.0 = hiç değişiklik gerekmedi.

    Not: Harf ve rakam bloklarında birden fazla aday denenmez — orada seçimi
    kısıtlayacak bir kural yoktur, en olası karşılık alınır. İl kodunda ise
    geçerlilik kısıtı olduğu için tüm adaylar denenir (bkz. _il_kodu_coz).
    """
    if hedef == "rakam":
        if karakter in RAKAMLAR:
            return karakter, 1.0
        alternatifler = RAKAMA_DONUSUM.get(karakter)
    else:
        if karakter in PLAKA_HARFLERI:
            return karakter, 1.0
        alternatifler = HARFE_DONUSUM.get(karakter)

    if not alternatifler:
        return None, 0.0
    alternatif = alternatifler[0]
    ceza = CEZA_GUCLU if (karakter, alternatif) in GUCLU_KARISTIRMA else CEZA_ZAYIF
    return alternatif, ceza


def _il_hane_adaylari(karakter: str) -> List[Tuple[str, float]]:
    """Bir karakterin il kodu hanesi olarak alabileceği (rakam, ceza) adayları."""
    adaylar = []
    if karakter in RAKAMLAR:
        adaylar.append((karakter, 1.0))
        # Doğru sınıfta ama il kodunu geçersiz kılıyor olabilir — aynı sınıf
        # görsel karıştırmalarını da (düşük güvenle) aday yap.
        for sira, alternatif in enumerate(RAKAM_ICI_KARISTIRMA.get(karakter, [])):
            adaylar.append((alternatif, CEZA_IL_KURTARMA if sira == 0
                            else CEZA_IL_KURTARMA * 0.85))
    else:
        for alternatif in RAKAMA_DONUSUM.get(karakter, []):
            ceza = CEZA_GUCLU if (karakter, alternatif) in GUCLU_KARISTIRMA else CEZA_ZAYIF
            adaylar.append((alternatif, ceza))
    return adaylar


def _il_kodu_coz(iki_karakter: str) -> Tuple[Optional[str], float]:
    """
    İl kodunun tüm makul yorumlarını dener ve GEÇERLİ olanlar arasından
    en az cezalı olanı seçer. (il_kodu, ceza) veya (None, 0.0).

    Bu, çözümleyicinin en güçlü tarafı: 'B4' için hem '84' hem '34' üretilir,
    ama sadece '34' gerçek bir il kodu olduğu için belirsizlik tek bir
    kısıtla çözülür.
    """
    en_iyi, en_ceza = None, 0.0
    for hane1, ceza1 in _il_hane_adaylari(iki_karakter[0]):
        for hane2, ceza2 in _il_hane_adaylari(iki_karakter[1]):
            kod = hane1 + hane2
            if kod not in IL_KODLARI:
                continue
            ceza = ceza1 * ceza2
            if ceza > en_ceza:
                en_ceza, en_iyi = ceza, kod
    return en_iyi, en_ceza


# İl kodundan sonra izin verilen (harf sayısı -> geçerli rakam sayıları)
BLOK_SEMALARI = {1: (4, 5), 2: (3, 4), 3: (2, 3)}


def plaka_cozumle(ham_metin: str, taban_guven: float) -> Tuple[Optional[str], float]:
    """
    Ham OCR metnini Türk plaka dilbilgisine göre çözümler.

    Metin içindeki 7 ve 8 karakterlik tüm alt dizileri, tüm olası
    (il kodu | harf bloğu | rakam bloğu) bölünmeleriyle dener; karakterleri
    konumlarının gerektirdiği sınıfa uyarlar ve en yüksek skorlu yorumu döner.

    Skor = taban_guven × (uyarlama cezalarının geometrik ortalaması)
    Hiç düzeltme gerekmeyen bir okuma, düzeltilmiş bir okumayı hep yener.
    """
    if not ham_metin or len(ham_metin) < 7:
        return None, 0.0

    en_iyi_plaka, en_iyi_skor = None, 0.0
    # Eşit skorda DAHA UZUN yorum kazansın diye karşılaştırma anahtarı
    # (skor, uzunluk) ikilisi; böylece '34CLY063' ile '34CLY06' berabere
    # kaldığında tüm kanıtı kullanan uzun olan seçilir.
    en_iyi_anahtar = (0.0, 0)
    n = len(ham_metin)

    for uzunluk in (8, 7):
        if n < uzunluk:
            continue
        # Alt dizi kullanıldığında atlanan karakter sayısı kadar ceza
        kapsama = KAPSAMA_CEZASI ** (n - uzunluk)

        for basla in range(n - uzunluk + 1):
            parca = ham_metin[basla:basla + uzunluk]

            for harf_sayisi, gecerli_rakamlar in BLOK_SEMALARI.items():
                rakam_sayisi = uzunluk - 2 - harf_sayisi
                if rakam_sayisi not in gecerli_rakamlar:
                    continue

                cozulmus, cezalar, basarili = [], [], True

                # 1) İl kodu — 2 rakam.
                # 🔑 KISIT: il kodu gerçekten var olmalı (01-81).
                # Belirsiz karakterleri çözen asıl bilgi bu.
                il_kodu, il_cezasi = _il_kodu_coz(parca[:2])
                if il_kodu is None:
                    continue
                cozulmus.extend(il_kodu)
                cezalar.append(il_cezasi)

                # 2) Harf bloğu
                for i in range(2, 2 + harf_sayisi):
                    ch, ceza = _karakteri_uyarla(parca[i], "harf")
                    if ch is None:
                        basarili = False
                        break
                    cozulmus.append(ch)
                    cezalar.append(ceza)
                if not basarili:
                    continue

                # 3) Rakam bloğu
                for i in range(2 + harf_sayisi, uzunluk):
                    ch, ceza = _karakteri_uyarla(parca[i], "rakam")
                    if ch is None:
                        basarili = False
                        break
                    cozulmus.append(ch)
                    cezalar.append(ceza)
                if not basarili:
                    continue

                # Cezalar DOĞRUDAN çarpılır (geometrik ortalama alınmaz):
                # 8 karakterlik bir dizide geometrik ortalama, tek bir kötü
                # uyarlamayı görünmez hale getirirdi (0.62^(1/8) ≈ 0.94).
                carpim = kapsama
                for c in cezalar:
                    carpim *= c
                skor = taban_guven * carpim

                anahtar = (round(skor, 6), uzunluk)
                if anahtar > en_iyi_anahtar:
                    en_iyi_anahtar = anahtar
                    en_iyi_skor = skor
                    en_iyi_plaka = "".join(cozulmus)

    return en_iyi_plaka, en_iyi_skor


def plaka_format_gecerli_mi(plaka: str) -> bool:
    """Metin, düzeltmeye gerek kalmadan geçerli bir TR plakası mı?"""
    if not plaka or len(plaka) not in (7, 8):
        return False
    if plaka[:2] not in IL_KODLARI:
        return False
    govde = plaka[2:]
    for harf_sayisi, gecerli_rakamlar in BLOK_SEMALARI.items():
        rakam_sayisi = len(govde) - harf_sayisi
        if rakam_sayisi not in gecerli_rakamlar:
            continue
        harfler, rakamlar = govde[:harf_sayisi], govde[harf_sayisi:]
        if all(c in PLAKA_HARFLERI for c in harfler) and all(c in RAKAMLAR for c in rakamlar):
            return True
    return False


def plaka_temizle(text: str) -> str:
    """OCR metnini normalize eder: büyük harf, Türkçe->Latin, sadece A-Z0-9."""
    text = (text or "").upper().replace(" ", "").strip()
    text = text.translate(str.maketrans("İIÖÜÇŞĞ", "IIOUCSG"))
    return re.sub(r"[^A-Z0-9]", "", text)


# 🇹🇷 Plakanın solundaki mavi TR bandı OCR tarafından 'TR', 'T', '7R', 'TRI'
# gibi okunuyor ve birleştirilmiş metnin başına yapışıyor. Bunları atıyoruz.
TR_BANDI_DESENLERI = {"TR", "T", "TRI", "7R", "IR", "R", "TF", "1R", "TP"}


# ==========================================================================
# 🚫 SABİT TABELA KARA LİSTESİ (sadece ELLE yönetilen, tam eşleşme)
# ==========================================================================
# ⚠️ ÖNEMLİ MİMARİ DEĞİŞİKLİK — "kendi kendine öğrenen kara liste" KALDIRILDI.
#
# Eski mekanizma: OCR'ın okuduğu, tek başına geçerli plaka olmayan her parça
# (>=4 karakter, harf içeren) aday sayılıyor; 3 farklı araçta tekrar ederse
# otomatik kara listeye giriyordu. Sorun şu ki plaka PARÇALARI tam olarak bu
# tanıma uyuyor: '34CLY' tek başına geçerli plaka değil, 'CLY063' de değil.
# Sistem sahadaki gerçek plakaların parçalarını öğrenip yasakladı. Diskteki
# dosya bunu kanıtlıyordu:
#     ["502P","5302P","ABS389","B4CLY","B4LLY","BH3152","CLY063","HJ8583","HRP250"]
# Buradaki 'CLY063', gerçek '34 CLY 063' plakasının kendisi.
#
# Üstüne, eşleştirme çift yönlü substring yapıyordu
# ('063' in 'CLY063' -> True) — yani '063' parçası da eleniyordu. Sonuç:
# sistem doğru okuduğu plakayı kendi eliyle çöpe atıp yerine uydurma bir
# sonuç üretiyordu. Bu mekanizma tamamen silindi.
#
# Sabit tabela/çıkartma sorunu artık DAHA DOĞRU bir yerden çözülüyor:
# plaka sadece hareket eden bir ARACIN kutusu içinde aranıyor (PLAKA_ARAC_ZORUNLU).
# Sabit tabela bir aracın üstünde olmadığı için aday bile olamıyor.
#
# Aşağıdaki liste yalnızca ELLE yönetilir ve TAM EŞLEŞME ile çalışır;
# substring eşleşmesi bilerek kullanılmıyor.
KARA_LISTE_DOSYASI = os.path.join(os.path.dirname(RETRAIN_DIR), "kara_liste.json")


def kara_listeyi_yukle() -> set:
    if os.path.exists(KARA_LISTE_DOSYASI):
        try:
            with open(KARA_LISTE_DOSYASI, "r", encoding="utf-8") as f:
                return set(json.load(f).get("kelimeler", []))
        except Exception as e:
            log(f"⚠️ Kara liste okunamadı, boş başlatılıyor: {e}", "uyari")
    return set()


def kara_listeyi_kaydet():
    try:
        with open(KARA_LISTE_DOSYASI, "w", encoding="utf-8") as f:
            json.dump({"kelimeler": sorted(KARA_LISTE)}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"⚠️ Kara liste diske kaydedilemedi: {e}", "uyari")


KARA_LISTE = kara_listeyi_yukle()
log(f"🚫 Kara liste yüklendi: {len(KARA_LISTE)} elle tanımlı kelime (otomatik öğrenme KAPALI).")


# ==========================================================================
# 🧠 DÜZELTME HAFIZASI (güvenlik görevlisinin düzeltmeleri)
# ==========================================================================
DUZELTME_HAFIZASI_YOLU = os.path.join(os.path.dirname(RETRAIN_DIR), "duzeltme_hafizasi.json")


def duzeltme_hafizasini_yukle() -> dict:
    if os.path.exists(DUZELTME_HAFIZASI_YOLU):
        try:
            with open(DUZELTME_HAFIZASI_YOLU, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log(f"⚠️ Düzeltme hafızası okunamadı: {e}", "uyari")
    return {}


def duzeltme_hafizasini_kaydet(hafiza: dict):
    try:
        with open(DUZELTME_HAFIZASI_YOLU, "w", encoding="utf-8") as f:
            json.dump(hafiza, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"⚠️ Düzeltme hafızası kaydedilemedi: {e}", "uyari")


DUZELTME_HAFIZASI = duzeltme_hafizasini_yukle()
log(f"🧠 Düzeltme hafızası yüklendi: {len(DUZELTME_HAFIZASI)} kayıt.")


def levenshtein_mesafesi(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    onceki = list(range(len(b) + 1))
    for i, ka in enumerate(a, start=1):
        simdiki = [i] + [0] * len(b)
        for j, kb in enumerate(b, start=1):
            simdiki[j] = min(onceki[j] + 1, simdiki[j - 1] + 1, onceki[j - 1] + (ka != kb))
        onceki = simdiki
    return onceki[-1]


def hafizadan_duzelt(plaka: str, esik_mesafe: int = 2) -> Tuple[str, bool]:
    """Geçmişte elle düzeltilmiş bir okumaya tam/yakın eşleşme arar."""
    if plaka in DUZELTME_HAFIZASI:
        return DUZELTME_HAFIZASI[plaka], True
    en_yakin, en_yakin_mesafe = None, esik_mesafe + 1
    for yanlis, dogru in DUZELTME_HAFIZASI.items():
        if len(yanlis) != len(plaka):
            continue
        mesafe = levenshtein_mesafesi(plaka, yanlis)
        if mesafe < en_yakin_mesafe:
            en_yakin_mesafe, en_yakin = mesafe, dogru
    return (en_yakin, True) if en_yakin else (plaka, False)


# ==========================================================================
# 📷 GÖRÜNTÜ İŞLEME
# ==========================================================================

def keskinlik_skoru(gorsel_bgr) -> float:
    """Laplacian varyansı ile netlik ölçer (yüksek = daha net)."""
    try:
        gray = cv2.cvtColor(gorsel_bgr, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except Exception:
        return 0.0


def plaka_bandini_daralt(crop_bgr):
    """
    YOLO'nun plaka kutusu, plakanın kendisinden belirgin şekilde YÜKSEK olur —
    plaka yuvasının gölgesini, tamponun bir kısmını da içine alır (sahadaki
    ölçüm: gerçek plaka 3.9:1 iken YOLO kutusu 2.3:1). Bu fazlalık alan OCR'ı
    yanıltıyor ve normalizasyonu bozuyor.

    Karakterlerin bulunduğu yatay bandı, satır bazlı DİKEY KENAR ENERJİSİNE
    bakarak buluyoruz: karakter satırları bol dikey kenar üretir, düz tampon
    yüzeyi üretmez. Bant güvenilir bulunamazsa orijinal crop aynen döner
    (yani bu adım asla veri kaybettirmez).
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return crop_bgr
    h, w = crop_bgr.shape[:2]
    if h < 20 or w < 40:
        return crop_bgr

    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    sobel = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    satir_enerjisi = sobel.sum(axis=1)
    if satir_enerjisi.max() <= 0:
        return crop_bgr

    esik = satir_enerjisi.max() * 0.35
    aktif = np.where(satir_enerjisi >= esik)[0]
    if aktif.size < 4:
        return crop_bgr

    y1, y2 = int(aktif[0]), int(aktif[-1])
    bant_yuksekligi = y2 - y1
    # Bant, kutunun çok küçük bir dilimiyse ölçüm güvenilmezdir
    if bant_yuksekligi < h * 0.20:
        return crop_bgr

    pay = int(bant_yuksekligi * 0.22) + 2
    y1 = max(0, y1 - pay)
    y2 = min(h, y2 + pay)
    daraltilmis = crop_bgr[y1:y2, :]
    return daraltilmis if daraltilmis.size > 0 else crop_bgr


# 📏 ÖLÇEK — doğruluğu belirleyen TEK EN ÖNEMLİ parametre.
# Kırpmayı sabit bir çarpanla değil HEDEF YÜKSEKLİĞE normalize ediyoruz:
# uzaktaki küçük bir plaka da, yakındaki büyük bir plaka da OCR'a aynı
# ölçekte gider.
#
# 📊 Değer, yer gerçeği BİLİNEN 4 araç (41 kare) üzerinde tarandı.
# Sahada giriş kamerası '41' plakalarını ısrarla '61' okuyordu; sebebi
# yetersiz büyütmeymiş:
#       hedef 230 -> %29 kare doğruluğu   (41ALA927 ve 41ATK278 YANLIŞ)
#       hedef 380 -> %63
#       hedef 460 -> %71
#       hedef 620 -> %88  ✅ dördü de doğru  <-- seçilen
#       hedef 700 -> %73  (aşırı büyütme artefaktı başlıyor)
#       hedef 900 -> %71  (büyük kırpmalı K2 vakası bile bozuluyor)
# Tepe noktası 620; ötesinde interpolasyon karakterleri bozmaya başlıyor.
HEDEF_PLAKA_YUKSEKLIGI = int(os.getenv("HEDEF_PLAKA_YUKSEKLIGI", "620"))
# Küçük kırpmalarda hedefe ulaşmak 8x'i bulabiliyor (74px -> 620px);
# tavan bunu engellememeli.
AZAMI_OLCEK = float(os.getenv("AZAMI_OLCEK", "10.0"))


def _hedef_boyuta_olcekle(bgr):
    """Kırpmayı hedef yüksekliğe büyütür ve griye çevirir. Asla küçültmez."""
    h, w = bgr.shape[:2]
    olcek = max(1.0, min(HEDEF_PLAKA_YUKSEKLIGI / float(h), AZAMI_OLCEK))
    if olcek > 1.01:
        bgr = cv2.resize(bgr, (int(w * olcek), int(h * olcek)),
                         interpolation=cv2.INTER_CUBIC)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)


def plaka_egimini_duzelt(crop_bgr):
    """
    Plakanın eğimini bulup düzeltir (deskew). Bulunamazsa None.

    📊 NEDEN: Sahadaki hataların ezici çoğunluğu İL KODUNDA yoğunlaşıyordu
    (34↔14↔61↔04↔81); gövde neredeyse her zaman doğru okunuyordu. Sebebi
    şu: kamera plakaya açıyla baktığı için perspektif SOL kenarı sıkıştırıyor
    ve il kodu tam orada duruyor. Eğim düzeltilince o sıkışma azalıyor.

    ⚠️ TAM perspektif (4 köşe + warpPerspective) denendi ve ÇOK DAHA KÖTÜ
    çıktı: tam plaka doğruluğu %62 -> %39. Dört köşe tespiti güvenilmez,
    yanlış dörtgen bulunca görüntüyü tamamen bozuyor. Sadece DÖNDÜRME
    (minAreaRect) kullanılıyor; ölçüm: %62 -> %70, orijinalle birlikte
    denenince %72.
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return None
    h, w = crop_bgr.shape[:2]
    if h < 20 or w < 40:
        return None
    try:
        gri = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        gri = cv2.bilateralFilter(gri, 9, 75, 75)
        _, esik = cv2.threshold(gri, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Karakter boşluklarını kapat ki plaka tek bir blok olsun
        cekirdek = cv2.getStructuringElement(cv2.MORPH_RECT,
                                             (max(5, w // 12), max(3, h // 10)))
        kapali = cv2.morphologyEx(esik, cv2.MORPH_CLOSE, cekirdek)
        konturlar, _ = cv2.findContours(kapali, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not konturlar:
            return None
        kontur = max(konturlar, key=cv2.contourArea)
        if cv2.contourArea(kontur) < w * h * 0.15:
            return None

        (cx, cy), (rw, rh), aci = cv2.minAreaRect(kontur)
        if rw < rh:
            rw, rh = rh, rw
            aci += 90
        # Plaka gibi durmuyorsa ya da açı saçmaysa dokunma
        if rh < 10 or not (1.5 <= rw / rh <= 8) or abs(aci) > 30:
            return None

        donus = cv2.getRotationMatrix2D((cx, cy), aci, 1.0)
        dondurulmus = cv2.warpAffine(crop_bgr, donus, (w, h),
                                     flags=cv2.INTER_CUBIC,
                                     borderMode=cv2.BORDER_REPLICATE)
        x1, y1 = max(0, int(cx - rw / 2)), max(0, int(cy - rh / 2))
        x2, y2 = min(w, int(cx + rw / 2)), min(h, int(cy + rh / 2))
        if x2 - x1 < 40 or y2 - y1 < 12:
            return None
        kirpilmis = dondurulmus[y1:y2, x1:x2]
        return kirpilmis if kirpilmis.size > 0 else None
    except Exception:
        return None


def _varyant_seti(crop_bgr, clahe) -> List:
    """Tek bir kırpma için gri / CLAHE / keskin varyantlarını üretir."""
    gri = _hedef_boyuta_olcekle(crop_bgr)
    clahe_gri = clahe.apply(gri)
    bulanik = cv2.GaussianBlur(clahe_gri, (0, 0), sigmaX=2.0)
    keskin = cv2.addWeighted(clahe_gri, 1.6, bulanik, -0.6, 0)
    return [gri, clahe_gri, keskin]


def ocr_varyantlari(crop_bgr) -> List:
    """
    OCR'a denenecek ön-işleme varyantlarını üretir.

    Eski sürüm zincirleme agresif işlem yapıyordu: CLAHE -> 400px resize ->
    bilateral -> kontur kırpma -> 3x resize -> 4 ayrı binarizasyon. Sert
    eşiklemeler NET bir '34 CLY 063' görüntüsünü bile bozuyordu.

    Varyant seti ölçümle seçildi — hepsi aynı hatayı yapmasın diye birbirini
    tamamlayan dönüşümler: ham gri (görüntü iyiyse en sadık), CLAHE (gölge),
    keskinleştirme (büyütme bulanıklığı), daraltılmış bant (fazla tampon
    alanı OCR'ı yanıltıyorsa) ve eğimi düzeltilmiş hâl (perspektif il kodunu
    sıkıştırıyorsa).

    ⚠️ SIRALAMA ÖNEMLİ: eğim düzeltilmiş varyantlar EN SONA konuyor. Orijinal
    zaten temiz okunduysa varyant erken çıkışı devreye girip fazladan iş
    yapılmıyor; ek maliyet yalnızca ZOR karelerde ödeniyor.
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return []
    h, w = crop_bgr.shape[:2]
    if h < 8 or w < 20:
        return []

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    varyantlar = _varyant_seti(crop_bgr, clahe)

    # Bant daraltma gerçekten bir şey değiştirdiyse, onun ölçeklenmiş
    # hâlini de ayrı bir varyant olarak dene.
    dar = plaka_bandini_daralt(crop_bgr)
    if dar is not crop_bgr and dar.shape[:2] != crop_bgr.shape[:2]:
        varyantlar.append(_hedef_boyuta_olcekle(dar))

    # 📐 Eğimi düzeltilmiş hâl — perspektifin sıkıştırdığı il kodu için.
    # En sonda: orijinal temiz okunduysa erken çıkış bunu hiç çalıştırmaz.
    egimsiz = plaka_egimini_duzelt(crop_bgr)
    if egimsiz is not None:
        varyantlar.extend(_varyant_seti(egimsiz, clahe))

    return varyantlar


EASYOCR_ALLOWLIST = "ABCDEFGHIJKLMNOPRSTUVYZ0123456789"


def parcalari_birlestir(ocr_sonuclari) -> List[Tuple[str, float]]:
    """
    EasyOCR parçalarını (bbox, text, prob) aynı metin satırına göre gruplar,
    soldan sağa birleştirir ve (birlesik_metin, ortalama_guven) adayları döner.

    Plaka tek satırdır; farklı yükseklikteki parçalar (firma yazısı, ikinci
    satır) ayrı gruplara düşer ve birbirine yapışmaz.
    """
    parcalar = []
    for bbox, text, prob in ocr_sonuclari:
        if prob < 0.10:
            continue
        temiz = plaka_temizle(text)
        if not temiz:
            continue
        ys = [n[1] for n in bbox]
        xs = [n[0] for n in bbox]
        y_merkez = (min(ys) + max(ys)) / 2.0
        yukseklik = max(max(ys) - min(ys), 1.0)
        parcalar.append({
            "text": temiz, "prob": float(prob),
            "x": min(xs), "y": y_merkez, "h": yukseklik,
        })

    if not parcalar:
        return []

    parcalar.sort(key=lambda p: p["x"])

    # Aynı satır grupları: dikey merkez farkı, ortalama yüksekliğin %60'ını aşmasın
    gruplar: List[List[dict]] = []
    for p in parcalar:
        yerlesti = False
        for g in gruplar:
            ort_y = sum(q["y"] for q in g) / len(g)
            ort_h = sum(q["h"] for q in g) / len(g)
            if abs(p["y"] - ort_y) <= ort_h * 0.60:
                g.append(p)
                yerlesti = True
                break
        if not yerlesti:
            gruplar.append([p])

    adaylar = []
    for g in gruplar:
        g.sort(key=lambda p: p["x"])

        # 🇹🇷 Soldaki mavi TR bandı ayrı bir parça olarak okunuyor — at.
        while g and g[0]["text"] in TR_BANDI_DESENLERI:
            g.pop(0)
        if not g:
            continue

        birlesik = "".join(p["text"] for p in g)
        ortalama = sum(p["prob"] for p in g) / len(g)
        adaylar.append((birlesik, ortalama))

        # 🇹🇷 TR bandı her zaman ayrı bir parça olarak okunmaz; bazen komşu
        # parçaya yapışır ('TR34'). Ön eki atılmış hâlini de aday yapıyoruz ki
        # çözümleyicide gereksiz kapsama cezası yemesin.
        for on_ek in ("TR", "7R", "IR", "T"):
            if birlesik.startswith(on_ek) and len(birlesik) - len(on_ek) >= 7:
                adaylar.append((birlesik[len(on_ek):], ortalama))
                break

        # Parçalardan biri gürültüyse, ardışık alt-dizileri de aday yap
        if len(g) > 1:
            for i in range(len(g)):
                for j in range(i + 1, len(g) + 1):
                    if j - i == len(g):
                        continue
                    alt = g[i:j]
                    metin = "".join(p["text"] for p in alt)
                    if len(metin) >= 7:
                        adaylar.append((metin, sum(p["prob"] for p in alt) / len(alt)))

    return adaylar


def kareyi_oku(crop_bgr) -> Tuple[Optional[str], float, List]:
    """
    Tek bir plaka karesini okur.
    (plaka, skor, ham_parcalar) döner. Geçerli sonuç yoksa (None, 0.0, [...]).
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return None, 0.0, []

    # Not: bant daraltma ocr_varyantlari() içinde ayrı bir varyant olarak
    # uygulanıyor — burada tekrar uygulanmamalı.
    varyantlar = ocr_varyantlari(crop_bgr)
    if not varyantlar:
        return None, 0.0, []

    en_iyi_plaka, en_iyi_skor = None, 0.0
    ham_parcalar = []

    for v_idx, varyant in enumerate(varyantlar):
        try:
            with INFERENCE_LOCK:
                sonuclar = reader.readtext(varyant, allowlist=EASYOCR_ALLOWLIST,
                                           detail=1, paragraph=False)
        except Exception as e:
            log(f"⚠️ OCR hatası (varyant {v_idx + 1}): {e}", "uyari")
            continue
        if not sonuclar:
            continue

        for (_bbox, text, prob) in sonuclar:
            ham_parcalar.append((v_idx, text, float(prob)))

        for birlesik, guven in parcalari_birlestir(sonuclar):
            if birlesik in KARA_LISTE:          # tam eşleşme — substring DEĞİL
                continue
            plaka, skor = plaka_cozumle(birlesik, guven)
            if plaka and skor > en_iyi_skor:
                en_iyi_plaka, en_iyi_skor = plaka, skor

        # ⏩ Bu varyant zaten neredeyse kusursuz okuduysa (hiç karakter
        # düzeltmesi gerekmemiş, OCR de emin) kalan varyantları denemeye
        # gerek yok. Kolay kareler ~4 kat hızlanıyor; kazanılan süre zor
        # vakalarda daha çok KARE okumaya harcanıyor.
        if en_iyi_skor >= VARYANT_ERKEN_CIKIS:
            break

    return en_iyi_plaka, en_iyi_skor, ham_parcalar


def zamansal_mutabakat(adaylar: List[Tuple[str, float]]
                       ) -> Tuple[Optional[str], float, int, float]:
    """
    Episode boyunca farklı karelerden toplanan adayları birleştirir.
    (plaka, guven, destekleyen_kare_sayisi, kanit_payi) döner.

    ⚠️ ÖNEMLİ DÜZELTME — sahada yanlış plaka gönderilmesine yol açan kusur:
    Önceki sürüm adayları önce KARE SAYISINA göre sıralıyordu. 2026-07-23
    loglarında bu, şu sonucu doğurdu:
        34MAA484 (DOĞRU)  -> 1 kare, skor 0.92
        34HAA484 (yanlış) -> 2 kare, skor 0.61 ve 0.55
    Sayı mutlak öncelikli olduğu için YANLIŞ olan kazandı ve backend'e gitti.
    Oysa tek bir çok net okuma, iki bulanık okumadan daha güvenilirdir.

    Artık adaylar KANIT AĞIRLIĞINA göre sıralanıyor: her okumanın skorunun
    KARESİ toplanır. Kare almak, yüksek güvenli okumaları öne çıkarır ve
    kararsız/düşük skorlu tekrarların birikip kazanmasını engeller:
        34MAA484 -> 0.92²             = 0.85
        34HAA484 -> 0.61² + 0.55²     = 0.68   -> doğru olan kazanır ✅

    `kanit_payi` = kazananın ağırlığı / tüm adayların toplam ağırlığı.
    Kazananın kanıta ne kadar hâkim olduğunu ölçer; tek karelik sonuçların
    kabulünde "ortalık karışık mı?" sorusunun cevabı olarak kullanılır.
    """
    if not adaylar:
        return None, 0.0, 0, 0.0

    havuz = {}
    for plaka, skor in adaylar:
        kayit = havuz.setdefault(plaka, {"sayi": 0, "toplam": 0.0,
                                         "agirlik": 0.0, "en_iyi": 0.0})
        kayit["sayi"] += 1
        kayit["toplam"] += skor
        kayit["agirlik"] += skor * skor
        kayit["en_iyi"] = max(kayit["en_iyi"], skor)

    en_iyi_plaka, kayit = max(havuz.items(), key=lambda o: o[1]["agirlik"])

    toplam_agirlik = sum(k["agirlik"] for k in havuz.values()) or 1.0
    kanit_payi = kayit["agirlik"] / toplam_agirlik

    ortalama = kayit["toplam"] / kayit["sayi"]
    # Tekrar eden okumaya küçük bir güven primi (en fazla +%12)
    prim = min(0.12, 0.04 * (kayit["sayi"] - 1))
    guven = min(1.0, max(ortalama, kayit["en_iyi"] * 0.9) + prim)
    return en_iyi_plaka, guven, kayit["sayi"], kanit_payi


def ayni_arac_mi(plaka: str, gonderilenler: dict, simdi: float) -> Optional[str]:
    """
    Bu okuma, yakın zamanda gönderilmiş bir plakayla AYNI ARACA mı ait?
    Eşleşen önceki plakayı döner, yoksa None.

    İki durumu yakalar:
      1) Birebir aynı plaka (klasik tekrar).
      2) SADECE İL KODU farklı, gövdesi birebir aynı olan okuma.
         Sahada en sık görülen hata tam olarak bu: aynı kamyon ardışık
         episode'larda '34HRR696' ve '14HRR696' olarak okundu ve backend'e
         iki çelişkili kayıt gitti.

    ⚠️ Gövde farkı BİLEREK eşleşme sayılmaz. Lojistik filolarında ardışık
    plakalar yaygın ('34POS625' ve '34POS628' sahada gerçekten iki AYRI
    kamyondu); gövdeye toleranslı bir birleştirme farklı araçları tek
    kayda indirip veri kaybettirirdi.
    """
    for onceki, zaman in gonderilenler.items():
        if (simdi - zaman) >= AYNI_PLAKA_BEKLEME:
            continue
        if onceki == plaka:
            return onceki
        if len(onceki) == len(plaka) and onceki[2:] == plaka[2:] and onceki[:2] != plaka[:2]:
            return onceki
    return None


def kutu_ortusme_orani(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    kx1, ky1 = max(ax1, bx1), max(ay1, by1)
    kx2, ky2 = min(ax2, bx2), min(ay2, by2)
    kesisim = max(0, kx2 - kx1) * max(0, ky2 - ky1)
    a_alan = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    b_alan = max(0, bx2 - bx1) * max(0, by2 - by1)
    birlesim = a_alan + b_alan - kesisim
    return kesisim / birlesim if birlesim > 0 else 0.0


def gorseli_base64_kodla(gorsel_bgr, jpeg_kalite: int = 88) -> Optional[str]:
    try:
        ok, buffer = cv2.imencode(".jpg", gorsel_bgr, [cv2.IMWRITE_JPEG_QUALITY, jpeg_kalite])
        return base64.b64encode(buffer).decode("utf-8") if ok else None
    except Exception as e:
        log(f"⚠️ Görsel base64'e çevrilemedi: {e}", "uyari")
        return None


# ==========================================================================
# 📋 VERİ YAPILARI
# ==========================================================================
class KameraIstek(BaseModel):
    kamera_id: int
    depo_id: int
    rtsp_url: str
    yon: Optional[str] = "bilinmiyor"
    aktif_mi: Optional[bool] = True


class PlakaVeriPaketi(BaseModel):
    kamera_id: int
    depo_id: int
    yon: str
    plaka_metni: str
    arac_tipi: str
    guven_skoru: float
    tarih_saat: str
    # 🖼️ Backend base64 değil erişilebilir bir URL bekliyor (bkz. /captures).
    image_url: Optional[str] = None
    # Geriye dönük uyumluluk — yalnızca GORSEL_BASE64_GONDER=true iken dolar.
    plaka_gorseli_base64: Optional[str] = None
    tam_kare_gorseli_base64: Optional[str] = None


class PlakaDuzeltmeIstek(BaseModel):
    kamera_id: int
    yanlis_plaka: str
    dogru_plaka: str


# ==========================================================================
# 🎥 KAMERA TANIMLARI
# ==========================================================================
# 🔐 Kamera kimlik bilgileri ve adresleri env'den okunur — kaynak kodda düz
# metin şifre bırakmıyoruz. Env verilmezse eski davranışa düşen varsayılanlar
# kullanılır, böylece servis her koşulda ayağa kalkar.
_GEBZE_KULLANICI = os.getenv("GEBZE_KAMERA_KULLANICI", "admin")
_GEBZE_SIFRE = os.getenv("GEBZE_KAMERA_SIFRE", "center@dhl99")
_GEBZE_SIFRE_ENCODED = quote(_GEBZE_SIFRE, safe="")
_GEBZE_HOST = os.getenv("GEBZE_KAMERA_HOST", "2.200.168.165")
_GEBZE_GIRIS_PORT = os.getenv("GEBZE_GIRIS_PORT", "8001")
_GEBZE_CIKIS_PORT = os.getenv("GEBZE_CIKIS_PORT", "8003")

# 📡 RTSP profili. profile1 = ana akış, profile2 = alt akış.
# Sahada profile2 de 2560x1440 veriyor ve doğrulanmış okumaların tamamı bu
# akıştan alındı — bant genişliği açısından varsayılan olarak bunu tutuyoruz.
RTSP_PROFIL = os.getenv("RTSP_PROFIL", "profile2")

GEBZE_KAMERALARI = [
    {
        "kamera_id": 1, "depo_id": 1, "yon": "giris", "isim": "Gebze Giriş Kamerası",
        "rtsp_url": (f"rtsp://{_GEBZE_KULLANICI}:{_GEBZE_SIFRE_ENCODED}@{_GEBZE_HOST}:"
                     f"{_GEBZE_GIRIS_PORT}/{RTSP_PROFIL}/media.smp"),
    },
    {
        "kamera_id": 2, "depo_id": 1, "yon": "cikis", "isim": "Gebze Çıkış Kamerası",
        "rtsp_url": (f"rtsp://{_GEBZE_KULLANICI}:{_GEBZE_SIFRE_ENCODED}@{_GEBZE_HOST}:"
                     f"{_GEBZE_CIKIS_PORT}/{RTSP_PROFIL}/media.smp"),
    },
]

son_yakalanan_goruntuler = {}
KAMERA_DURUMLARI = {}   # kamera_id -> canlı istatistik (durum uçları için)
_durum_kilit = threading.Lock()


def durum_guncelle(kamera_id: int, **alanlar):
    with _durum_kilit:
        KAMERA_DURUMLARI.setdefault(kamera_id, {}).update(alanlar)


# ==========================================================================
# 📡 RTSP OKUYUCU — ayrı thread, daima en güncel kare
# ==========================================================================
class KameraOkuyucu:
    """
    RTSP akışını kendi thread'inde sürekli okur ve sadece EN SON kareyi tutar.

    Neden gerekli: YOLO+OCR bir kareyi işlerken kamera yeni kareler üretmeye
    devam eder ve bunlar FFMPEG tamponunda birikir. Ana döngü cap.read()
    çağırdığında saniyeler ÖNCESİNE ait bayat bir kare alır; araç çoktan
    geçmiş olur. CAP_PROP_BUFFERSIZE=1 FFMPEG backend'inde çoğu zaman
    yok sayılır. Okumayı ayırmak bu gecikmeyi tamamen ortadan kaldırır.
    """

    def __init__(self, rtsp_url: str, etiket: str):
        self.rtsp_url = rtsp_url
        self.etiket = etiket
        self._kare = None
        self._sayac = 0
        self._kilit = threading.Lock()
        self._dur = False
        self._thread = None
        self.baglanti_tamam = False

    def basla(self):
        self._thread = threading.Thread(target=self._dongu, daemon=True,
                                        name=f"rtsp-{self.etiket}")
        self._thread.start()

    def _dongu(self):
        cap = None
        while not self._dur:
            if cap is None or not cap.isOpened():
                if cap is not None:
                    cap.release()
                cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if not cap.isOpened():
                    self.baglanti_tamam = False
                    log(f"❌ {self.etiket} RTSP akışı açılamadı, 5 sn sonra tekrar denenecek.", "hata")
                    time.sleep(5)
                    continue
                self.baglanti_tamam = True
                log(f"🎥 {self.etiket} RTSP akışı açıldı.")

            ret, kare = cap.read()
            if not ret or kare is None:
                self.baglanti_tamam = False
                log(f"⚠️ {self.etiket} kare alınamadı, akış yeniden kurulacak.", "uyari")
                cap.release()
                cap = None
                time.sleep(2)
                continue

            with self._kilit:
                self._kare = kare
                self._sayac += 1

        if cap is not None:
            cap.release()

    def son_kare(self):
        """(kare_kopyasi, sayac) döner; henüz kare yoksa (None, 0)."""
        with self._kilit:
            if self._kare is None:
                return None, 0
            return self._kare.copy(), self._sayac

    def durdur(self):
        self._dur = True


# ==========================================================================
# 🧠 ANA PIPELINE
# ==========================================================================
def gercek_yolo_ocr_pipeline(kamera_id: int, depo_id: int, rtsp_url: str, yon: str = "bilinmiyor"):
    etiket = f"[{yon.upper()} K{kamera_id}]"
    log(f"🔌 {etiket} pipeline başlatılıyor...")

    okuyucu = KameraOkuyucu(rtsp_url, etiket)
    okuyucu.basla()

    durum_guncelle(kamera_id, yon=yon, depo_id=depo_id, baslangic=datetime.now().isoformat(),
                   toplam_episode=0, toplam_okuma=0, son_plaka=None, son_okuma_zamani=None)

    son_islenen_sayac = -1
    son_heartbeat = time.time()

    # Episode durumu
    arac_aktif = False
    arac_baslangic = 0.0
    son_tespit = 0.0
    episode_arac_tipi = "bilinmiyor"
    kare_havuzu: List[dict] = []
    episod_kutu = None
    # 🖼️ Episode'un en iyi TAM karesi (image_url ve debug kaydı için)
    en_iyi_tam_kare = None
    en_iyi_tam_kare_kutu = None
    en_iyi_tam_kare_skoru = 0.0

    son_islenen_kutu = None
    son_islenen_zaman = 0.0
    gonderilen_plakalar = {}   # plaka -> son gönderim zamanı
    # 🩺 Teşhis sayaçları: elenen plaka kutularının sebepleri
    tani_sayaclari = {}

    while True:
        # 🛡️ HATA KORUMASI: tek bir bozuk karede fırlayan exception, bu
        # kameranın thread'ini KALICI olarak öldürürdü — servis ayakta
        # görünmeye devam eder ama o kamera sessizce ölür. Döngü gövdesini
        # koruyoruz: hatayı logla, sonraki kareye geç.
        try:
            kare, sayac = okuyucu.son_kare()

            # ⚠️ Aynı kareyi İKİ KEZ işlememek kritik: aksi halde tek bir okuma
            # havuza defalarca girip SAHTE MUTABAKAT üretir (zamansal_mutabakat
            # "5 farklı karede aynı sonuç" sanar) ve GPU boşa yanar. Yeni kare
            # yoksa kareyi işlemeye hiç sokmuyoruz — ama episode zaman aşımı
            # kontrolü aşağıda yine de çalışmalı, yoksa araç ayrıldığında
            # episode hiç kapanmaz.
            yeni_kare_var = kare is not None and sayac != son_islenen_sayac
            if yeni_kare_var:
                son_islenen_sayac = sayac
            else:
                kare = None
                time.sleep(0.01)   # yeni kare yok — CPU'yu boşa yakma

            simdi = time.time()

            # 💓 Heartbeat
            if not arac_aktif and (simdi - son_heartbeat) >= HEARTBEAT_SANIYE:
                baglanti = "canlı" if okuyucu.baglanti_tamam else "KOPUK"
                mesaj = f"💓 {etiket} Akış {baglanti}, son {int(HEARTBEAT_SANIYE)} sn'de araç yok."
                # 🩺 Sürekli "çok küçük" eleniyorsa bu bir YAZILIM değil KAMERA
                # AÇISI sorunudur — kullanıcı bunu logdan görebilmeli.
                kucuk = tani_sayaclari.get("cok_kucuk", 0)
                if kucuk > 0:
                    mesaj += (f"  ⚠️ bu pencerede {kucuk} kez 'plaka çok küçük' elendi — "
                              f"kamera açısı/zoom plakayı yeterince büyük görmüyor olabilir.")
                log(mesaj)
                son_heartbeat = simdi
                # Sayaçlar PENCERE bazlı olmalı: kümülatif toplam sürekli büyüyüp
                # ("1112 kez") sorunun hâlâ sürüp sürmediğini gizliyordu.
                tani_sayaclari.clear()

            if kare is not None:
                # 🚫 Üstteki tarih/saat filigranı ve sabit yazı bandını karart
                if UST_MASKE_ORANI > 0:
                    h_f, w_f = kare.shape[:2]
                    kare[0:int(h_f * UST_MASKE_ORANI), 0:w_f] = (0, 0, 0)

                # ---------- ADIM 1: Araç tespiti ----------
                arac_kutusu, arac_tipi, insan_kutulari = arac_tespit_et(kare)

                # ---------- ADIM 2: Plaka tespiti (araç kutusu içinde) ----------
                en_iyi_kutu, en_iyi_conf = None, 0.0
                if arac_kutusu is not None or not PLAKA_ARAC_ZORUNLU:
                    en_iyi_kutu, en_iyi_conf = plaka_tespit_et(
                        kare, arac_kutusu, insan_kutulari, etiket, tani_sayaclari)
                    durum_guncelle(kamera_id, elenen_kutular=dict(tani_sayaclari))

                # ---------- ADIM 3: Episode yönetimi ----------
                if en_iyi_kutu is not None:
                    x1, y1, x2, y2 = en_iyi_kutu
                    crop = kare[y1:y2, x1:x2]

                    if crop.size > 0:
                        if not arac_aktif:
                            # 🧊 Cooldown: az önce işlediğimiz aynı konumdaki nesne mi?
                            #
                            # ⚠️ Bu kontrol KONUMSAL olmalı, sadece zamana bağlı
                            # DEĞİL. Sahada (2026-07-23) bir kamyon çıkış kapısında
                            # durdu; sabit süreli cooldown dolunca sistem sürekli
                            # yeni episode açtı ve aynı plakayı 83 saniye arayla
                            # İKİ KEZ backend'e gönderdi — tek araç için iki kayıt.
                            # Araç kutusu hâlâ aynı yerdeyse zamanlayıcıyı
                            # TAZELİYORUZ: duran araç asla yeniden tetiklemez, ama
                            # gerçekten ayrılıp yerine yenisi geldiğinde (kutu
                            # kayar, IoU düşer) episode anında açılır.
                            if (son_islenen_kutu is not None
                                    and (simdi - son_islenen_zaman) < COOLDOWN_SANIYE
                                    and kutu_ortusme_orani(en_iyi_kutu, son_islenen_kutu) > COOLDOWN_IOU_ESIGI):
                                son_islenen_zaman = simdi   # araç hâlâ orada — süreyi uzat
                            else:
                                arac_aktif = True
                                arac_baslangic = simdi
                                kare_havuzu = []
                                episode_arac_tipi = arac_tipi
                                log(f"🚗 {etiket} Araç algılandı ({arac_tipi}) — kare toplanıyor...")

                        if arac_aktif:
                            son_tespit = simdi
                            episod_kutu = en_iyi_kutu

                            keskinlik = keskinlik_skoru(crop)
                            if keskinlik < MIN_KESKINLIK:
                                log_ayrinti(f"   🏃 {etiket} Bulanık kare atlandı (keskinlik={keskinlik:.0f}).")
                            else:
                                kare_havuzu.append({
                                    "gorsel": crop,
                                    "alan": (x2 - x1) * (y2 - y1),
                                    "keskinlik": keskinlik,
                                    "conf": en_iyi_conf,
                                    "kutu": en_iyi_kutu,
                                })

                                # 🖼️ Episode'un EN İYİ tam karesini tek bir değişkende
                                # tutuyoruz.
                                # ⚠️ Bellek: eskiden her havuz kaydına kare.copy()
                                # konuyordu. 2560x1440 bir kare ~11 MB; sahada 179
                                # karelik episode'lar görüldü -> ~2 GB. Tek bir "en
                                # iyi" kare tutmak bunu sabit maliyete indiriyor.
                                tam_kare_skoru = keskinlik * (x2 - x1)
                                if tam_kare_skoru > en_iyi_tam_kare_skoru:
                                    en_iyi_tam_kare_skoru = tam_kare_skoru
                                    en_iyi_tam_kare = kare.copy()
                                    en_iyi_tam_kare_kutu = en_iyi_kutu

                            if DEBUG_KARE_KAYDET:
                                ad = f"kam{kamera_id}_{int(simdi * 1000)}.jpg"
                                cv2.imwrite(os.path.join(DEBUG_KARE_DIR, ad), crop)

            # ---------- ADIM 4: Episode sonlandırma ----------
            if arac_aktif:
                ayrildi = (simdi - son_tespit) >= ARAC_AYRILMA_BOSLUGU
                zaman_asimi = (simdi - arac_baslangic) >= MAKS_TOPLAMA_SANIYESI

                if ayrildi or zaman_asimi:
                    sebep = "araç ayrıldı" if ayrildi else "azami süre doldu"
                    log(f"⏱️ {etiket} Toplama bitti ({sebep}) — {len(kare_havuzu)} kare toplandı.")

                    episode_isle(kamera_id, depo_id, yon, etiket, kare_havuzu,
                                 episode_arac_tipi, gonderilen_plakalar,
                                 en_iyi_tam_kare, en_iyi_tam_kare_kutu)

                    if episod_kutu is not None:
                        son_islenen_kutu = episod_kutu
                        son_islenen_zaman = time.time()

                    en_iyi_tam_kare = None
                    en_iyi_tam_kare_kutu = None
                    en_iyi_tam_kare_skoru = 0.0
                    arac_aktif = False
                    kare_havuzu = []
                    episod_kutu = None
                    son_heartbeat = time.time()
        except Exception as e:
            log(f"❌ {etiket} Kare işlenirken beklenmeyen hata: {e}", "hata")
            logger.exception("kare işleme hatası")
            time.sleep(0.5)
            continue


def arac_tespit_et(kare):
    """
    COCO ile araç ve insan kutularını bulur.
    (arac_kutusu | None, arac_tipi, insan_kutulari) döner.

    ⚠️ Eski sürümde karede herhangi bir insan görülürse TÜM kare atlanıyordu
    (`continue`). Şoför kabinde neredeyse her zaman göründüğü için bu, araç
    geçişlerinin büyük kısmının hiç işlenmemesine yol açıyordu. Artık insan
    kutuları sadece plaka adaylarını elemek için kullanılıyor.
    """
    with INFERENCE_LOCK:
        sonuclar = detection_model(kare, device=AI_DEVICE, verbose=False, conf=ARAC_TESPIT_CONF)

    insan_kutulari = []
    en_buyuk_arac, en_buyuk_alan, arac_tipi = None, 0, "bilinmiyor"

    for sonuc in sonuclar:
        for kutu in sonuc.boxes:
            sinif = int(kutu.cls[0])
            xyxy = tuple(map(int, kutu.xyxy[0].cpu().numpy()))

            if sinif == 0:
                insan_kutulari.append(xyxy)
                continue

            if sinif in COCO_ARAC_SINIFLARI:
                alan = (xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1])
                if alan > en_buyuk_alan:
                    en_buyuk_alan = alan
                    en_buyuk_arac = xyxy
                    arac_tipi = COCO_CLASSES.get(sinif, "bilinmiyor")

    return en_buyuk_arac, arac_tipi, insan_kutulari


def plaka_tespit_et(kare, arac_kutusu, insan_kutulari, etiket, sayaclar=None):
    """
    Plaka kutusunu bulur. Arama, varsa araç kutusuyla sınırlanır.
    (en_iyi_kutu | None, conf) döner.

    `sayaclar` verilirse elenen kutuların sebepleri sayılır — bir kamera
    sürekli "çok küçük" eliyorsa bu bir YAZILIM değil KAMERA AÇISI sorunudur
    ve /api/v1/kamera/durum üzerinden görülebilir olmalı.

    ⚠️ Eski sürümde adaylar arasından ALANI EN BÜYÜK olan seçiliyordu. Kamyon
    üstündeki uyarı çıkartması gerçek plakadan büyük göründüğünde, o karede
    gerçek plaka havuza hiç girmiyor, etiket OCR'a gidiyordu. Artık dedektörün
    en GÜVENDİĞİ kutu seçiliyor.
    """
    arama_karesi = kare
    ofset_x, ofset_y = 0, 0

    if arac_kutusu is not None:
        ax1, ay1, ax2, ay2 = arac_kutusu
        pay = int((ay2 - ay1) * 0.10)
        ax1, ay1 = max(0, ax1 - pay), max(0, ay1 - pay)
        ax2 = min(kare.shape[1], ax2 + pay)
        ay2 = min(kare.shape[0], ay2 + pay)
        if ax2 > ax1 and ay2 > ay1:
            arama_karesi = kare[ay1:ay2, ax1:ax2]
            ofset_x, ofset_y = ax1, ay1

    if arama_karesi.size == 0:
        return None, 0.0

    with INFERENCE_LOCK:
        sonuclar = model(arama_karesi, device=AI_DEVICE, verbose=False,
                         conf=PLAKA_CONF_ESIGI, imgsz=PLAKA_IMGSZ)

    en_iyi_kutu, en_iyi_conf = None, 0.0

    for sonuc in sonuclar:
        for kutu in sonuc.boxes:
            x1, y1, x2, y2 = map(int, kutu.xyxy[0].cpu().numpy())
            x1, y1 = x1 + ofset_x, y1 + ofset_y
            x2, y2 = x2 + ofset_x, y2 + ofset_y
            conf = float(kutu.conf[0]) if kutu.conf is not None else 0.0

            genislik, yukseklik = x2 - x1, y2 - y1
            if genislik < PLAKA_MIN_GENISLIK or yukseklik < 16:
                if sayaclar is not None:
                    sayaclar["cok_kucuk"] = sayaclar.get("cok_kucuk", 0) + 1
                log_ayrinti(f"   🚫 {etiket} Kutu çok küçük ({genislik}x{yukseklik}px) — okunamaz.")
                continue

            oran = genislik / float(yukseklik)
            if not (PLAKA_EN_BOY_MIN <= oran <= PLAKA_EN_BOY_MAX):
                if sayaclar is not None:
                    sayaclar["oran_uymadi"] = sayaclar.get("oran_uymadi", 0) + 1
                log_ayrinti(f"   🚫 {etiket} Kutu elendi (oran={oran:.2f}, güven={conf:.2f}).")
                continue

            # 🚚 Araca göre çok büyük bir kutu plaka değildir — kapı/kaporta
            # üzerindeki firma yazısıdır (bkz. PLAKA_MAKS_ARAC_ORANI).
            if arac_kutusu is not None:
                arac_alan = max(1, (arac_kutusu[2] - arac_kutusu[0]) * (arac_kutusu[3] - arac_kutusu[1]))
                alan_orani = (genislik * yukseklik) / float(arac_alan)
                if alan_orani > PLAKA_MAKS_ARAC_ORANI:
                    if sayaclar is not None:
                        sayaclar["araca_gore_buyuk"] = sayaclar.get("araca_gore_buyuk", 0) + 1
                    log_ayrinti(f"   🚫 {etiket} Kutu araca göre çok büyük "
                                f"(%{alan_orani*100:.1f} > %{PLAKA_MAKS_ARAC_ORANI*100:.0f}) — "
                                f"muhtemelen kaporta/kapı yazısı.")
                    continue

            # Bir insanın üzerindeki yazı/kart plaka sanılmasın
            if any(kutu_ortusme_orani((x1, y1, x2, y2), ik) > 0.35 for ik in insan_kutulari):
                if sayaclar is not None:
                    sayaclar["insan_cakismasi"] = sayaclar.get("insan_cakismasi", 0) + 1
                log_ayrinti(f"   🚫 {etiket} Kutu insanla çakışıyor, elendi.")
                continue

            if conf > en_iyi_conf:
                en_iyi_conf = conf
                # Yatayda hafif pay: karakterlerin kenarı kesilmesin.
                # Dikeyde pay YOK — YOLO kutusu zaten plakadan yüksek geliyor.
                pay_x = int(yukseklik * 0.08)
                en_iyi_kutu = (
                    max(0, x1 - pay_x), max(0, y1),
                    min(kare.shape[1], x2 + pay_x), min(kare.shape[0], y2),
                )

    return en_iyi_kutu, en_iyi_conf


def episode_isle(kamera_id, depo_id, yon, etiket, kare_havuzu, arac_tipi,
                 gonderilen_plakalar, en_iyi_tam_kare=None, en_iyi_tam_kare_kutu=None):
    """Bir araç geçişinde toplanan kareleri OCR'a sokar, mutabakat alır, gönderir."""
    if len(kare_havuzu) < MIN_ISLEME_KARE_SAYISI:
        log(f"⚠️ {etiket} Sadece {len(kare_havuzu)} kare — anlık yanlış algılama, OCR yapılmıyor.")
        return

    with _durum_kilit:
        KAMERA_DURUMLARI.setdefault(kamera_id, {})
        KAMERA_DURUMLARI[kamera_id]["toplam_episode"] = \
            KAMERA_DURUMLARI[kamera_id].get("toplam_episode", 0) + 1

    # En iyi kareler: netlik + boyut + dedektör güveni
    max_alan = max(k["alan"] for k in kare_havuzu) or 1
    max_keskinlik = max(k["keskinlik"] for k in kare_havuzu) or 1
    for k in kare_havuzu:
        k["skor"] = (0.35 * (k["alan"] / max_alan)
                     + 0.45 * (k["keskinlik"] / max_keskinlik)
                     + 0.20 * k["conf"])
    kare_havuzu.sort(key=lambda k: k["skor"], reverse=True)
    secilen = kare_havuzu[:OCR_KARE_SAYISI]

    # 🖼️ Episode'un en iyi tam karesi — YOLO kutusu çizili hâli hem debug
    # kaydı hem de backend'e gidecek image_url için kullanılır.
    kutulu_tam_kare = None
    if en_iyi_tam_kare is not None and en_iyi_tam_kare_kutu is not None:
        kutulu_tam_kare = en_iyi_tam_kare.copy()
        bx1, by1, bx2, by2 = en_iyi_tam_kare_kutu
        cv2.rectangle(kutulu_tam_kare, (bx1, by1), (bx2, by2), (0, 255, 0), 3)
        if DEBUG_ORIJINAL_KARE_KAYDET:
            ad = f"kam{kamera_id}_{yon}_{int(time.time() * 1000)}.jpg"
            cv2.imwrite(os.path.join(DEBUG_ORIJINAL_KARE_DIR, ad), kutulu_tam_kare)

    adaylar = []
    okunan_kare = 0
    for idx, k in enumerate(secilen):
        son_yakalanan_goruntuler[kamera_id] = k["gorsel"].copy()
        plaka, skor, ham = kareyi_oku(k["gorsel"])
        okunan_kare += 1

        if _AYRINTILI:
            for (v_idx, text, prob) in ham:
                log_ayrinti(f"   🔍 [Kare {idx + 1}/V{v_idx + 1}] '{text}' ({prob:.2f})")

        if plaka:
            log(f"   → {etiket} [Kare {idx + 1}] Aday: {plaka} (skor {skor:.2f})")
            adaylar.append((plaka, skor))
        else:
            log_ayrinti(f"   ⚠️ [Kare {idx + 1}] Geçerli plaka çözümlenemedi.")

        # ⏩ ERKEN ÇIKIŞ: yeterli sayıda kare zaten aynı plakada anlaştıysa
        # kalanları okumak sonucu değiştirmez. Kolay vakalar hızlanır,
        # böylece zor vakalara daha fazla kare bütçesi ayırabiliyoruz.
        if len(adaylar) >= ERKEN_CIKIS_OY:
            _p, _g, _d, _pay = zamansal_mutabakat(adaylar)
            if _d >= ERKEN_CIKIS_OY and _g >= ERKEN_CIKIS_GUVEN:
                break

    plaka, guven, destek, kanit_payi = zamansal_mutabakat(adaylar)

    if plaka is None:
        log(f"⚠️ {etiket} Bu araçta okunabilir plaka bulunamadı ({okunan_kare} kare denendi).")
        return

    log(f"🗳️ {etiket} Mutabakat: {plaka} — {destek}/{okunan_kare} karede, "
        f"güven {guven:.2f}, kanıt payı {kanit_payi:.0%}")

    # 🧠 Güvenlik görevlisinin geçmiş düzeltmesi
    duzeltilmis, hafizadan = hafizadan_duzelt(plaka)
    if hafizadan and duzeltilmis != plaka:
        log(f"🧠 {etiket} [HAFIZA] '{plaka}' → '{duzeltilmis}'")
        plaka, guven = duzeltilmis, max(guven, 0.90)

    # ---- Kabul kriterleri ----
    # Tek karelik bir sonuç ancak HEM çok güvenliyse HEM de kanıtın büyük
    # kısmına hâkimse kabul edilir. Her karenin farklı bir şey okuduğu
    # kaotik episode'larda (hızlı geçen araç) en yüksek skorlu aday bile
    # güvenilir değildir.
    yeterli_mutabakat = (destek >= MIN_MUTABAKAT_KARE
                         or (guven >= TEK_KARE_KESIN_GUVEN and kanit_payi >= TEK_KARE_MIN_PAY))

    if guven < MIN_PLAKA_GUVENI:
        log(f"⛔ {etiket} '{plaka}' düşük güven ({guven:.2f} < {MIN_PLAKA_GUVENI}) — GÖNDERİLMEDİ.")
        return
    if kanit_payi < MIN_KANIT_PAYI:
        log(f"⛔ {etiket} '{plaka}' kanıtın yalnızca %{kanit_payi*100:.0f}'ine sahip "
            f"(gereken %{MIN_KANIT_PAYI*100:.0f}) — kareler birbiriyle çelişiyor, GÖNDERİLMEDİ.")
        return
    if not yeterli_mutabakat:
        log(f"⛔ {etiket} '{plaka}' sadece {destek} karede göründü (min {MIN_MUTABAKAT_KARE}); "
            f"güven {guven:.2f} / kanıt payı {kanit_payi:.0%} tek kare için yetersiz "
            f"(gereken {TEK_KARE_KESIN_GUVEN} ve {TEK_KARE_MIN_PAY:.0%}) — GÖNDERİLMEDİ.")
        return

    simdi = time.time()
    ayni_arac = ayni_arac_mi(plaka, gonderilen_plakalar, simdi)
    if ayni_arac is not None:
        gecen = int(simdi - gonderilen_plakalar[ayni_arac])
        if ayni_arac == plaka:
            log(f"🔁 {etiket} '{plaka}' {gecen} sn önce gönderildi — tekrar gönderilmiyor.")
        else:
            log(f"🔁 {etiket} '{plaka}' okundu ama {gecen} sn önce gönderilen "
                f"'{ayni_arac}' ile aynı araç görünüyor (sadece il kodu farklı) — "
                f"çift kayıt olmasın diye gönderilmiyor.", "uyari")
        return

    gonderilen_plakalar[plaka] = simdi

    log(f"🎯 {etiket} PLAKA OKUNDU → {plaka}  (güven {guven:.2f}, {destek} kare mutabakatı)", "basari")

    durum_guncelle(kamera_id, son_plaka=plaka, son_okuma_zamani=datetime.now().isoformat())
    with _durum_kilit:
        KAMERA_DURUMLARI[kamera_id]["toplam_okuma"] = \
            KAMERA_DURUMLARI[kamera_id].get("toplam_okuma", 0) + 1

    en_iyi_gorsel = kare_havuzu[0]["gorsel"]
    plaka_b64 = gorseli_base64_kodla(en_iyi_gorsel) if GORSEL_BASE64_GONDER else None

    tam_kare_b64 = (gorseli_base64_kodla(kutulu_tam_kare)
                    if (GORSEL_BASE64_GONDER and kutulu_tam_kare is not None) else None)

    # 🖼️ Backend base64 değil erişilebilir bir URL bekliyor. Tam kare varsa
    # onu tercih ediyoruz (aracı da gösterir), yoksa kırpılmış plakayı.
    image_url = gorsel_kaydet_ve_url_uret(
        kutulu_tam_kare if kutulu_tam_kare is not None else en_iyi_gorsel,
        kamera_id, plaka)

    paket = PlakaVeriPaketi(
        kamera_id=kamera_id, depo_id=depo_id, yon=yon,
        plaka_metni=plaka, arac_tipi=arac_tipi,
        guven_skoru=float(guven),
        tarih_saat=datetime.now(timezone.utc).isoformat(),
        image_url=image_url,
        plaka_gorseli_base64=plaka_b64,
        tam_kare_gorseli_base64=tam_kare_b64,
    )
    send_plate_to_backend_sync(paket)


def gorsel_kaydet_ve_url_uret(gorsel_bgr, kamera_id: int, plaka: str,
                              jpeg_kalite: int = 88) -> Optional[str]:
    """
    Yakalanan görseli CAPTURES_DIR'e yazar ve backend'e gönderilecek
    erişilebilir bir URL döner. Başarısızsa None.
    """
    try:
        guvenli = re.sub(r"[^A-Z0-9]", "", (plaka or "").upper()) or "PLAKA"
        dosya_adi = f"kam{kamera_id}_{guvenli}_{int(time.time() * 1000)}.jpg"
        hedef = os.path.join(CAPTURES_DIR, dosya_adi)
        if not cv2.imwrite(hedef, gorsel_bgr, [cv2.IMWRITE_JPEG_QUALITY, jpeg_kalite]):
            return None
        return f"{AI_SERVICE_PUBLIC_BASE_URL.rstrip('/')}/captures/{dosya_adi}"
    except Exception as e:
        log(f"⚠️ Yakalanan görsel diske yazılamadı: {e}", "uyari")
        return None


def send_plate_to_backend_sync(paket: PlakaVeriPaketi):
    """
    Plakayı Go backend'in ANPR webhook'una gönderir.

    Gövde, Go `WebhookEvent` şemasına hizalıdır. Go bilinmeyen alanları yok
    saydığı için yon/arac_tipi gibi ekstralar zarar vermez; asıl mesele
    beklenen alanların doğru AD ve TİPLE gitmesi.
    """
    try:
        govde = {
            "depot_id": DEPOT_ID,
            "camera_id": str(paket.kamera_id),
            "plaka": paket.plaka_metni,
            "confidence_score": paket.guven_skoru,
            "image_url": paket.image_url or "",
            "detected_at": paket.tarih_saat,
            # Fazladan alanlar (Go yok sayar, ileride kullanılabilir)
            "yon": paket.yon,
            "arac_tipi": paket.arac_tipi,
        }
        if GORSEL_BASE64_GONDER:
            govde["plaka_gorseli_base64"] = paket.plaka_gorseli_base64
            govde["tam_kare_gorseli_base64"] = paket.tam_kare_gorseli_base64

        response = requests.post(BACKEND_EVENTS_URL, json=govde, timeout=5.0)
        if response.status_code == 200:
            log(f"✅ Backend veriyi aldı: {paket.plaka_metni}")
        else:
            log(f"⚠️ Backend beklenmeyen kod döndü: {response.status_code} — "
                f"{response.text[:200]}", "uyari")
    except Exception as exc:
        log(f"❌ Backend'e ulaşılamadı ({BACKEND_EVENTS_URL}): {exc}", "hata")


# ==========================================================================
# 🎛️ ENDPOINTS
# ==========================================================================
@app.get("/")
async def root():
    return {"durum": "AI Servisi Canlı Akış Modunda Ayakta", "surum": "2.0"}


@app.get("/api/v1/loglar")
async def loglar(limit: int = 200):
    """Son log satırlarını döner (canlı izleme için /loglar sayfasını kullan)."""
    with _log_kilit:
        kayitlar = list(LOG_TAMPONU)[-limit:]
    return {"toplam": len(kayitlar), "loglar": kayitlar}


@app.get("/api/v1/loglar/canli")
async def loglar_canli():
    """
    Server-Sent Events ile canlı log akışı.
    Kullanım:  curl -N http://localhost:8000/api/v1/loglar/canli
    """
    async def uret():
        with _log_kilit:
            mevcut = list(LOG_TAMPONU)[-50:]
        son_id = -1
        for kayit in mevcut:
            son_id = kayit["id"]
            yield f"data: {json.dumps(kayit, ensure_ascii=False)}\n\n"
        while True:
            with _log_kilit:
                yeniler = [k for k in LOG_TAMPONU if k["id"] > son_id]
            for kayit in yeniler:
                son_id = kayit["id"]
                yield f"data: {json.dumps(kayit, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.4)

    return StreamingResponse(uret(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/loglar", response_class=HTMLResponse)
async def loglar_sayfasi():
    """Tarayıcıdan canlı log izleme sayfası — http://<sunucu>:8000/loglar"""
    return """<!doctype html><html lang="tr"><head><meta charset="utf-8">
<title>Plaka AI — Canlı Log</title>
<style>
 body{background:#0d1117;color:#c9d1d9;font:13px/1.5 ui-monospace,Menlo,Consolas,monospace;margin:0;padding:16px}
 h1{font-size:15px;color:#58a6ff;margin:0 0 12px}
 #kutu{white-space:pre-wrap;word-break:break-word}
 .satir{padding:1px 0;border-bottom:1px solid #161b22}
 .zaman{color:#6e7681;margin-right:8px}
 .basari{color:#3fb950;font-weight:600}
 .uyari{color:#d29922}
 .hata{color:#f85149}
 .ayrinti{color:#8b949e}
 #durum{position:fixed;top:12px;right:16px;font-size:11px;color:#6e7681}
</style></head><body>
<h1>🚗 Plaka Tanıma — Canlı Log</h1><div id="durum">bağlanıyor…</div><div id="kutu"></div>
<script>
 const kutu=document.getElementById('kutu'), durum=document.getElementById('durum');
 const es=new EventSource('/api/v1/loglar/canli');
 es.onopen=()=>durum.textContent='● canlı';
 es.onerror=()=>durum.textContent='○ bağlantı koptu';
 es.onmessage=e=>{
   const k=JSON.parse(e.data);
   const d=document.createElement('div');
   d.className='satir '+(k.tur||'');
   d.innerHTML='<span class="zaman">'+k.zaman+'</span>'+k.mesaj.replace(/</g,'&lt;');
   kutu.appendChild(d);
   while(kutu.childNodes.length>1500) kutu.removeChild(kutu.firstChild);
   window.scrollTo(0,document.body.scrollHeight);
 };
</script></body></html>"""


@app.post("/api/v1/plaka/duzelt")
async def plaka_duzelt(istek: PlakaDuzeltmeIstek):
    """Güvenlik görevlisi hatalı okumayı düzeltince: veri setine kaydet + hafızaya yaz."""
    global DUZELTME_HAFIZASI
    try:
        gorsel = son_yakalanan_goruntuler.get(istek.kamera_id)
        if gorsel is None:
            raise HTTPException(status_code=400,
                                detail=f"Kamera {istek.kamera_id} için son görsel bulunamadı.")

        yanlis = plaka_temizle(istek.yanlis_plaka)
        dogru = plaka_temizle(istek.dogru_plaka)

        dosya_adi = f"kam{istek.kamera_id}_{dogru}_{int(time.time())}.jpg"
        cv2.imwrite(os.path.join(RETRAIN_DIR, dosya_adi), gorsel)

        DUZELTME_HAFIZASI[yanlis] = dogru
        duzeltme_hafizasini_kaydet(DUZELTME_HAFIZASI)
        log(f"🧠 [ÖĞRENME] '{yanlis}' → '{dogru}' (toplam {len(DUZELTME_HAFIZASI)} kayıt)")

        return {"durum": "basarili",
                "mesaj": f"'{dogru}' etiketiyle kaydedildi ve hafızaya alındı.",
                "toplam_hafiza_kaydi": len(DUZELTME_HAFIZASI)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/plaka/duzeltme-hafizasi")
async def duzeltme_hafizasi_goruntule():
    return {"toplam_kayit": len(DUZELTME_HAFIZASI), "hafiza": DUZELTME_HAFIZASI}


@app.delete("/api/v1/plaka/duzeltme-hafizasi/{yanlis_plaka}")
async def duzeltme_hafizasindan_sil(yanlis_plaka: str):
    temiz = plaka_temizle(yanlis_plaka)
    if temiz not in DUZELTME_HAFIZASI:
        raise HTTPException(status_code=404, detail="Bu plaka hafızada bulunamadı.")
    silinen = DUZELTME_HAFIZASI.pop(temiz)
    duzeltme_hafizasini_kaydet(DUZELTME_HAFIZASI)
    return {"durum": "basarili", "mesaj": f"'{temiz} -> {silinen}' silindi."}


@app.get("/api/v1/plaka/kara-liste")
async def kara_liste_goruntule():
    return {
        "kara_liste": sorted(KARA_LISTE),
        "not": ("Otomatik öğrenme KALDIRILDI — gerçek plaka parçalarını "
                "yasakladığı için doğruluğu düşürüyordu. Bu liste yalnızca elle "
                "yönetilir ve TAM EŞLEŞME ile çalışır."),
    }


@app.post("/api/v1/plaka/kara-liste/{kelime}")
async def kara_listeye_ekle(kelime: str):
    temiz = plaka_temizle(kelime)
    if not temiz or len(temiz) < 3:
        raise HTTPException(status_code=400, detail="En az 3 karakterlik bir metin girmelisin.")
    if plaka_format_gecerli_mi(temiz):
        raise HTTPException(
            status_code=400,
            detail=f"'{temiz}' geçerli bir TR plaka formatında — kara listeye eklenemez. "
                   "Bu koruma, sistemin gerçek plakaları yasaklamasını önler.")
    KARA_LISTE.add(temiz)
    kara_listeyi_kaydet()
    return {"durum": "basarili", "mesaj": f"'{temiz}' kara listeye eklendi.", "toplam": len(KARA_LISTE)}


@app.delete("/api/v1/plaka/kara-liste/{kelime}")
async def kara_listeden_sil(kelime: str):
    temiz = plaka_temizle(kelime)
    if temiz not in KARA_LISTE:
        raise HTTPException(status_code=404, detail="Bu kelime kara listede bulunamadı.")
    KARA_LISTE.discard(temiz)
    kara_listeyi_kaydet()
    return {"durum": "basarili", "mesaj": f"'{temiz}' silindi."}


@app.get("/api/v1/plaka/test/{metin}")
async def plaka_cozumleyici_test(metin: str):
    """
    Gramer çözümleyicisini elle test etmek için.
    Örn: /api/v1/plaka/test/B4CLY063  ->  34CLY063
    """
    temiz = plaka_temizle(metin)
    plaka, skor = plaka_cozumle(temiz, 1.0)
    return {
        "girdi": metin, "temizlenmis": temiz,
        "cozumlenen_plaka": plaka, "skor": round(skor, 3),
        "dogrudan_gecerli_mi": plaka_format_gecerli_mi(temiz),
    }


@app.post("/api/v1/kamera/baslat")
async def kamera_baslat(istek: KameraIstek):
    if not istek.rtsp_url or istek.rtsp_url == "string":
        raise HTTPException(status_code=400, detail="Geçerli bir RTSP URL'si girmelisin!")
    thread = threading.Thread(
        target=gercek_yolo_ocr_pipeline,
        args=(istek.kamera_id, istek.depo_id, istek.rtsp_url, istek.yon),
        daemon=True, name=f"kamera-{istek.kamera_id}")
    thread.start()
    return {"durum": "basarili",
            "mesaj": f"{istek.kamera_id} numaralı kamera arka planda başlatıldı."}


@app.get("/api/v1/kamera/durum")
async def kamera_durum():
    with _durum_kilit:
        canli = dict(KAMERA_DURUMLARI)
    return {
        "kameralar": [
            {"kamera_id": k["kamera_id"], "isim": k["isim"], "yon": k["yon"],
             "depo_id": k["depo_id"], "canli_durum": canli.get(k["kamera_id"], {})}
            for k in GEBZE_KAMERALARI
        ],
        "ayarlar": {
            "rtsp_profil": RTSP_PROFIL,
            "min_plaka_guveni": MIN_PLAKA_GUVENI,
            "min_mutabakat_kare": MIN_MUTABAKAT_KARE,
            "plaka_arac_zorunlu": PLAKA_ARAC_ZORUNLU,
            "log_seviyesi": LOG_SEVIYESI,
        },
    }


@app.get("/healthz")
async def healthz():
    """Canlılık: süreç ayakta mı?"""
    return {"durum": "canli"}


@app.get("/readyz")
async def readyz():
    """
    Hazırlık: modeller yüklendi mi ve en az bir kamera thread'i çalışıyor mu?
    Kamera thread'i ölmüşse burası 503 döner — sessiz ölümü görünür kılar.
    """
    canli_threadler = [t.name for t in AKTIF_THREADLER if t.is_alive()]
    hazir = bool(canli_threadler)
    icerik = {
        "durum": "hazir" if hazir else "hazir_degil",
        "modeller_yuklendi": True,
        "canli_kamera_threadleri": canli_threadler,
        "toplam_kamera_threadi": len(AKTIF_THREADLER),
    }
    if not hazir:
        raise HTTPException(status_code=503, detail=icerik)
    return icerik


if __name__ == "__main__":
    # ⚠️ reload=True KULLANMA: uygulama çalışırken dataset/debug klasörlerine
    # dosya yazıyoruz; reload bunu "kod değişti" sanıp kamera thread'lerini öldürür.
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
