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

# Bağımlılık listesini kopyalayıp kuruyoruz
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 && \
    pip install --no-cache-dir -r requirements.txt

# Yapay zeka modellerinin Docker her açıldığında sıfordat inmesini engellemek için önbellek dizinleri
ENV YOLO_CONFIG_DIR=/app/.ultralytics
ENV EASYOCR_MODULE_DATA_DIR=/app/.easyocr
ENV CUDA_HOME=/usr/local/cuda
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
ENV PATH=$CUDA_HOME/bin:$PATH

# Proje dosyalarını içeri aktar
COPY . .

EXPOSE 8000

CMD ["python", "main.py"]