# ---- Backend for Hugging Face Spaces (FastAPI) ----
FROM python:3.10-slim

# (faiss wheel works on slim; build-essential is nice-to-have)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend deps
COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy backend code
COPY apps/api /app

# Default env (HF Spaces will inject HF_TOKEN secret)
ENV DATA_DIR=/data \
    INDEX_DIR=/data/index \
    EMBED_PROVIDER=hf_api \
    MODEL_EMBED=sentence-transformers/all-MiniLM-L6-v2 \
    LLM_PROVIDER=hf \
    MODEL_LLM=mistralai/Mistral-7B-Instruct

EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
