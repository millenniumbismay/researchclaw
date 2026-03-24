"""Paper Content Service — fetches and caches full paper content from source (arXiv HTML)."""

import json
import logging
import re
import time
import threading
from typing import Optional

import requests
from bs4 import BeautifulSoup

from app.config import settings
from app.utils import safe_filename

logger = logging.getLogger(__name__)

# Rate limiting for arXiv requests
_last_fetch_time = 0.0
_fetch_lock = threading.Lock()
_FETCH_DELAY = 3.0  # seconds between requests


def _rate_limit():
    """Ensure at least _FETCH_DELAY seconds between arXiv requests."""
    global _last_fetch_time
    with _fetch_lock:
        now = time.time()
        wait = _FETCH_DELAY - (now - _last_fetch_time)
        if wait > 0:
            time.sleep(wait)
        _last_fetch_time = time.time()


def _extract_arxiv_id(paper_id: str, paper_url: str = "") -> Optional[str]:
    """Extract arXiv ID from paper_id or URL."""
    # paper_id format: "arxiv:2603.19935v1"
    if paper_id.startswith("arxiv:"):
        return paper_id[6:]
    # Try URL: https://arxiv.org/abs/2603.19935v1
    m = re.search(r"arxiv\.org/abs/([^\s?#]+)", paper_url)
    if m:
        return m.group(1)
    return None


def _fetch_arxiv_html(arxiv_id: str) -> Optional[str]:
    """Fetch HTML version of an arXiv paper."""
    _rate_limit()
    url = f"https://arxiv.org/html/{arxiv_id}"
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "ResearchClaw/1.0"})
        if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
            return resp.text
        logger.info(f"arXiv HTML not available for {arxiv_id} (status {resp.status_code})")
    except Exception as e:
        logger.warning(f"Failed to fetch arXiv HTML for {arxiv_id}: {e}")
    return None


def _sanitize_html(html_content: str) -> str:
    """Remove script tags, event handlers, and other dangerous content from HTML."""
    soup = BeautifulSoup(html_content, "lxml")

    # Remove dangerous elements
    for tag in soup.find_all(["script", "style", "iframe", "object", "embed", "form"]):
        tag.decompose()

    # Remove event handler attributes (onclick, onerror, onload, etc.)
    for tag in soup.find_all(True):
        attrs_to_remove = [attr for attr in tag.attrs if attr.lower().startswith("on")]
        for attr in attrs_to_remove:
            del tag[attr]
        # Remove javascript: URLs
        if tag.get("href", "").strip().lower().startswith("javascript:"):
            tag["href"] = "#"
        if tag.get("src", "").strip().lower().startswith("javascript:"):
            del tag["src"]

    return str(soup)


def _extract_sections(html: str) -> dict[str, str]:
    """Extract key sections from arXiv HTML paper."""
    soup = BeautifulSoup(html, "lxml")
    sections = {}

    # arXiv HTML uses <section> elements with headings
    # Look for sections by heading text
    target_sections = {
        "related_work": re.compile(r"related\s+work|related\s+works|prior\s+work", re.I),
        "introduction": re.compile(r"^introduction$", re.I),
        "background": re.compile(r"^background$|^background\s+and\s+", re.I),
        "method": re.compile(r"^method|^approach|^methodology", re.I),
        "conclusion": re.compile(r"^conclusion", re.I),
    }

    # Strategy 1: Look for <section> elements
    for section_el in soup.find_all("section"):
        heading = section_el.find(re.compile(r"^h[1-6]$"))
        if not heading:
            continue
        heading_text = heading.get_text(strip=True)
        # Remove section numbers like "2." or "II."
        heading_text_clean = re.sub(r"^[\d.]+\s*", "", heading_text)
        heading_text_clean = re.sub(r"^[IVX]+\.\s*", "", heading_text_clean)

        for key, pattern in target_sections.items():
            if pattern.search(heading_text_clean) and key not in sections:
                # Get section content as HTML, excluding the heading itself
                content_parts = []
                for child in section_el.children:
                    if child == heading:
                        continue
                    if hasattr(child, "name") and child.name and re.match(r"^h[1-6]$", child.name):
                        continue
                    text = str(child).strip()
                    if text:
                        content_parts.append(text)
                if content_parts:
                    sections[key] = "\n".join(content_parts)
                break

    # Strategy 2: If no <section> elements found, try heading-based extraction
    if "related_work" not in sections:
        for heading in soup.find_all(re.compile(r"^h[1-6]$")):
            heading_text = heading.get_text(strip=True)
            heading_text_clean = re.sub(r"^[\d.]+\s*", "", heading_text)
            heading_text_clean = re.sub(r"^[IVX]+\.\s*", "", heading_text_clean)

            if target_sections["related_work"].search(heading_text_clean):
                # Collect siblings until next heading of same or higher level
                content_parts = []
                heading_level = int(heading.name[1])
                for sibling in heading.find_next_siblings():
                    if hasattr(sibling, "name") and sibling.name and re.match(r"^h[1-6]$", sibling.name):
                        sib_level = int(sibling.name[1])
                        if sib_level <= heading_level:
                            break
                    text = str(sibling).strip()
                    if text:
                        content_parts.append(text)
                if content_parts:
                    sections["related_work"] = "\n".join(content_parts)
                break

    # Sanitize all extracted sections
    return {key: _sanitize_html(val) for key, val in sections.items()}


def _content_path(paper_id: str):
    return settings.paper_content_dir / f"{safe_filename(paper_id)}.json"


def get_cached_content(paper_id: str) -> Optional[dict]:
    """Load cached paper content from disk."""
    path = _content_path(paper_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to load cached content for {paper_id}: {e}")
        return None


def get_related_work_section(paper_id: str) -> Optional[str]:
    """Get the Related Work section HTML for a paper, if cached."""
    content = get_cached_content(paper_id)
    if content and content.get("sections", {}).get("related_work"):
        return content["sections"]["related_work"]
    return None


def fetch_and_cache_paper_content(paper_id: str, paper_url: str = "") -> dict:
    """Fetch full paper content from arXiv HTML and cache locally.

    Returns the content dict with fetch_status.
    """
    # Check if already cached
    existing = get_cached_content(paper_id)
    if existing and existing.get("fetch_status") == "ok":
        return existing

    import datetime
    result = {
        "paper_id": paper_id,
        "fetched_at": datetime.datetime.utcnow().isoformat(),
        "source_url": "",
        "sections": {},
        "fetch_status": "error",
    }

    arxiv_id = _extract_arxiv_id(paper_id, paper_url)
    if not arxiv_id:
        result["fetch_status"] = "not_arxiv"
        _save_content(paper_id, result)
        return result

    result["source_url"] = f"https://arxiv.org/html/{arxiv_id}"

    html = _fetch_arxiv_html(arxiv_id)
    if not html:
        result["fetch_status"] = "no_html"
        _save_content(paper_id, result)
        return result

    sections = _extract_sections(html)
    result["sections"] = sections

    if sections.get("related_work"):
        result["fetch_status"] = "ok"
    else:
        result["fetch_status"] = "no_related_work"

    _save_content(paper_id, result)
    return result


def _save_content(paper_id: str, data: dict):
    """Save paper content to disk."""
    settings.paper_content_dir.mkdir(parents=True, exist_ok=True)
    path = _content_path(paper_id)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_content_background(paper_id: str, paper_url: str = ""):
    """Fetch paper content in a background thread."""
    t = threading.Thread(
        target=fetch_and_cache_paper_content,
        args=(paper_id, paper_url),
        daemon=True,
    )
    t.start()
