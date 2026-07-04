FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# build the index at image-build time so the container starts ready to serve.
# (downloads the embedding model once; baked into the image.)
RUN python -m scripts.build_index

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
