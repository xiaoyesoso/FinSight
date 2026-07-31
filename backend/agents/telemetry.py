"""OpenTelemetry environment factory for the Claude Agent SDK.

The Claude Code CLI subprocess has built-in OTel instrumentation. The SDK only
needs the right environment variables (passed via ``ClaudeAgentOptions.env``)
to export traces / metrics / log events to any OTLP backend (Jaeger,
Prometheus, Grafana) without touching business logic.

This module produces that env dict via ``build_otel_env()``. It is merged into
every ``ClaudeAgentOptions`` by ``_build_options()`` so fresh / resume / fork
runs share one telemetry configuration.

Security note: content-level flags (``OTEL_LOG_USER_PROMPTS``,
``OTEL_LOG_TOOL_DETAILS``, ``OTEL_LOG_TOOL_CONTENT``, ``OTEL_LOG_RAW_API_BODIES``)
are deliberately NOT set here. Default exports carry structure only: durations,
model names, tool names and token counts. Financial-PDF content, search keywords
and internal file paths are sensitive and must not leave the host without a
security review of the telemetry pipeline. The local JSONL audit log
(``backend/data/audit_log.jsonl``) already covers content-level compliance needs.

Never set an exporter to ``console`` - it hijacks the SDK<->CLI stdio control
channel and breaks the run. Local debugging uses a local collector (Jaeger
all-in-one) instead.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from backend.config import settings

logger = logging.getLogger(__name__)


def build_otel_env(
    service_name: str = "iiras",
    enduser_id: str = "",
    tenant_id: str = "",
) -> dict[str, str]:
    """Build the OpenTelemetry env dict for ``ClaudeAgentOptions.env``.

    Returns an empty dict when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is unset, so
    telemetry is opt-in and never blocks a run.

    Args:
        service_name: Name shown in Jaeger / Grafana (``OTEL_SERVICE_NAME``).
        enduser_id:   Analyst identifier for per-user cost attribution
                      (placed in ``OTEL_RESOURCE_ATTRIBUTES`` as ``enduser.id``).
        tenant_id:    Team / tenant identifier for per-tenant cost rollups
                      (placed in ``OTEL_RESOURCE_ATTRIBUTES`` as ``tenant.id``).

    Attribution values are percent-encoded so commas / spaces / equals signs
    do not corrupt the attributes string.
    """
    endpoint = settings.otel_exporter_otlp_endpoint
    if not endpoint:
        # Telemetry disabled: no env injected, run proceeds normally.
        return {}

    # Resource attributes: service version, deployment environment, and
    # optional user/tenant labels for cost attribution.
    attrs = [
        "service.version=1.0.0",
        "deployment.environment=development",
    ]
    if enduser_id:
        attrs.append(f"enduser.id={quote(enduser_id)}")
    if tenant_id:
        attrs.append(f"tenant.id={quote(tenant_id)}")

    env: dict[str, str] = {
        # Master switch - required for any signal to be exported.
        "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
        # Beta gate: traces need this additional flag (still beta in the CLI).
        "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA": "1",
        # Exporter selection: all three signals use OTLP (never "console").
        "OTEL_TRACES_EXPORTER": "otlp",
        "OTEL_METRICS_EXPORTER": "otlp",
        "OTEL_LOGS_EXPORTER": "otlp",
        # OTLP transport: HTTP/protobuf is firewall-friendly and simple.
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        "OTEL_EXPORTER_OTLP_ENDPOINT": endpoint,
        # Service identity and resource attributes for filtering in backends.
        "OTEL_SERVICE_NAME": service_name,
        "OTEL_RESOURCE_ATTRIBUTES": ",".join(attrs),
        # Short-lived CLI process: lower export intervals so buffered data is
        # not lost when the process exits. CLI defaults are 60s (metrics) and
        # 5s (traces/logs); we set all to 1 second.
        "OTEL_METRIC_EXPORT_INTERVAL": "1000",
        "OTEL_LOGS_EXPORT_INTERVAL": "1000",
        "OTEL_TRACES_EXPORT_INTERVAL": "1000",
    }

    # Optional authentication header for cloud-hosted collectors.
    if settings.otel_exporter_otlp_headers:
        env["OTEL_EXPORTER_OTLP_HEADERS"] = settings.otel_exporter_otlp_headers

    logger.info(
        "Telemetry enabled: service=%s endpoint=%s user=%s tenant=%s",
        service_name,
        endpoint,
        enduser_id or "(none)",
        tenant_id or "(none)",
    )
    return env
