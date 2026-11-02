# Service d'analyse de document (document-analysis/api.py).
# CPU par défaut ; carte NVIDIA : --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu126
FROM python:3.13-slim

ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models \
    OCR_HOST=0.0.0.0 \
    OCR_PORT=8501

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.14.1 torchvision==0.29.1 --index-url ${TORCH_INDEX} \
    && pip install --no-cache-dir -r requirements.txt

COPY *.py ./

# Le modèle (~7,5 Go) est téléchargé au premier démarrage dans /models : monter un volume pour le garder
VOLUME /models
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/health', timeout=4)"
CMD ["python", "api.py"]
