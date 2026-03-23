"""ResearchClaw UI — shim that re-exports the modular app.

start_ui.sh runs: uvicorn ui:app --host 0.0.0.0 --port 7337 --reload
This shim keeps that working while the real app lives in app/.
"""
from app.main import app  # noqa: F401

__all__ = ["app"]
