"""Research Directions Service — deep critical analysis and chat interface."""

import datetime
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Optional

import anthropic
import yaml

from app.config import settings
from app.models.research_directions import (
    ChatMessage,
    ChatResponse,
    CoreDecomposition,
    CriticalLens,
    ResearchDirection,
    ResearchDirectionsAnalysis,
)
from app.utils import safe_filename

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"

# Track in-progress generations
_generating: set[str] = set()
_lock = threading.Lock()

# Per-paper locks for chat serialization
_chat_locks: dict[str, threading.Lock] = {}
_chat_locks_lock = threading.Lock()


def _get_chat_lock(paper_id: str) -> threading.Lock:
    with _chat_locks_lock:
        if paper_id not in _chat_locks:
            _chat_locks[paper_id] = threading.Lock()
        return _chat_locks[paper_id]


# ============================================================
# Storage
# ============================================================

def _analysis_path(paper_id: str) -> Path:
    return settings.explorations_dir / safe_filename(paper_id) / "research_directions.json"


def get_analysis(paper_id: str) -> Optional[ResearchDirectionsAnalysis]:
    path = _analysis_path(paper_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ResearchDirectionsAnalysis(**data)
    except Exception as e:
        logger.error(f"Failed to load research directions for {paper_id}: {e}")
        return None


def _save_analysis(analysis: ResearchDirectionsAnalysis) -> None:
    folder = settings.explorations_dir / safe_filename(analysis.paper_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "research_directions.json").write_text(
        analysis.model_dump_json(indent=2), encoding="utf-8"
    )


def get_status(paper_id: str) -> str:
    with _lock:
        if paper_id in _generating:
            return "generating"
    analysis = get_analysis(paper_id)
    if analysis is None:
        return "not_found"
    return analysis.status


# ============================================================
# Paper Content Loading
# ============================================================

def _load_paper_content(paper_id: str) -> dict:
    """Load paper markdown, summary, and related papers index."""
    from app.services.paper_service import get_paper_by_id, get_paper_path_by_id

    paper_meta = get_paper_by_id(paper_id)
    title = (paper_meta or {}).get("title", "Unknown")
    authors = ", ".join((paper_meta or {}).get("authors", []))
    abstract = (paper_meta or {}).get("abstract", "")

    # Load full paper body from .md file
    body = ""
    paper_path = get_paper_path_by_id(paper_id)
    if paper_path and paper_path.exists():
        raw = paper_path.read_text(encoding="utf-8")
        # Strip YAML frontmatter
        parts = raw.split("---\n", 2)
        if len(parts) >= 3:
            body = parts[2].strip()
        else:
            body = raw.strip()

    # Load summary if exists
    summary = ""
    if paper_path:
        summary_path = settings.summaries_dir / f"{paper_path.stem}.md"
        if summary_path.exists():
            summary = summary_path.read_text(encoding="utf-8").strip()

    # Load related papers index if exists
    related_papers_titles = []
    related_index_path = (
        settings.explorations_dir / safe_filename(paper_id) / "related_papers_index.json"
    )
    if related_index_path.exists():
        try:
            related_index = json.loads(related_index_path.read_text(encoding="utf-8"))
            related_papers_titles = [r.get("title", "") for r in related_index if r.get("title")]
        except Exception:
            pass

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "body": body,
        "summary": summary,
        "related_papers_titles": related_papers_titles,
    }


# ============================================================
# LLM Helpers
# ============================================================

def _call_llm(client: anthropic.Anthropic, system: str, prompt: str, max_tokens: int = 1200) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    for block in response.content:
        if block.type == "text":
            return block.text.strip()
    return ""


def _parse_json(text: str):
    """Defensively parse JSON from LLM output (handles markdown fences, extra text)."""
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.strip().rstrip("`")

    # Try parsing directly
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try parsing from each { or [ position using raw_decode,
    # preferring later occurrences (LLMs typically put JSON at the end)
    decoder = json.JSONDecoder()
    for i in range(len(cleaned) - 1, -1, -1):
        if cleaned[i] in ('{', '['):
            try:
                obj, _ = decoder.raw_decode(cleaned, i)
                return obj
            except (json.JSONDecodeError, ValueError):
                continue
    return None


# ============================================================
# Analysis Phases
# ============================================================

def _decompose_paper(client: anthropic.Anthropic, paper_content: dict) -> CoreDecomposition:
    system = "You are a research analyst. Return ONLY valid JSON, no other text."
    prompt = f"""Analyze this research paper and extract its core components as JSON.

Title: {paper_content['title']}
Authors: {paper_content['authors']}
Abstract: {paper_content['abstract'][:1500]}
Content:
{paper_content['body'][:4000]}

{f"Summary: {paper_content['summary'][:1000]}" if paper_content['summary'] else ""}

Return ONLY valid JSON with this structure:
{{
  "hypothesis": "The paper's central claim or hypothesis in 1-2 sentences",
  "methodology": "What methods/techniques were used, in 2-3 sentences",
  "experiments": "What experiments were run, what baselines, what metrics, in 2-3 sentences",
  "key_findings": "The main results and conclusions, in 2-3 sentences"
}}"""

    text = _call_llm(client, system, prompt, max_tokens=800)
    parsed = _parse_json(text)
    if parsed and isinstance(parsed, dict):
        return CoreDecomposition(
            hypothesis=parsed.get("hypothesis", "Not identified"),
            methodology=parsed.get("methodology", "Not identified"),
            experiments=parsed.get("experiments", "Not identified"),
            key_findings=parsed.get("key_findings", "Not identified"),
        )
    # Fallback: use abstract as hypothesis, body excerpt as methodology
    return CoreDecomposition(
        hypothesis=paper_content["abstract"][:300] or "See paper for details.",
        methodology="See paper for methodology details.",
        experiments="See paper for experiment details.",
        key_findings=paper_content["summary"][:300] if paper_content["summary"] else "See paper for findings.",
    )


def _run_critical_lenses(
    client: anthropic.Anthropic, paper_content: dict, core: CoreDecomposition
) -> list[CriticalLens]:
    system = "You are a rigorous peer reviewer. Return ONLY a valid JSON array, no other text."
    prompt = f"""Analyze this research paper critically. Identify the most important critical insights. Only include dimensions that are genuinely applicable and revealing.

Paper: {paper_content['title']}
Hypothesis: {core.hypothesis}
Methodology: {core.methodology}
Experiments: {core.experiments}
Findings: {core.key_findings}

{f"Related works in the field: {', '.join(paper_content['related_papers_titles'][:8])}" if paper_content['related_papers_titles'] else ""}

Analyze from these angles (include only 3-6 that are most relevant):
- Novelty Check: Is this genuinely novel or scaffolding prior work?
- Methodological Critique: Why this design? What are its limits?
- Robustness & Generalization: What if conditions changed?
- Bias & Assumptions: What's baked in that isn't acknowledged?
- Overlooked Factors: What did the authors miss?
- Comparative Positioning: Does it truly outperform alternatives fairly?

Return ONLY a JSON array:
[{{
  "dimension": "Dimension Name",
  "title": "Short punchy title for this specific finding",
  "insight": "2-4 sentences of specific, incisive analysis",
  "severity": "info|caution|concern"
}}]"""

    text = _call_llm(client, system, prompt, max_tokens=1500)
    parsed = _parse_json(text)
    if parsed and isinstance(parsed, list):
        lenses = []
        for item in parsed[:6]:
            if isinstance(item, dict) and item.get("dimension") and item.get("insight"):
                severity = item.get("severity", "info")
                if severity not in ("info", "caution", "concern"):
                    severity = "info"
                lenses.append(CriticalLens(
                    dimension=item["dimension"],
                    title=item.get("title", item["dimension"]),
                    insight=item["insight"],
                    severity=severity,
                ))
        if lenses:
            return lenses

    # Fallback: generate a basic lens from available info
    return [CriticalLens(
        dimension="Overview",
        title="Paper analysis pending deeper review",
        insight=f"This paper on '{paper_content['title']}' presents {core.hypothesis[:200]}. A more detailed critical analysis requires full paper content.",
        severity="info",
    )]


def _generate_directions(
    client: anthropic.Anthropic,
    paper_content: dict,
    core: CoreDecomposition,
    lenses: list[CriticalLens],
) -> list[ResearchDirection]:
    lenses_summary = "\n".join(
        f"- {l.dimension}: {l.title} — {l.insight}" for l in lenses
    )
    system = "You are a research advisor. Return ONLY a valid JSON array, no other text."
    prompt = f"""Based on the critical analysis of this paper, generate 4-6 specific, actionable research directions.

Paper: {paper_content['title']}
Core findings: {core.key_findings}
Methodology: {core.methodology}
Critical insights:
{lenses_summary}

{f"Related works: {', '.join(paper_content['related_papers_titles'][:6])}" if paper_content['related_papers_titles'] else ""}

Generate directions that are:
- Specific to this paper's gaps, NOT generic future work suggestions
- Actionable (a researcher could start this tomorrow)
- Grounded in the identified weaknesses or strengths

Return ONLY a JSON array:
[{{
  "title": "Direction title",
  "description": "2-3 sentences describing what to do and how",
  "why_it_matters": "1-2 sentences on the significance",
  "difficulty": "low|medium|high",
  "tags": ["relevant", "topic", "tags"]
}}]"""

    text = _call_llm(client, system, prompt, max_tokens=1500)
    parsed = _parse_json(text)
    if parsed and isinstance(parsed, list):
        directions = []
        for item in parsed[:6]:
            if isinstance(item, dict) and item.get("title"):
                difficulty = item.get("difficulty", "medium")
                if difficulty not in ("low", "medium", "high"):
                    difficulty = "medium"
                directions.append(ResearchDirection(
                    title=item["title"],
                    description=item.get("description", ""),
                    why_it_matters=item.get("why_it_matters", ""),
                    difficulty=difficulty,
                    tags=item.get("tags", [])[:5] if isinstance(item.get("tags"), list) else [],
                ))
        if directions:
            return directions

    # Fallback
    return [ResearchDirection(
        title=f"Extend {paper_content['title'][:60]}",
        description=f"Based on the findings: {core.key_findings[:200]}",
        why_it_matters="Addresses gaps identified in the critical analysis.",
        difficulty="medium",
        tags=[],
    )]


# ============================================================
# Graceful Degradation (no API key)
# ============================================================

def _build_template_analysis(paper_id: str, paper_content: dict) -> ResearchDirectionsAnalysis:
    """Generate a structured template-based output using actual paper data when no API key is available."""
    core = CoreDecomposition(
        hypothesis=paper_content["abstract"][:400] if paper_content["abstract"] else "See the paper for the central hypothesis.",
        methodology="Refer to the paper's methodology section for detailed techniques used.",
        experiments="Refer to the paper's experimental setup and results sections.",
        key_findings=paper_content["summary"][:400] if paper_content["summary"] else "See the paper for key findings and conclusions.",
    )
    lenses = [CriticalLens(
        dimension="Analysis Unavailable",
        title="LLM analysis requires API key",
        insight=f"To generate a deep critical analysis of '{paper_content['title']}', configure the ANTHROPIC_API_KEY environment variable. The analysis will cover novelty, methodology, robustness, and more.",
        severity="info",
    )]
    directions = [ResearchDirection(
        title="Configure API key for research directions",
        description="Set the ANTHROPIC_API_KEY environment variable to enable AI-powered research direction generation based on this paper's content and gaps.",
        why_it_matters="Automated analysis can surface non-obvious research opportunities from the paper's methodology and findings.",
        difficulty="low",
        tags=["setup"],
    )]
    return ResearchDirectionsAnalysis(
        paper_id=paper_id,
        core=core,
        critical_lenses=lenses,
        directions=directions,
        status="ready",
    )


# ============================================================
# Background Generation
# ============================================================

def _build_analysis_sync(paper_id: str) -> ResearchDirectionsAnalysis:
    """Run phases 1-5 synchronously (called in background thread)."""
    # Phase 1: Load paper content
    paper_content = _load_paper_content(paper_id)

    # Phase 2-4: LLM analysis (or template fallback)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _build_template_analysis(paper_id, paper_content)

    try:
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        logger.warning(f"Failed to create Anthropic client: {e}")
        return _build_template_analysis(paper_id, paper_content)

    # Phase 2: Core Decomposition
    core = _decompose_paper(client, paper_content)

    # Phase 3: Critical Lenses
    lenses = _run_critical_lenses(client, paper_content, core)

    # Phase 4: Research Directions
    directions = _generate_directions(client, paper_content, core, lenses)

    # Phase 5: Build and save
    analysis = ResearchDirectionsAnalysis(
        paper_id=paper_id,
        core=core,
        critical_lenses=lenses,
        directions=directions,
        status="ready",
    )
    return analysis


def _build_analysis_bg(paper_id: str) -> None:
    """Background thread target for analysis generation."""
    try:
        analysis = _build_analysis_sync(paper_id)
        _save_analysis(analysis)
        logger.info(f"Research directions generated for {paper_id}")
    except Exception as e:
        logger.error(f"Research directions generation failed for {paper_id}: {e}")
        try:
            error_analysis = ResearchDirectionsAnalysis(
                paper_id=paper_id,
                core=CoreDecomposition(
                    hypothesis="Error during analysis",
                    methodology="",
                    experiments="",
                    key_findings="",
                ),
                status="error",
            )
            _save_analysis(error_analysis)
        except Exception:
            pass
    finally:
        with _lock:
            _generating.discard(paper_id)


def start_analysis(paper_id: str) -> str:
    """Non-blocking. Starts background thread, returns status."""
    with _lock:
        if paper_id in _generating:
            return "generating"
        existing = get_analysis(paper_id)
        if existing and existing.status == "ready":
            return "ready"
        _generating.add(paper_id)

    t = threading.Thread(target=_build_analysis_bg, args=(paper_id,), daemon=True)
    t.start()
    return "generating"


# ============================================================
# Chat
# ============================================================

def chat_with_analysis(paper_id: str, user_message: str) -> ChatResponse:
    """Conversational chat about the analysis."""
    analysis = get_analysis(paper_id)
    if not analysis:
        return ChatResponse(reply="No analysis found for this paper. Please generate research directions first.")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ChatResponse(reply="Chat requires the ANTHROPIC_API_KEY environment variable to be configured.")

    try:
        client = anthropic.Anthropic(api_key=api_key)
    except Exception:
        return ChatResponse(reply="Failed to initialize the AI client. Please check your API key.")

    # Build context
    directions_summary = "\n".join(
        f"{i+1}. {d.title}: {d.description}" for i, d in enumerate(analysis.directions)
    )
    lenses_summary = "\n".join(
        f"- {l.dimension}: {l.insight}" for l in analysis.critical_lenses
    )

    system_prompt = f"""You are a research advisor helping a researcher explore and refine research directions for the paper "{analysis.core.hypothesis[:100]}".

Paper analysis context:
- Hypothesis: {analysis.core.hypothesis}
- Methodology: {analysis.core.methodology}
- Key Findings: {analysis.core.key_findings}

Critical insights:
{lenses_summary}

Current research directions:
{directions_summary}

The researcher may ask you to: explain findings, challenge assumptions, suggest refinements, go deeper on a specific direction, or brainstorm new angles.
Be specific, critical, and intellectually honest. Reference the actual paper content when relevant.
Keep responses concise (2-4 paragraphs max).
If the researcher asks to update/add/remove a research direction, do so and return a JSON block with key "updated_directions" containing the full updated list as a JSON array with fields: title, description, why_it_matters, difficulty, tags."""

    # Build messages from recent chat history (last 8)
    messages = []
    for msg in analysis.chat_history[-8:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=system_prompt,
            messages=messages,
        )
        reply_text = ""
        for block in response.content:
            if block.type == "text":
                reply_text = block.text.strip()
                break
    except Exception as e:
        logger.error(f"Chat LLM call failed: {e}")
        return ChatResponse(reply="Sorry, I encountered an error processing your message. Please try again.")

    # Handle empty LLM response
    if not reply_text:
        reply_text = "I wasn't able to generate a response. Please try rephrasing your question."

    # Check if reply contains updated_directions JSON
    updated_directions = None
    if '"updated_directions"' in reply_text:
        decoder = json.JSONDecoder()
        for i in range(len(reply_text)):
            if reply_text[i] == '{':
                try:
                    obj, end = decoder.raw_decode(reply_text, i)
                    if isinstance(obj, dict) and 'updated_directions' in obj:
                        parsed = obj['updated_directions']
                        updated_directions = []
                        for item in parsed:
                            if isinstance(item, dict) and item.get("title"):
                                difficulty = item.get("difficulty", "medium")
                                if difficulty not in ("low", "medium", "high"):
                                    difficulty = "medium"
                                updated_directions.append(ResearchDirection(
                                    title=item["title"],
                                    description=item.get("description", ""),
                                    why_it_matters=item.get("why_it_matters", ""),
                                    difficulty=difficulty,
                                    tags=item.get("tags", [])[:5] if isinstance(item.get("tags"), list) else [],
                                ))
                        # Surgically remove the JSON block from visible reply
                        reply_text = (reply_text[:i] + reply_text[end:]).strip()
                        reply_text = re.sub(r'```json\s*\n?\s*```', '', reply_text).strip()
                        break
                except (json.JSONDecodeError, ValueError):
                    continue

    # Serialize chat read-modify-write with per-paper lock
    chat_lock = _get_chat_lock(paper_id)
    with chat_lock:
        # Re-read analysis to get latest chat history
        analysis = get_analysis(paper_id)
        if not analysis:
            return ChatResponse(reply=reply_text, updated_directions=updated_directions)

        now = datetime.datetime.utcnow().isoformat()
        analysis.chat_history.append(ChatMessage(role="user", content=user_message, timestamp=now))
        analysis.chat_history.append(ChatMessage(role="assistant", content=reply_text, timestamp=now))

        # Cap chat history to prevent unbounded growth
        max_history = 50
        if len(analysis.chat_history) > max_history:
            analysis.chat_history = analysis.chat_history[-max_history:]

        if updated_directions:
            analysis.directions = updated_directions

        _save_analysis(analysis)

    return ChatResponse(reply=reply_text, updated_directions=updated_directions)
