import json
import re
from pathlib import Path


def safe_filename(title: str) -> str:
    name = title.lower()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", "-", name.strip())
    name = re.sub(r"-+", "-", name)
    return name[:80].rstrip("-")


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
