# ── Stage 1: dependency builder ────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Create a virtual environment so paths are self-contained and unambiguous
RUN python -m venv /venv

COPY requirements.txt .
RUN /venv/bin/pip install --no-cache-dir -r requirements.txt


# ── Stage 2: production image ───────────────────────────────────────────────
FROM python:3.12-slim

# Security: run as a dedicated non-root user
RUN groupadd -r appuser && \
    useradd -r -g appuser -d /app -s /sbin/nologin -c "App user" appuser

WORKDIR /app

# Copy the entire venv from the builder — all scripts and packages stay consistent
COPY --from=builder /venv /venv

# Copy application source
COPY app/ ./app/

RUN chown -R appuser:appuser /app

USER appuser

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD /venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["/venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
