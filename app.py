"""Thin entrypoint for uvicorn: uvicorn app:app"""
from app.main import app

__all__ = ["app"]
