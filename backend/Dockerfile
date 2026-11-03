# Multi-stage: wheels are built once in a throwaway layer so the runtime image
# carries no compiler toolchain.
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# pdfplumber needs these at runtime for image-backed pages.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libjpeg62-turbo zlib1g curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels

# Non-root: the container scrapes third-party sites and parses untrusted PDFs,
# so it should not be running as uid 0.
RUN useradd --create-home --uid 1000 finn
WORKDIR /app
COPY --chown=finn:finn . .
RUN mkdir -p /app/data/cache && chown -R finn:finn /app/data
USER finn

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/admin/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]