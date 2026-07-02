# Stage 1: Install Python dependencies only
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production runtime
FROM python:3.11-slim-bookworm AS runtime

RUN groupadd -r dxfvec && useradd -r -g dxfvec -d /app -s /sbin/nologin dxfvec

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder --chown=dxfvec:dxfvec /install /usr/local

COPY --chown=dxfvec:dxfvec src/ src/
COPY --chown=dxfvec:dxfvec pyproject.toml .

USER dxfvec

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PORT=5000 \
    FLASK_DEBUG=0 \
    MAX_IMAGE_DIM=2048 \
    DOWNLOAD_TTL=3600

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/ping || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "dxfvec.web:app"]
