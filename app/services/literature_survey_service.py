"""Related Works Service — generates multi-hop D3 knowledge graphs with rich edge annotations."""

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

# Fan-out per hop level: (top_n papers to find, hop level)
HOP_CONFIG = [(6, 1), (3, 2), (2, 3)]


# ============================================================
# Related Paper Scoring
# ============================================================

def find_related_papers(
    focal_paper: dict, all_papers: list[dict], top_n: int = 12,
    exclude_ids: set | None = None,
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
    skip_ids = {focal_id} | (exclude_ids or set())
    candidates = []

    for paper in all_papers:
        pid = paper.get("id")
        if pid in skip_ids:
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
# Rich Relation Generation (batched)
# ============================================================

def _heuristic_rich_relation(paper_a: dict, paper_b: dict) -> dict:
    """Generate relation, commonalities, differences using heuristics."""
    tags_a = set(t.lower() for t in (paper_a.get("tags") or []))
    tags_b = set(t.lower() for t in (paper_b.get("tags") or []))
    shared_tags = tags_a & tags_b
    unique_a = tags_a - tags_b
    unique_b = tags_b - tags_a

    authors_a = set(a.lower() for a in (paper_a.get("authors") or []))
    authors_b = set(a.lower() for a in (paper_b.get("authors") or []))

    # Relation
    if authors_a & authors_b:
        relation = "shares authorship with related research"
    elif len(shared_tags) > 2:
        relation = f"closely related in {next(iter(shared_tags))} domain"
    elif shared_tags:
        relation = f"related work in {next(iter(shared_tags))} research area"
    else:
        words_a = set(w for w in (paper_a.get("title") or "").lower().split() if len(w) > 4)
        words_b = set(w for w in (paper_b.get("title") or "").lower().split() if len(w) > 4)
        shared_words = words_a & words_b
        if shared_words:
            relation = f"builds on similar {next(iter(shared_words))} techniques"
        else:
            relation = "related work in this research area"

    # Commonalities
    if shared_tags:
        commonalities = f"Both address {', '.join(list(shared_tags)[:3])}"
    else:
        commonalities = "Both contribute to related research areas"

    # Differences
    if unique_a and unique_b:
        differences = f"One focuses on {next(iter(unique_a))}, the other on {next(iter(unique_b))}"
    elif unique_a:
        differences = f"This paper additionally covers {next(iter(unique_a))}"
    elif unique_b:
        differences = f"The other paper additionally covers {next(iter(unique_b))}"
    else:
        differences = "Different approaches to similar problems"

    return {"relation": relation, "commonalities": commonalities, "differences": differences}


def generate_rich_relations_batch(
    pairs: list[tuple[dict, dict]],
    client: Optional[anthropic.Anthropic] = None,
) -> list[dict]:
    """Generate rich relation info for multiple paper pairs.

    Each pair is (paper_a, paper_b).
    Returns list of {"relation": ..., "commonalities": ..., "differences": ...}.
    """
    if not pairs:
        return []

    if not client:
        return [_heuristic_rich_relation(a, b) for a, b in pairs]

    # Process in batches of 5-6 pairs per LLM call
    BATCH_SIZE = 5
    results = []

    for batch_start in range(0, len(pairs), BATCH_SIZE):
        batch = pairs[batch_start:batch_start + BATCH_SIZE]
        pair_descriptions = []
        for i, (pa, pb) in enumerate(batch, 1):
            sum_a = (pa.get("summary") or pa.get("abstract") or "")[:200]
            sum_b = (pb.get("summary") or pb.get("abstract") or "")[:200]
            pair_descriptions.append(
                f"Pair {i}:\n"
                f"  Paper A: {pa.get('title', 'Untitled')}\n"
                f"  Summary A: {sum_a}\n"
                f"  Paper B: {pb.get('title', 'Untitled')}\n"
                f"  Summary B: {sum_b}"
            )

        prompt = (
            "For each paper pair below, provide exactly 3 lines:\n"
            "RELATION: Their relationship in 5-8 words starting with a verb\n"
            "COMMON: What they share (1 sentence, max 25 words)\n"
            "DIFFERENT: What distinguishes them (1 sentence, max 25 words)\n\n"
            + "\n\n".join(pair_descriptions)
            + "\n\nRespond with the analysis for each pair, numbered. Use exactly the format:\n"
            "Pair N:\nRELATION: ...\nCOMMON: ...\nDIFFERENT: ..."
        )

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=200 * len(batch),
                messages=[{"role": "user", "content": prompt}],
            )
            text = ""
            for block in response.content:
                if block.type == "text":
                    text = block.text.strip()
                    break

            # Parse response
            batch_results = _parse_batch_response(text, len(batch))
            if len(batch_results) == len(batch):
                results.extend(batch_results)
            else:
                # Partial parse — fill missing with heuristics
                for i, (pa, pb) in enumerate(batch):
                    if i < len(batch_results):
                        results.append(batch_results[i])
                    else:
                        results.append(_heuristic_rich_relation(pa, pb))
        except Exception as e:
            logger.warning(f"Batched relation generation failed: {e}")
            results.extend([_heuristic_rich_relation(a, b) for a, b in batch])

    return results


def _parse_batch_response(text: str, expected_count: int) -> list[dict]:
    """Parse batched LLM response into list of relation dicts."""
    results = []
    # Split by "Pair N:" markers
    pair_blocks = re.split(r"Pair\s+\d+\s*:", text)
    # First element is usually empty (before "Pair 1:")
    pair_blocks = [b.strip() for b in pair_blocks if b.strip()]

    for block in pair_blocks[:expected_count]:
        relation_m = re.search(r"RELATION:\s*(.+?)(?:\n|$)", block)
        common_m = re.search(r"COMMON:\s*(.+?)(?:\n|$)", block)
        diff_m = re.search(r"DIFFERENT:\s*(.+?)(?:\n|$)", block)

        results.append({
            "relation": (relation_m.group(1).strip().strip('"').strip("'") if relation_m else "related work"),
            "commonalities": (common_m.group(1).strip() if common_m else ""),
            "differences": (diff_m.group(1).strip() if diff_m else ""),
        })

    return results


# ============================================================
# Multi-Hop Graph Builder
# ============================================================

def build_multi_hop_graph(
    focal_paper: dict,
    all_papers: list[dict],
    client: Optional[anthropic.Anthropic] = None,
) -> tuple[list[PaperNode], list[RelationEdge]]:
    """Build a 3-hop knowledge graph with rich edge annotations.

    Returns (nodes, edges) for the full multi-hop graph.
    """
    focal_id = focal_paper["id"]
    seen_ids: set[str] = {focal_id}

    # Focal node
    focal_node = PaperNode(
        id=focal_id,
        title=focal_paper.get("title", "Untitled"),
        authors=focal_paper.get("authors") or [],
        date=focal_paper.get("date"),
        url=focal_paper.get("url"),
        relevance_score=1.0,
        is_focal=True,
        tags=focal_paper.get("tags") or [],
        hop_level=0,
    )

    all_nodes: list[PaperNode] = [focal_node]
    all_edges: list[RelationEdge] = []

    # frontier: list of (paper_dict, source_paper_id) for generating edges
    frontier: list[tuple[dict, str]] = [(focal_paper, focal_id)]

    for top_n, hop_level in HOP_CONFIG:
        next_frontier: list[tuple[dict, str]] = []
        # Collect all pairs for batched relation generation
        edge_pairs: list[tuple[dict, dict]] = []
        edge_meta: list[tuple[str, str, float]] = []  # (source_id, target_id, score)

        for source_paper, source_id in frontier:
            related = find_related_papers(
                source_paper, all_papers, top_n=top_n, exclude_ids=seen_ids
            )
            for rel_paper, score in related:
                rel_id = rel_paper.get("id")
                if rel_id in seen_ids:
                    continue
                seen_ids.add(rel_id)

                all_nodes.append(PaperNode(
                    id=rel_id,
                    title=rel_paper.get("title", "Untitled"),
                    authors=rel_paper.get("authors") or [],
                    date=rel_paper.get("date"),
                    url=rel_paper.get("url"),
                    relevance_score=score,
                    is_focal=False,
                    tags=rel_paper.get("tags") or [],
                    hop_level=hop_level,
                ))

                edge_pairs.append((source_paper, rel_paper))
                edge_meta.append((source_id, rel_id, score))
                next_frontier.append((rel_paper, rel_id))

        # Generate rich relations for all edges at this hop level
        rich_relations = generate_rich_relations_batch(edge_pairs, client)

        for (source_id, target_id, score), rel_info in zip(edge_meta, rich_relations):
            all_edges.append(RelationEdge(
                source=source_id,
                target=target_id,
                relation=rel_info["relation"],
                commonalities=rel_info.get("commonalities", ""),
                differences=rel_info.get("differences", ""),
                strength=score,
            ))

        frontier = next_frontier

    return all_nodes, all_edges


# ============================================================
# Staleness Detection
# ============================================================

def check_survey_staleness(paper_id: str) -> bool:
    """Check if the survey is stale due to new My List papers."""
    from app.utils import load_json
    from datetime import datetime, timezone

    survey = get_survey(paper_id)
    if not survey or survey.status != "ready":
        return False

    mylist_data = load_json(settings.mylist_path, {})

    # Parse generated_at to a tz-aware datetime for reliable comparison
    try:
        gen_dt = datetime.fromisoformat(survey.generated_at)
        if gen_dt.tzinfo is None:
            gen_dt = gen_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return False

    # Get IDs already in the graph
    graph_ids = {n.id for n in survey.graph.nodes}

    # Extract focal paper before iterating
    focal_entry = mylist_data.get(paper_id, {})
    focal_paper = focal_entry.get("paper", {})
    if not focal_paper:
        return False
    focal_tags = set(t.lower() for t in (focal_paper.get("tags") or []))

    for pid, entry in mylist_data.items():
        if pid == paper_id or pid in graph_ids:
            continue
        # Parse added_at to tz-aware datetime
        added_at_str = entry.get("added_at", "")
        if not added_at_str:
            continue
        try:
            added_dt = datetime.fromisoformat(added_at_str)
            if added_dt.tzinfo is None:
                added_dt = added_dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        if added_dt > gen_dt:
            entry_paper = entry.get("paper", {})
            entry_tags = set(t.lower() for t in (entry_paper.get("tags") or []))
            if focal_tags & entry_tags:
                return True

    return False


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
    """Synchronously build the full related works graph."""
    from app.services.paper_service import get_paper_by_id
    from app.services.paper_content_service import get_related_work_section

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

    # Build multi-hop graph
    nodes, edges = build_multi_hop_graph(focal_paper, all_papers, client)

    graph = LiteratureSurveyGraph(
        focal_paper_id=focal_paper["id"],
        nodes=nodes,
        edges=edges,
    )

    # Get related work from original paper (cached), fetch on-demand if not cached
    related_work_html = get_related_work_section(paper_id)
    if related_work_html is None:
        from app.services.paper_content_service import fetch_and_cache_paper_content
        paper_url = focal_paper.get("url", "")
        fetch_and_cache_paper_content(paper_id, paper_url)
        related_work_html = get_related_work_section(paper_id) or ""
    related_work_source = "arxiv_html" if related_work_html else "none"

    # Save related papers to exploration folder
    folder = settings.explorations_dir / safe_filename(focal_paper["id"])
    folder.mkdir(parents=True, exist_ok=True)
    related_dir = folder / "related_papers"
    related_dir.mkdir(exist_ok=True)
    index_entries = []
    for node in nodes:
        if node.is_focal:
            continue
        # Find paper data for this node
        paper_data = next((p for p in all_papers if p.get("id") == node.id), None)
        if paper_data:
            pid_safe = safe_filename(node.id)
            (related_dir / f"{pid_safe}.json").write_text(
                json.dumps(paper_data, indent=2, default=str), encoding="utf-8"
            )
        index_entries.append({
            "id": node.id,
            "title": node.title,
            "authors": node.authors,
            "date": node.date,
            "url": node.url,
            "relevance_score": node.relevance_score,
            "hop_level": node.hop_level,
        })
    (folder / "related_papers_index.json").write_text(
        json.dumps(index_entries, indent=2, default=str), encoding="utf-8"
    )

    return LiteratureSurvey(
        focal_paper_id=focal_paper["id"],
        graph=graph,
        related_work_html=related_work_html,
        related_work_source=related_work_source,
        paper_count=len(nodes),
        status="ready",
    )


def _build_survey_bg(paper_id: str, all_papers: list[dict]) -> None:
    """Background thread target for survey generation."""
    try:
        survey = _build_survey_sync(paper_id, all_papers)
        _save_survey(survey)
        logger.info(f"Related works graph generated for {paper_id}")
    except Exception as e:
        logger.error(f"Related works generation failed for {paper_id}: {e}")
        try:
            error_survey = LiteratureSurvey(
                focal_paper_id=paper_id,
                graph=LiteratureSurveyGraph(focal_paper_id=paper_id, nodes=[], edges=[]),
                status="error",
                paper_count=0,
            )
            _save_survey(error_survey)
        except Exception:
            pass
    finally:
        with _lock:
            _generating.discard(paper_id)


def start_survey_generation(paper_id: str, all_papers: list[dict], force: bool = False) -> str:
    """Kick off background survey generation. Returns current status string."""
    with _lock:
        if paper_id in _generating:
            return "generating"

    # Already done?
    if not force:
        existing = get_survey(paper_id)
        if existing and existing.status == "ready":
            return "ready"

    with _lock:
        _generating.add(paper_id)

    t = threading.Thread(target=_build_survey_bg, args=(paper_id, all_papers), daemon=True)
    t.start()
    return "generating"
