import logging
import logging.config

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from prometheus_fastapi_instrumentator import Instrumentator

from app.routes.users import router

# ── Structured JSON logging ────────────────────────────────────────────────────
logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.json.JsonFormatter",
                "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
            }
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "json",
            }
        },
        "root": {"level": "INFO", "handlers": ["stdout"]},
    }
)

# ── OpenTelemetry tracing ──────────────────────────────────────────────────────
# TracerProvider with no exporter — spans are generated but discarded.
# In production: swap for BatchSpanProcessor(OTLPSpanExporter(endpoint=...))
# pointed at Jaeger, Tempo, or Datadog.  One-line change.
provider = TracerProvider()
trace.set_tracer_provider(provider)

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Prima SRE Tech Challenge API",
    description="User management API backed by DynamoDB and S3.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# ── Prometheus metrics — exposes /metrics ──────────────────────────────────────
Instrumentator().instrument(app).expose(app)

# ── OpenTelemetry FastAPI instrumentation ──────────────────────────────────────
FastAPIInstrumentor.instrument_app(app)


@app.get("/health", tags=["ops"], summary="Health check")
async def health_check() -> dict:
    return {"status": "healthy"}
