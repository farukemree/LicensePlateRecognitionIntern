FROM python:3.10-slim

WORKDIR /app

# Yeni Debian standartlarına uygun libgl1 ve libglib kütüphaneleri lo
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Önce bağımlılık listesini kopyalayıp kuruyoruz (Önbellek avantajı için)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Yapay zeka modellerinin Docker her açıldığında sıfordat inmesini engellemek için önbellek dizinleri
ENV YOLO_CONFIG_DIR=/app/.ultralytics
ENV EASYOCR_MODULE_DATA_DIR=/app/.easyocr

# Proje dosyalarını içeri aktar
COPY . .

EXPOSE 8000

CMD ["python", "main.py"]