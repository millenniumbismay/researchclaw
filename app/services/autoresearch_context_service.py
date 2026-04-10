"""AutoResearch Context Service — paper content + GitHub repo analysis pipeline."""

import asyncio
import datetime
import json
import logging
import re
import subprocess
import threading
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.autoresearch import PaperContext, RepoAnalysis
from app.services import autoresearch_project_service as project_svc
from app.services.paper_service import get_paper_by_id
from app.services.paper_content_service import (
    fetch_and_cache_paper_content,
    get_cached_content,
)

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"

# Track in-progress context builds
_building: set[str] = set()
_lock = threading.Lock()

# Progress tracking per project
_progress: dict[str, str] = {}


def get_build_status(project_id: str) -> str:
    with _lock:
        if project_id in _building:
            return "building"
    state = project_svc.get_project(project_id)
    if state is None:
        return "not_found"
    if state.paper_contexts:
        return "ready"
    return "idle"


def get_build_progress(project_id: str) -> Optional[str]:
    with _lock:
        return _progress.get(project_id)


# ============================================================
# arXiv paper fetching for manual URLs
# ============================================================

def _extract_arxiv_id_from_url(url: str) -> Optional[str]:
    """Extract arXiv ID from a URL like https://arxiv.org/abs/2401.12345."""
    m = re.search(r"arxiv\.org/(?:abs|pdf|html)/([^\s?#/]+)", url)
    if m:
        return m.group(1)
    return None


def fetch_paper_by_url(arxiv_url: str) -> Optional[dict]:
    """Fetch paper metadata from arXiv API for a paper not in MyList.

    Returns a dict compatible with paper_service format, or None on failure.
    """
    arxiv_id = _extract_arxiv_id_from_url(arxiv_url)
    if not arxiv_id:
        return None

    paper_id = f"arxiv:{arxiv_id}"

    # Check if already in papers cache
    existing = get_paper_by_id(paper_id)
    if existing:
        return existing

    # Fetch from arXiv Atom API
    try:
        import requests
        api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
        resp = requests.get(api_url, timeout=15, headers={"User-Agent": "ResearchClaw/1.0"})
        if resp.status_code != 200:
            logger.warning(f"arXiv API returned {resp.status_code} for {arxiv_id}")
            return None

        from xml.etree import ElementTree
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ElementTree.fromstring(resp.text)
        entry = root.find("atom:entry", ns)
        if entry is None:
            return None

        title = (entry.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
        abstract = (entry.findtext("atom:summary", "", ns) or "").strip().replace("\n", " ")
        authors = [
            a.findtext("atom:name", "", ns).strip()
            for a in entry.findall("atom:author", ns)
        ]
        published = (entry.findtext("atom:published", "", ns) or "")[:10]

        return {
            "id": paper_id,
            "title": title,
            "authors": authors,
            "date": published,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "abstract": abstract,
            "source": "arxiv",
            "tags": [],
            "confidence": 0,
            "relevance_score": 0.0,
            "summary": "",
            "has_summary": False,
        }
    except Exception as e:
        logger.error(f"Failed to fetch arXiv metadata for {arxiv_id}: {e}")
        return None


# ============================================================
# GitHub repo cloning and analysis
# ============================================================

_EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", ".eggs", "dist", "build", ".mypy_cache"}
_EXCLUDE_EXTS = {".pyc", ".pyo", ".so", ".o", ".a", ".dylib", ".egg-info"}

_LANG_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".java": "java", ".cpp": "c++", ".c": "c", ".h": "c/c++ header",
    ".rs": "rust", ".go": "go", ".rb": "ruby", ".jl": "julia",
    ".r": "r", ".R": "r", ".ipynb": "jupyter",
}


def _repo_name_from_url(url: str) -> str:
    """Extract repo name from GitHub URL."""
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url.split("/")[-1]


def _validate_github_url(url: str) -> bool:
    return bool(re.fullmatch(r"https?://github\.com/[\w.-]+/[\w.-]+/?", url))


def _clone_repo(url: str, dest: Path) -> bool:
    """Shallow clone a GitHub repo."""
    if dest.exists():
        logger.info(f"Repo already cloned at {dest}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error(f"git clone failed: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"git clone timed out for {url}")
        return False
    except Exception as e:
        logger.error(f"git clone error: {e}")
        return False


def _build_directory_tree(root: Path, max_depth: int = 4, prefix: str = "") -> str:
    """Build a text directory tree, excluding common non-source dirs."""
    lines = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return ""

    dirs = [e for e in entries if e.is_dir() and e.name not in _EXCLUDE_DIRS]
    files = [e for e in entries if e.is_file() and e.suffix not in _EXCLUDE_EXTS and not e.name.startswith(".")]

    for f in files[:30]:  # Cap files per directory
        lines.append(f"{prefix}{f.name}")

    if len(files) > 30:
        lines.append(f"{prefix}... ({len(files) - 30} more files)")

    for d in dirs[:20]:  # Cap dirs
        lines.append(f"{prefix}{d.name}/")
        if max_depth > 1:
            sub = _build_directory_tree(d, max_depth - 1, prefix + "  ")
            if sub:
                lines.append(sub)

    return "\n".join(lines)


def _identify_key_files(root: Path) -> list[Path]:
    """Identify the most important source files in a repo."""
    priority_names = {"README.md", "readme.md", "README.rst", "setup.py", "pyproject.toml",
                      "requirements.txt", "Makefile", "main.py", "app.py", "train.py",
                      "model.py", "config.py", "config.yaml", "config.yml"}

    key_files = []

    # Priority files first
    for name in priority_names:
        p = root / name
        if p.exists():
            key_files.append(p)

    # Then largest Python files (likely main implementation)
    py_files = []
    for f in root.rglob("*.py"):
        if any(part in _EXCLUDE_DIRS for part in f.parts):
            continue
        if f.name.startswith("test_") or f.name.startswith("_"):
            continue
        try:
            py_files.append((f, f.stat().st_size))
        except OSError:
            continue

    py_files.sort(key=lambda x: x[1], reverse=True)
    for f, _ in py_files[:10]:
        if f not in key_files:
            key_files.append(f)

    return key_files[:15]  # Cap at 15 files


def _compute_language_breakdown(root: Path) -> dict[str, float]:
    """Compute language breakdown by file count."""
    counts: dict[str, int] = {}
    total = 0
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if any(part in _EXCLUDE_DIRS for part in f.parts):
            continue
        lang = _LANG_MAP.get(f.suffix)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
            total += 1

    if total == 0:
        return {}
    return {lang: round(count / total * 100, 1) for lang, count in sorted(counts.items(), key=lambda x: -x[1])}


def _read_file_content(path: Path, max_lines: int = 500) -> str:
    """Read file content with line cap."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        content = "\n".join(lines[:max_lines])
        if len(lines) > max_lines:
            content += f"\n... ({len(lines) - max_lines} more lines)"
        return content
    except Exception:
        return ""


def _llm_query_sync(prompt: str, model: str = MODEL) -> str:
    """Run a single-shot LLM query via claude-agent-sdk synchronously.

    Called from background threads (no running event loop), so asyncio.run() is safe.
    """
    async def _run():
        from claude_agent_sdk import ClaudeAgentOptions, query
        from claude_agent_sdk import AssistantMessage, TextBlock

        # Unset ANTHROPIC_API_KEY so the SDK uses its own OAuth auth
        options = ClaudeAgentOptions(
            allowed_tools=[],
            model=model,
            env={"ANTHROPIC_API_KEY": ""},
        )

        text_parts: list[str] = []
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
        return "".join(text_parts)

    return asyncio.run(_run())


def _analyze_repo_with_llm(repo_url: str, tree: str, key_file_contents: dict[str, str]) -> RepoAnalysis:
    """Use LLM to analyze a cloned repo."""
    key_files_text = ""
    for path, content in key_file_contents.items():
        key_files_text += f"\n--- {path} ---\n{content}\n"

    prompt = f"""Analyze this GitHub repository and provide a structured summary.

Repository: {repo_url}

Directory structure:
{tree}

Key file contents:
{key_files_text}

Provide your analysis as JSON with these fields:
- "architecture_notes": A 2-3 paragraph summary of the codebase architecture, key patterns, and how the code is organized
- "dependencies": List of key dependencies/libraries used
- "key_algorithms": Brief description of any algorithms or techniques implemented

Return ONLY valid JSON, no markdown fences."""

    try:
        text = _llm_query_sync(prompt)
        text = text.strip()
        # Strip markdown fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        return RepoAnalysis(
            repo_url=repo_url,
            architecture_notes=data.get("architecture_notes", ""),
            dependencies=data.get("dependencies", []),
        )
    except Exception as e:
        logger.error(f"LLM repo analysis failed for {repo_url}: {e}")
        return RepoAnalysis(
            repo_url=repo_url,
            architecture_notes=f"Analysis failed: {e}",
        )


# ============================================================
# Paper context extraction with LLM
# ============================================================

def _extract_paper_context_with_llm(paper_data: dict, cached_content: Optional[dict] = None) -> PaperContext:
    """Use LLM to extract key methods and algorithms from a paper."""
    title = paper_data.get("title", "Unknown")
    abstract = paper_data.get("abstract", "")
    summary = paper_data.get("summary", "")

    # Build content from available sources
    content_parts = [f"Title: {title}", f"Abstract: {abstract}"]
    if summary:
        content_parts.append(f"Summary: {summary}")
    if cached_content and cached_content.get("sections"):
        for section, html in cached_content["sections"].items():
            # Strip HTML tags for LLM
            from bs4 import BeautifulSoup
            text = BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)
            if text:
                content_parts.append(f"{section.replace('_', ' ').title()}: {text[:3000]}")

    full_content = "\n\n".join(content_parts)

    prompt = f"""Analyze this research paper and extract key information for code implementation.

{full_content}

Provide your analysis as JSON with these fields:
- "content_summary": A concise 2-3 paragraph summary focused on what this paper contributes and how it works (for an engineer who needs to implement it)
- "key_methods": List of specific methods, techniques, or approaches described in the paper (e.g., "Attention mechanism with rotary position embeddings", "Proximal policy optimization")
- "key_algorithms": List of specific algorithms or pseudocode described (e.g., "Algorithm 1: Training loop with reward shaping", "MCTS with neural value estimation")

Return ONLY valid JSON, no markdown fences."""

    try:
        text = _llm_query_sync(prompt)
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        return PaperContext(
            paper_id=paper_data.get("id", "unknown"),
            title=title,
            content_summary=data.get("content_summary", ""),
            key_methods=data.get("key_methods", []),
            key_algorithms=data.get("key_algorithms", []),
        )
    except Exception as e:
        logger.error(f"LLM paper context extraction failed for {title}: {e}")
        return PaperContext(
            paper_id=paper_data.get("id", "unknown"),
            title=title,
            content_summary=abstract,
        )


# ============================================================
# Main context build pipeline
# ============================================================

def build_context(project_id: str) -> None:
    """Trigger context build in a background thread."""
    with _lock:
        if project_id in _building:
            return
        _building.add(project_id)
        _progress[project_id] = "Starting..."

    t = threading.Thread(
        target=_build_context_bg,
        args=(project_id,),
        daemon=True,
    )
    t.start()


def _build_context_bg(project_id: str) -> None:
    """Background worker for context assembly."""
    try:
        with project_svc._get_project_lock(project_id):
            state = project_svc.get_project(project_id)
            if state is None:
                return

            state.project.phase = "context_gathering"
            state.project.status = "setup"
            project_svc.save_state(state)

            # Snapshot what to process (avoids stale state after lock release)
            paper_ids_to_process = list(state.project.paper_ids)
            repos_to_process = list(state.project.github_repos)

        paper_contexts: list[PaperContext] = []

        # Phase 1: Fetch paper content
        with _lock:
            _progress[project_id] = "Fetching papers..."

        for paper_id in paper_ids_to_process:
            paper_data = get_paper_by_id(paper_id)
            if paper_data is None and paper_id.startswith("arxiv:"):
                # Paper was added via URL fetch and isn't in the papers cache.
                # Fall back to fetching metadata directly from arXiv.
                arxiv_id = paper_id[len("arxiv:"):]
                url = f"https://arxiv.org/abs/{arxiv_id}"
                paper_data = fetch_paper_by_url(url)
            if paper_data is None:
                logger.warning(f"Paper {paper_id} not found, skipping")
                continue

            # Fetch arXiv HTML content if not cached
            cached = get_cached_content(paper_id)
            if not cached or cached.get("fetch_status") != "ok":
                fetch_and_cache_paper_content(paper_id, paper_data.get("url", ""))
                cached = get_cached_content(paper_id)

            # Extract context with LLM
            with _lock:
                _progress[project_id] = f"Analyzing paper: {paper_data.get('title', paper_id)[:50]}..."

            ctx = _extract_paper_context_with_llm(paper_data, cached)
            paper_contexts.append(ctx)

        # Phase 2: Clone and analyze GitHub repos
        with _lock:
            _progress[project_id] = "Cloning repositories..."

        repo_analyses: dict[str, RepoAnalysis] = {}
        for repo_url in repos_to_process:
            if not _validate_github_url(repo_url):
                logger.warning(f"Invalid GitHub URL: {repo_url}, skipping")
                continue

            repo_name = _repo_name_from_url(repo_url)
            dest = settings.autoresearch_dir / project_id / "repos" / repo_name

            with _lock:
                _progress[project_id] = f"Cloning {repo_name}..."

            if not _clone_repo(repo_url, dest):
                continue

            with _lock:
                _progress[project_id] = f"Analyzing {repo_name}..."

            # Build tree and identify key files
            tree = _build_directory_tree(dest)
            key_files = _identify_key_files(dest)
            key_file_contents = {}
            for kf in key_files:
                rel_path = str(kf.relative_to(dest))
                key_file_contents[rel_path] = _read_file_content(kf)

            lang_breakdown = _compute_language_breakdown(dest)

            # LLM analysis
            analysis = _analyze_repo_with_llm(repo_url, tree, key_file_contents)
            analysis.structure = tree
            analysis.key_files = list(key_file_contents.keys())
            analysis.language_breakdown = lang_breakdown
            repo_analyses[repo_url] = analysis

        # Phase 3: Link repo analyses to paper contexts
        with _lock:
            _progress[project_id] = "Building context..."

        # Simple heuristic: if there's only one repo and one paper, link them
        # Otherwise, repos are available but not auto-linked to specific papers
        for ctx in paper_contexts:
            if ctx.github_repo_url and ctx.github_repo_url in repo_analyses:
                ctx.repo_analysis = repo_analyses[ctx.github_repo_url]

        # Store unlinked repo analyses as separate paper contexts
        linked_urls = {ctx.github_repo_url for ctx in paper_contexts if ctx.github_repo_url}
        for url, analysis in repo_analyses.items():
            if url not in linked_urls:
                # Find first paper without a repo, or create a standalone entry
                assigned = False
                for ctx in paper_contexts:
                    if ctx.github_repo_url is None and ctx.repo_analysis is None:
                        ctx.github_repo_url = url
                        ctx.repo_analysis = analysis
                        assigned = True
                        break
                if not assigned and len(paper_contexts) == 1:
                    paper_contexts[0].github_repo_url = url
                    paper_contexts[0].repo_analysis = analysis

        # Save results — merge with any existing contexts for papers not in this build
        with project_svc._get_project_lock(project_id):
            state = project_svc.get_project(project_id)
            if state is None:
                return
            built_ids = {ctx.paper_id for ctx in paper_contexts}
            existing_kept = [
                ctx for ctx in state.paper_contexts
                if ctx.paper_id not in built_ids
            ]
            state.paper_contexts = paper_contexts + existing_kept
            state.project.phase = "planning_chat"  # Ready for Phase B
            project_svc.save_state(state)

        logger.info(f"Context build complete for project {project_id}: "
                     f"{len(paper_contexts)} papers, {len(repo_analyses)} repos")

    except Exception as e:
        logger.error(f"Context build failed for {project_id}: {e}", exc_info=True)
        try:
            with project_svc._get_project_lock(project_id):
                state = project_svc.get_project(project_id)
                if state:
                    state.project.status = "error"
                    project_svc.save_state(state)
        except Exception:
            pass
    finally:
        with _lock:
            _building.discard(project_id)
            _progress.pop(project_id, None)
