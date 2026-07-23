FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

WORKDIR /app

# Python ve bağımlılıklar yükle
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3.10-dev \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Python 3.10'u varsayılan yapmak istiyorsan (opsiyonel)
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# ⚠️ KATMAN SIRASI ÖNEMLİ — büyük ve nadiren değişen bağımlılıklar önce.
#
# Eskiden `COPY requirements.txt` ile torch kurulumu TEK katmandaydı. Bu
# yüzden requirements.txt'teki tek satırlık bir değişiklik (httpx -> requests)
# bile torch + CUDA paketlerini (~4 GB) baştan indirtiyordu; yavaş bir
# bağlantıda build 5 saniye yerine ~75 dakika sürüyordu.
#
# 1) Büyük, nadiren değişen katman: pip araçları + torch/CUDA.
#    requirements.txt'e HİÇ bağlı değil, bu yüzden o dosya değişse bile
#    önbellekten gelir.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch torchvision torchaudio \
        --index-url https://download.pytorch.org/whl/cu124

# 2) Küçük, sık değişen katman: proje bağımlılıkları.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Yapay zeka modellerinin Docker her açıldığında sıfordat inmesini engellemek için önbellek dizinleri
ENV YOLO_CONFIG_DIR=/app/.ultralytics
ENV EASYOCR_MODULE_DATA_DIR=/app/.easyocr
# 🩹 Canlı log akışı için: Python'un stdout/stderr'i bloklar halinde değil
# satır satır anında flush etmesini garanti eder (bkz. main.py'deki
# sys.stdout.reconfigure ile aynı amaç, iki katmanlı güvence).
ENV PYTHONUNBUFFERED=1
ENV CUDA_HOME=/usr/local/cuda
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
ENV PATH=$CUDA_HOME/bin:$PATH

# Proje dosyalarını içeri aktar
COPY . .

EXPOSE 8000

CMD ["python", "main.py"]