# syntax=docker/dockerfile:1.7
# ---------- builder ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

WORKDIR /build

# Runtime deps (all ship manylinux wheels — no compiler needed)
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# onnx is only needed to generate the demo model at build time
RUN pip install --prefix=/install onnx==1.17.0

# Generate the demo ONNX model (script writes to /app/model.onnx)
RUN mkdir -p /app
COPY generate_model.py .
RUN PYTHONPATH=/install/lib/python3.12/site-packages python generate_model.py

# ---------- runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/install/bin:${PATH}" \
    PYTHONPATH="/install/lib/python3.12/site-packages" \
    MODEL_PATH=/app/model.onnx \
    INPUT_SHAPE=1,4

WORKDIR /app

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy installed Python packages from builder (onnxruntime + fastapi etc., no onnx/compiler)
COPY --from=builder /install /install

# Copy application code and pre-generated model
COPY app.py ./
COPY --from=builder /app/model.onnx /app/model.onnx

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=6 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8001/health', timeout=3).status==200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]