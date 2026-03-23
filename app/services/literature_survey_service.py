"""Literature Survey Service — generates D3 knowledge graphs and AI-written academic surveys."""

import json
import logging
import os
import re
import threading
from typing import Optional

import anthropic

from app.config import settings
from app.models.literature_survey import (
    LiteratureSurvey,
    LiteratureSurveyGraph,
    PaperNode,
    RelationEdge,
)
from app.utils import safe_filename

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"

# Track in-progress generations
_generating: set[str] = set()
_lock = threading.Lock()


# ============================================================
# Related Paper Scoring
# ============================================================

def find_related_papers(
    focal_paper: dict, all_papers: list[dict], top_n: int = 12
) -> list[tuple[dict, float]]:
    """Score all papers by relevance to focal paper and return top N with normalized scores."""
    focal_tags = [t.lower() for t in (focal_paper.get("tags") or [])]
    focal_authors = [a.lower() for a in (focal_paper.get("authors") or [])]
    focal_title = (focal_paper.get("title") or "").lower()
    focal_abstract = (focal_paper.get("abstract") or "") + " " + (focal_paper.get("summary") or "")
    focal_title_words = set(w for w in focal_title.split() if len(w) > 4)
    focal_abstract_words = set(
        w for w in re.findall(r"\b\w+\b", focal_abstract.lower()) if len(w) > 4
    )

    focal_id = focal_paper.get("id")
    candidates = []

    for paper in all_papers:
        if paper.get("id") == focal_id:
            continue

        score = 0.0

        # Tag overlap: 3pts per shared tag
        paper_tags = [t.lower() for t in (paper.get("tags") or [])]
        for t in focal_tags:
            if t in paper_tags:
                score += 3

        # Author overlap: 2pts per shared author
        paper_authors = [a.lower() for a in (paper.get("authors") or [])]
        for a in focal_authors:
            if a in paper_authors:
                score += 2

        # Title keyword overlap: 1pt per shared meaningful word
        paper_title = (paper.get("title") or "").lower()
        paper_title_words = set(w for w in paper_title.split() if len(w) > 4)
        score += len(focal_title_words & paper_title_words) * 1

        # Abstract keyword overlap: 0.5pt per shared word
        paper_abstract = (paper.get("abstract") or "") + " " + (paper.get("summary") or "")
        paper_abstract_words = set(
            w for w in re.findall(r"\b\w+\b", paper_abstract.lower()) if len(w) > 4
        )
        score += len(focal_abstract_words & paper_abstract_words) * 0.5

        if score > 0:
            candidates.append((paper, score))

    candidates.sort(key=lambda x: x[1], reverse=True)
    candidates = candidates[:top_n]

    if not candidates:
        return candidates

    # Normalize scores to 0.0–1.0
    max_score = candidates[0][1]
    if max_score > 0:
        candidates = [(paper, round(score / max_score, 3)) for paper, score in candidates]

    return candidates


# ============================================================
# Relation Description
# ============================================================

def _heuristic_relation(focal_paper: dict, related_paper: dict) -> str:
    """Generate a relation description using heuristics when LLM is unavailable."""
    focal_tags = set(t.lower() for t in (focal_paper.get("tags") or []))
    related_tags = set(t.lower() for t in (related_paper.get("tags") or []))
    shared_tags = focal_tags & related_tags

    focal_authors = set(a.lower() for a in (focal_paper.get("authors") or []))
    related_authors = set(a.lower() for a in (related_paper.get("authors") or []))

    if focal_authors & related_authors:
        return "shares authorship with related research"

    if len(shared_tags) > 2:
        tag = next(iter(shared_tags))
        return f"closely related in {tag} domain"

    if shared_tags:
        tag = next(iter(shared_tags))
        return f"related work in {tag} research area"

    focal_words = set(w for w in (focal_paper.get("title") or "").lower().split() if len(w) > 4)
    related_words = set(w for w in (related_paper.get("title") or "").lower().split() if len(w) > 4)
    shared_words = focal_words & related_words

    if shared_words:
        keyword = next(iter(shared_words))
        return f"builds on similar {keyword} techniques"

    return "related work in this research area"


def generate_relation_description(
    focal_paper: dict,
    related_paper: dict,
    focal_summary: str,
    related_summary: str,
    client: Optional[anthropic.Anthropic] = None,
) -> str:
    """Generate a 5-8 word relation description between two papers."""
    if client:
        try:
            prompt = (
                "You are analyzing two research papers. Describe their relationship in exactly "
                "5-8 words starting with a verb.\n"
                'Examples: "extends transformer architecture for multimodal tasks", '
                '"contradicts findings on attention scaling", "applies RLHF to code generation"\n\n'
                f"Paper A: {focal_paper.get('title', '')}\n"
                f"Summary A: {(focal_summary or focal_paper.get('abstract') or '')[:300]}\n\n"
                f"Paper B: {related_paper.get('title', '')}\n"
                f"Summary B: {(related_summary or related_paper.get('abstract') or '')[:300]}\n\n"
                "Relationship (5-8 words, verb first):"
            )
            response = client.messages.create(
                model=MODEL,
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}],
            )
            for block in response.content:
                if block.type == "text":
                    relation = block.text.strip().strip('"').strip("'").strip()
                    if relation:
                        return relation
        except Exception as e:
            logger.warning(f"LLM relation generation failed: {e}")

    return _heuristic_relation(focal_paper, related_paper)


# ============================================================
# Survey Text Generation
# ============================================================

def _heuristic_survey(
    focal_paper: dict,
    related_papers_with_relations: list[tuple[dict, str, float]],
) -> str:
    """Generate a structured template-based survey when LLM is unavailable."""
    title = focal_paper.get("title", "Untitled")
    authors = focal_paper.get("authors") or []
    author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
    abstract = focal_paper.get("abstract") or focal_paper.get("summary") or ""

    # Group papers into thematic clusters by their primary tag
    clusters: dict[str, list] = {}
    for paper, relation, score in related_papers_with_relations:
        tags = paper.get("tags") or []
        key = tags[0].title() if tags else "General"
        clusters.setdefault(key, []).append((paper, relation, score))

    html_parts = []

    # Introduction
    abstract_excerpt = (abstract[:400] + "…") if len(abstract) > 400 else abstract
    intro = (
        f"<p><strong>{title}</strong>"
        + (f" by {author_str}" if author_str else "")
        + " addresses a significant problem in the research landscape. "
        + (abstract_excerpt or "This paper makes important contributions to the field.")
        + f" The following survey situates this work within the broader literature, "
        f"examining {len(related_papers_with_relations)} related works.</p>"
    )
    html_parts.append(intro)

    # Thematic clusters
    cluster_names = list(clusters.keys())[:4]
    for cluster_name in cluster_names:
        cluster_papers = clusters[cluster_name]
        html_parts.append(f"<h3>{cluster_name}</h3>")
        descs = []
        for paper, relation, score in cluster_papers[:4]:
            p_title = paper.get("title", "Untitled")
            p_authors = paper.get("authors") or []
            p_author = p_authors[0] if p_authors else "Unknown"
            descs.append(f"<strong>{p_title}</strong> ({p_author}) — {relation}.")
        html_parts.append(f"<p>{'  '.join(descs)}</p>")

    # Synthesis
    html_parts.append("<h3>Synthesis</h3>")
    html_parts.append(
        f"<p><strong>{title}</strong> represents an important contribution to this body of work. "
        f"Drawing from {len(related_papers_with_relations)} related works across "
        f"{len(clusters)} research theme(s), this paper advances the field by building on "
        "existing methodologies while addressing gaps in the current literature. "
        "Future work in this area will likely extend the foundations established here.</p>"
    )

    return "\n".join(html_parts)


def generate_survey_text(
    focal_paper: dict,
    related_papers_with_relations: list[tuple[dict, str, float]],
    focal_summary: str,
    client: Optional[anthropic.Anthropic] = None,
) -> str:
    """Generate a comprehensive academic literature survey as HTML."""
    if client:
        try:
            related_lines = []
            for paper, relation, score in related_papers_with_relations:
                p_authors = ", ".join((paper.get("authors") or [])[:3])
                p_summary = (paper.get("summary") or paper.get("abstract") or "")[:200]
                related_lines.append(
                    f"- **{paper.get('title', 'Untitled')}** by {p_authors}\n"
                    f"  Relation to focal paper: {relation}\n"
                    f"  Summary: {p_summary}"
                )

            focal_authors = ", ".join((focal_paper.get("authors") or [])[:5])
            survey_summary = focal_summary or focal_paper.get("abstract") or ""

            prompt = (
                "You are an expert academic researcher writing a literature review section.\n\n"
                f"FOCAL PAPER: {focal_paper.get('title', '')}\n"
                f"Authors: {focal_authors}\n"
                f"Abstract/Summary: {survey_summary[:600]}\n\n"
                "RELATED PAPERS:\n"
                + "\n".join(related_lines[:12])
                + "\n\nWrite a comprehensive literature survey (400-600 words) covering:\n"
                "1. An intro paragraph placing the focal paper in context\n"
                "2. Group related papers into 2-4 thematic clusters with descriptive headers\n"
                "3. For each cluster: what the papers contribute, how they relate to each other, "
                "how they inform the focal paper\n"
                "4. A synthesis paragraph on how the focal paper advances the field\n\n"
                "Use academic writing style. Bold paper titles when mentioned. "
                "Use HTML: <h3> for cluster headers, <p> for paragraphs, <strong> for paper titles. "
                "Do NOT include any markdown, only HTML tags."
            )

            response = client.messages.create(
                model=MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            for block in response.content:
                if block.type == "text":
                    return block.text.strip()
        except Exception as e:
            logger.warning(f"LLM survey generation failed: {e}")

    return _heuristic_survey(focal_paper, related_papers_with_relations)


# ============================================================
# Storage
# ============================================================

def _survey_path(paper_id: str):
    return settings.explorations_dir / safe_filename(paper_id) / "literature_survey.json"


def _save_survey(survey: LiteratureSurvey) -> None:
    folder = settings.explorations_dir / safe_filename(survey.focal_paper_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "literature_survey.json").write_text(
        survey.model_dump_json(indent=2), encoding="utf-8"
    )


def get_survey(paper_id: str) -> Optional[LiteratureSurvey]:
    """Load a survey from disk if it exists."""
    path = _survey_path(paper_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return LiteratureSurvey(**data)
    except Exception as e:
        logger.error(f"Failed to load survey for {paper_id}: {e}")
        return None


def get_survey_status(paper_id: str) -> str:
    """Return survey status: not_found | generating | ready | error."""
    with _lock:
        if paper_id in _generating:
            return "generating"
    survey = get_survey(paper_id)
    if survey is None:
        return "not_found"
    return survey.status


# ============================================================
# Background Generation
# ============================================================

def _build_survey_sync(paper_id: str, all_papers: list[dict]) -> LiteratureSurvey:
    """Synchronously build the full literature survey."""
    from app.services.paper_service import get_paper_by_id

    focal_paper = get_paper_by_id(paper_id)
    if not focal_paper:
        focal_paper = next((p for p in all_papers if p.get("id") == paper_id), None)
    if not focal_paper:
        raise ValueError(f"Paper not found: {paper_id}")

    # Set up LLM client (optional — gracefully degrades without API key)
    client = None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            logger.warning(f"Failed to create Anthropic client: {e}")

    focal_summary = focal_paper.get("summary") or focal_paper.get("abstract") or ""

    # Find related papers
    related = find_related_papers(focal_paper, all_papers, top_n=12)

    # Generate relation descriptions
    related_with_relations: list[tuple[dict, str, float]] = []
    for paper, score in related:
        related_summary = paper.get("summary") or paper.get("abstract") or ""
        relation = generate_relation_description(
            focal_paper, paper, focal_summary, related_summary, client
        )
        related_with_relations.append((paper, relation, score))

    # Generate survey text
    survey_text = generate_survey_text(focal_paper, related_with_relations, focal_summary, client)

    # Build graph
    focal_node = PaperNode(
        id=focal_paper["id"],
        title=focal_paper.get("title", "Untitled"),
        authors=focal_paper.get("authors") or [],
        date=focal_paper.get("date"),
        url=focal_paper.get("url"),
        relevance_score=1.0,
        is_focal=True,
        tags=focal_paper.get("tags") or [],
    )

    related_nodes = [
        PaperNode(
            id=paper["id"],
            title=paper.get("title", "Untitled"),
            authors=paper.get("authors") or [],
            date=paper.get("date"),
            url=paper.get("url"),
            relevance_score=score,
            is_focal=False,
            tags=paper.get("tags") or [],
        )
        for paper, _, score in related_with_relations
    ]

    edges = [
        RelationEdge(
            source=focal_paper["id"],
            target=paper["id"],
            relation=relation,
            strength=score,
        )
        for paper, relation, score in related_with_relations
    ]

    graph = LiteratureSurveyGraph(
        focal_paper_id=focal_paper["id"],
        nodes=[focal_node] + related_nodes,
        edges=edges,
    )

    return LiteratureSurvey(
        focal_paper_id=focal_paper["id"],
        graph=graph,
        survey_text=survey_text,
        paper_count=len(related_nodes) + 1,
        status="ready",
    )


def _build_survey_bg(paper_id: str, all_papers: list[dict]) -> None:
    """Background thread target for survey generation."""
    try:
        survey = _build_survey_sync(paper_id, all_papers)
        _save_survey(survey)
        logger.info(f"Survey generated for {paper_id}")
    except Exception as e:
        logger.error(f"Survey generation failed for {paper_id}: {e}")
        try:
            error_survey = LiteratureSurvey(
                focal_paper_id=paper_id,
                graph=LiteratureSurveyGraph(focal_paper_id=paper_id, nodes=[], edges=[]),
                survey_text="<p>Error generating survey. Please try again.</p>",
                status="error",
                paper_count=0,
            )
            _save_survey(error_survey)
        except Exception:
            pass
    finally:
        with _lock:
            _generating.discard(paper_id)


def start_survey_generation(paper_id: str, all_papers: list[dict]) -> str:
    """Kick off background survey generation. Returns current status string."""
    with _lock:
        if paper_id in _generating:
            return "generating"

    # Already done?
    existing = get_survey(paper_id)
    if existing and existing.status == "ready":
        return "ready"

    with _lock:
        _generating.add(paper_id)

    t = threading.Thread(target=_build_survey_bg, args=(paper_id, all_papers), daemon=True)
    t.start()
    return "generating"
