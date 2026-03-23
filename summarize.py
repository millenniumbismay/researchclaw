"""
ResearchClaw - summarize.py
Reads filtered_papers.json, generates Claude-powered structured summaries for new papers,
saves individual .md files, regenerates the output/index.md, and sends a Telegram notification.
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import anthropic
import requests
import yaml
from bs4 import BeautifulSoup

# Note: the original spec requested claude-3-5-haiku-20241022, which was retired
# on Feb 19, 2026. Using claude-haiku-4-5 as its current replacement.
MODEL = "claude-haiku-4-5"

SUMMARY_PROMPT = """You are a research paper analyst for an expert ML researcher. Produce a structured summary with these exact sections:

**Abstract** (copy verbatim from the paper text below)

**Conclusion** (copy verbatim from the paper text if present, otherwise write "See paper")

**Introduction Highlights**
- What problem does this paper solve?
- Key contributions and how they improve over related work
- What specific gap or limitation does it address?

**Research Questions**
List the explicit or implicit research questions this paper investigates. If not stated, infer from introduction and experiments.

**Methodology & Experiments**
- Key methodologies and model architecture
- Important technical details: loss functions, reward signals, key equations (use LaTeX if helpful)
- Why this approach is preferred over alternatives
- Key experimental findings (highlight best results only — do NOT copy tables)

Paper title: {title}
Authors: {authors}

Paper content:
{full_text_or_abstract}"""


def load_preferences(path: str = "preferences.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def safe_filename(title: str) -> str:
    """Convert a paper title to a safe filename."""
    name = title.lower()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", "-", name.strip())
    name = re.sub(r"-+", "-", name)
    return name[:80].rstrip("-")


def paper_md_path(output_dir: Path, title: str) -> Path:
    return output_dir / "papers" / f"{safe_filename(title)}.md"


def paper_summary_path(output_dir: Path, title: str) -> Path:
    return output_dir / "summaries" / f"{safe_filename(title)}.md"


def write_summary_file(output_dir: Path, title: str, summary: str) -> Path:
    """Write summary text to output/summaries/{stem}.md (no frontmatter)."""
    path = paper_summary_path(output_dir, title)
    path.write_text(summary, encoding="utf-8")
    return path


def fetch_full_text(url: str) -> str:
    """Fetch full paper text from arXiv HTML. Returns "" on any failure."""
    # Extract arXiv ID from URL
    match = re.search(r"arxiv\.org/abs/([\w.]+?)(?:v\d+)?$", url)
    if not match:
        return ""
    arxiv_id = match.group(1)

    html_url = f"https://arxiv.org/html/{arxiv_id}"
    try:
        resp = requests.get(
            html_url,
            timeout=20,
            headers={"User-Agent": "ResearchClaw/1.0 (research paper summarizer)"},
        )
        time.sleep(0.5)
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()
    except Exception:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Try targeted sections first
    target_classes = ("abstract", "introduction", "conclusion", "method", "experiment", "result")
    sections = []
    for section in soup.find_all("section"):
        cls = " ".join(section.get("class", [])).lower()
        if any(t in cls for t in target_classes):
            sections.append(section.get_text(separator=" ", strip=True))

    if not sections:
        # Fall back to <p> tags inside <article> or <main>
        container = soup.find("article") or soup.find("main")
        if container:
            sections = [p.get_text(separator=" ", strip=True) for p in container.find_all("p")]

    if not sections:
        return ""

    text = " ".join(sections)

    # Clean up
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\[\d+(?:,\s*\d+)*\]", "", text)  # reference markers [1], [1,2]
    lines = text.split(". ")
    lines = [l for l in lines if not re.match(r"^\s*Figure\s+\d+", l, re.IGNORECASE)]
    lines = [l for l in lines if not re.match(r"^\s*Table\s+\d+", l, re.IGNORECASE)]
    text = ". ".join(lines)
    text = re.sub(r"\s+", " ", text).strip()

    return text[:12000]


def generate_summary(client: anthropic.Anthropic, paper: dict) -> str:
    """Call Claude API to produce a rich structured summary of a paper."""
    authors_str = ", ".join(paper.get("authors", [])[:5])
    if len(paper.get("authors", [])) > 5:
        authors_str += " et al."

    full_text = fetch_full_text(paper.get("url", ""))
    if len(full_text) > 500:
        full_text_or_abstract = full_text
    else:
        abstract = paper.get("abstract", "")[:3000]
        full_text_or_abstract = (
            abstract + "\n\n(inferred from abstract only)"
        )

    prompt = SUMMARY_PROMPT.format(
        title=paper["title"],
        authors=authors_str,
        full_text_or_abstract=full_text_or_abstract,
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    for block in response.content:
        if block.type == "text":
            return block.text.strip()
    return ""


def write_paper_file(output_dir: Path, paper: dict, summary: str) -> Path:
    """Write a single paper markdown file with YAML frontmatter."""
    authors_str = ", ".join(paper["authors"][:5])
    if len(paper["authors"]) > 5:
        authors_str += " et al."

    tags = paper.get("tags", [])
    confidence = paper.get("confidence", 0)
    source_tags = paper.get("source_tags", [])
    tags_display = " · ".join(tags) if tags else ""

    path = paper_md_path(output_dir, paper["title"])

    # Build frontmatter source_tags as YAML list
    source_tags_yaml = json.dumps(source_tags)
    tags_yaml = json.dumps(tags)

    abstract_short = (paper.get("abstract", "") or "")[:3000]
    stem = safe_filename(paper['title'])
    has_real_summary = bool(summary) and not summary.startswith("*Summary not generated")
    summary_ref = (
        f"*See [output/summaries/{stem}.md](../summaries/{stem}.md)*"
        if has_real_summary
        else "*Summary not generated. Click \"Summarize\" in My List or Dashboard to generate on demand.*"
    )
    content = f"""---
title: "{paper['title'].replace('"', "'")}"
authors: "{authors_str}"
date: "{paper['date']}"
url: "{paper['url']}"
source: "{paper['source']}"
source_tags: {source_tags_yaml}
tags: {tags_yaml}
confidence: {confidence}
relevance_score: {paper.get('relevance_score', 0)}
abstract: "{abstract_short.replace(chr(34), chr(39))}"
---

# {paper['title']}

> **Tags:** {tags_display}
> **Confidence:** {confidence}/5
> **Authors:** {authors_str} · {paper['date']}
> **Source:** {paper['source']} · [Read Paper →]({paper['url']})

---

{summary_ref}
"""
    path.write_text(content, encoding="utf-8")
    if has_real_summary:
        write_summary_file(output_dir, paper['title'], summary)
    return path


def infer_topic(title: str, abstract: str, tags: list, topics: list) -> str:
    """Assign a paper to its most likely topic, preferring assigned tags."""
    # Use assigned tags first
    for tag in tags:
        for topic in topics:
            if tag.lower() == topic.lower():
                return topic

    # Fall back to keyword matching
    text = (title + " " + abstract).lower()
    for topic in topics:
        if topic.lower() in text:
            return topic
    return "Other"


def regenerate_index(output_dir: Path, all_papers_meta: list, topics: list):
    """Rebuild output/index.md sorted by date, grouped by topic."""
    # Sort by date descending, then confidence descending
    sorted_papers = sorted(
        all_papers_meta,
        key=lambda p: (p.get("date", ""), p.get("confidence", 0)),
        reverse=True,
    )

    # Group by inferred topic
    groups: dict = {}
    for paper in sorted_papers:
        topic = infer_topic(
            paper.get("title", ""),
            paper.get("abstract", ""),
            paper.get("tags", []),
            topics,
        )
        groups.setdefault(topic, []).append(paper)

    lines = [
        "# ResearchClaw Index",
        "",
        f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        f"*Total papers: {len(sorted_papers)}*",
        "",
    ]

    for topic in topics + ["Other"]:
        if topic not in groups:
            continue
        lines.append(f"## {topic}")
        lines.append("")
        for paper in groups[topic]:
            title = paper.get("title", "Untitled")
            authors = paper.get("authors", [])
            author_str = authors[0] if authors else "Unknown"
            if len(authors) > 1:
                author_str += " et al."
            date = paper.get("date", "")
            tags = paper.get("tags", [])
            confidence = paper.get("confidence", 0)
            rel_path = f"papers/{safe_filename(title)}.md"
            score = paper.get("relevance_score", 0)
            tags_str = ", ".join(tags) if tags else ""

            lines.append(f"### [{title}]({rel_path})")
            lines.append(f"*{author_str} · {date} · confidence: {confidence}/5*")
            if tags_str:
                lines.append(f"**Tags:** {tags_str}")
            lines.append("")

    index_path = output_dir / "index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Regenerated {index_path} with {len(sorted_papers)} papers")


def notify_telegram(summary_text: str) -> None:
    """Send a Telegram notification with the crawl summary."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[Telegram] Skipping notification: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": summary_text,
        "parse_mode": "HTML",
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        print("[Telegram] Notification sent successfully")
    except Exception as e:
        print(f"[Telegram] Failed to send notification: {e}")


def main():
    prefs = load_preferences()
    output_dir = Path(prefs.get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "papers").mkdir(parents=True, exist_ok=True)
    (output_dir / "summaries").mkdir(parents=True, exist_ok=True)
    topics = prefs.get("topics", [])

    # Load new papers from crawl
    filtered_path = Path("filtered_papers.json")
    if not filtered_path.exists():
        print("No filtered_papers.json found. Run crawl.py first.")
        new_papers = []
    else:
        with open(filtered_path) as f:
            new_papers = json.load(f)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY not set. Skipping Claude summaries.")
        client = None
    else:
        client = anthropic.Anthropic(api_key=api_key)

    # Process new papers
    processed = 0
    processed_papers = []
    for paper in new_papers:
        out_path = paper_md_path(output_dir, paper["title"])
        if out_path.exists():
            print(f"  [skip] {paper['title'][:60]}...")
            continue

        summary = ""
        conf = paper.get("confidence", 0)
        if conf == 5 and client:
            try:
                summary = generate_summary(client, paper)
                print(f"  [ok] {paper['title'][:60]}...")
            except Exception as e:
                print(f"  [error] {paper['title'][:60]}: {e}")
                summary = paper.get("abstract", "")[:500]
        elif conf == 5 and not client:
            summary = paper.get("abstract", "")
        else:
            # confidence 3 or 4: write placeholder, skip Claude summary
            summary = "*Summary not generated. Click \"Summarize\" in My List to generate on demand.*"
            print(f"  [placeholder] {paper['title'][:60]}… (conf={conf})")

        write_paper_file(output_dir, paper, summary)
        processed_papers.append(paper)
        processed += 1

    print(f"\nProcessed {processed} new papers")

    # Collect ALL papers metadata for index (from all existing .md files + new ones)
    all_meta = []

    # Load metadata from existing paper files
    for md_file in (output_dir / "papers").glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            # Parse frontmatter
            if content.startswith("---"):
                end = content.index("---", 3)
                fm_text = content[3:end]
                fm = yaml.safe_load(fm_text)
                meta = {
                    "title": fm.get("title", md_file.stem),
                    "authors": [a.strip() for a in (fm.get("authors", "") or "").split(",")],
                    "date": fm.get("date", ""),
                    "url": fm.get("url", ""),
                    "source": fm.get("source", ""),
                    "source_tags": fm.get("source_tags", []),
                    "tags": fm.get("tags", []),
                    "confidence": fm.get("confidence", 0),
                    "relevance_score": fm.get("relevance_score", 0),
                    "abstract": "",
                }
                all_meta.append(meta)
        except Exception:
            continue

    # Merge in new papers that may not be on disk yet (edge case)
    existing_titles = {m["title"] for m in all_meta}
    for paper in new_papers:
        if paper["title"] not in existing_titles:
            all_meta.append(paper)

    regenerate_index(output_dir, all_meta, topics)

    # Send Telegram notification
    if processed_papers:
        all_tags = []
        for p in processed_papers:
            all_tags.extend(p.get("tags", []))
        unique_tags = list(dict.fromkeys(all_tags))  # dedupe preserving order
        tags_joined = ", ".join(unique_tags) if unique_tags else "N/A"

        # Top 5 by confidence
        top_papers = sorted(processed_papers, key=lambda p: p.get("confidence", 0), reverse=True)[:5]
        top_lines = []
        for p in top_papers:
            t = p.get("title", "Untitled")[:60]
            tags_str = ", ".join(p.get("tags", [])) or "—"
            conf = p.get("confidence", 0)
            top_lines.append(f"• <b>{t}</b> [{tags_str}] ({conf}/5)")

        top_papers_text = "\n".join(top_lines) if top_lines else "—"

        message = (
            f"🔬 <b>ResearchClaw Complete</b>\n\n"
            f"📄 <b>{processed} new papers</b> summarized today\n"
            f"🏷 Topics covered: {tags_joined}\n\n"
            f"Top papers:\n{top_papers_text}\n\n"
            f'<a href="http://localhost:7337/output">View full index →</a>'
        )
        notify_telegram(message)
    else:
        print("[Telegram] No new papers processed — skipping notification")


if __name__ == "__main__":
    main()
