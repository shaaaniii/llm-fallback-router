"""
PHASE 5 — Distributed tracing with OpenTelemetry.

A "trace" follows one request across every component it touches. Right
now that's just this one service, but the value compounds the moment you
add a second service (a queue, another microservice) — traces stitch
their spans together into one timeline, which is otherwise nearly
impossible to reconstruct from separate log files.

Exporter choice:
  - No OTEL_EXPORTER_OTLP_ENDPOINT set -> spans print to console. Zero
    setup, lets you SEE tracing working immediately.
  - OTEL_EXPORTER_OTLP_ENDPOINT set -> spans ship to a real collector
    (Jaeger, Honeycomb, Grafana Tempo, etc.) via OTLP. docker-compose
    does not include a collector by default (out of scope for a portfolio
    project) — point this at any OTLP-compatible backend you stand up.
"""

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.config import settings


def configure_tracing(app: FastAPI) -> None:
    if not settings.OTEL_ENABLED:
        return

    resource = Resource(attributes={SERVICE_NAME: "llm-fallback-router"})
    provider = TracerProvider(resource=resource)

    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)


def get_tracer():
    return trace.get_tracer("llm-fallback-router")