"""Status API — FastAPI micro-endpoints for source management and health.

Provides REST endpoints for querying connector status, managing tokens,
and integrating with the NKZ-BioOrchestrator frontend module.

Usage standalone:
    uvicorn ikerketa.api:app --port 8420

Usage as hook:
    from ikerketa.api import app as ikerketa_api
    main_app.mount("/ikerketa", ikerketa_api)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    raise ImportError(
        "FastAPI not installed. Add 'fastapi[standard]' to dependencies: "
        "pip install 'fastapi[standard]'"
    )

from ikerketa.config import load_sources_config, settings
from ikerketa.logging_setup import get_logger
from ikerketa.models.base import DataSource

_log = get_logger(__name__)

app = FastAPI(
    title="IkerKeta Status API",
    description="Source connector status and pipeline health for NKZ-BioOrchestrator",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _get_source_status(source_key: str, source_config: dict) -> dict[str, Any]:
    """Build status dict for a single source."""
    # Check for required env vars / API keys
    credential_status = "ok"
    credential_field = source_config.get("credential_env_var")
    if credential_field:
        import os
        if not os.getenv(credential_field):
            credential_status = "missing"

    # Check for local data file
    data_file = source_config.get("data_file")
    data_available = False
    if data_file:
        data_available = Path(data_file).exists()
    else:
        # API-based sources don't need local files
        data_available = True

    # Check for exported output
    output_files = []
    processed_dir = settings.data_processed_dir
    if processed_dir.exists():
        for ext in ("jsonld", "parquet"):
            p = processed_dir / f"{source_key}_entities.{ext}"
            if p.exists():
                output_files.append({
                    "format": ext,
                    "path": str(p),
                    "size_bytes": p.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        p.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                })

    return {
        "key": source_key,
        "name": source_config.get("name", source_key),
        "domain": source_config.get("domain", "agriculture"),
        "enabled": source_config.get("enabled", True),
        "type": source_config.get("type", "unknown"),
        "credential_status": credential_status,
        "data_available": data_available,
        "outputs": output_files,
        "status": "ready" if (credential_status == "ok" and data_available) else "unavailable",
    }


@app.get("/api/v1/health")
async def health() -> dict[str, Any]:
    """Pipeline health check."""
    config = load_sources_config()
    sources = config.get("sources", {})
    enabled = sum(1 for v in sources.values() if v.get("enabled", True))

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
        "sources_configured": len(sources),
        "sources_enabled": enabled,
        "data_dirs": {
            "raw": str(settings.data_raw_dir),
            "processed": str(settings.data_processed_dir),
            "reports": str(settings.data_reports_dir),
        },
    }


@app.get("/api/v1/sources")
async def list_sources() -> dict[str, Any]:
    """List all configured data sources with status."""
    config = load_sources_config()
    sources = config.get("sources", {})

    source_list = []
    for key, cfg in sources.items():
        source_list.append(_get_source_status(key, cfg))

    # Group by domain
    domains: dict[str, list] = {}
    for s in source_list:
        domain = s.get("domain", "other")
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(s)

    ready = sum(1 for s in source_list if s["status"] == "ready")

    return {
        "total": len(source_list),
        "ready": ready,
        "unavailable": len(source_list) - ready,
        "by_domain": domains,
        "sources": source_list,
    }


@app.get("/api/v1/sources/{source_key}")
async def get_source(source_key: str) -> dict[str, Any]:
    """Get detailed status of a single source."""
    config = load_sources_config()
    sources = config.get("sources", {})

    if source_key not in sources:
        raise HTTPException(status_code=404, detail=f"Source '{source_key}' not found")

    return _get_source_status(source_key, sources[source_key])


@app.get("/api/v1/reports/latest")
async def latest_report() -> dict[str, Any]:
    """Return the latest quality report."""
    import json

    reports_dir = settings.data_reports_dir
    if not reports_dir.exists():
        raise HTTPException(status_code=404, detail="No reports found")

    reports = sorted(reports_dir.glob("quality_report_*.json"), reverse=True)
    if not reports:
        raise HTTPException(status_code=404, detail="No reports found")

    with reports[0].open() as f:
        return json.load(f)
