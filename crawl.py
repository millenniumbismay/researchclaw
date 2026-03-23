"""
ResearchCrawl - crawl.py
Fetches research papers from arXiv, Semantic Scholar, HuggingFace Daily Papers,
and Twitter/X, scores relevance, and saves new papers to filtered_papers.json
for summarize.py to process.
"""

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
import yaml

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


@dataclass
class Paper:
    id: str
    title: str
    authors: list
    abstract: str
    url: str
    source: str
    date: str
    relevance_score: float
    source_tags: list = field(default_factory=list)
    tags: list = field(default_factory=list)        # e.g. ["Diffusion", "Reasoning"]
    confidence: int = 0                              # 1-5, 5 = highly aligned with tags


def load_preferences(path: str = "preferences.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def compute_relevance(title: str, abstract: str, prefs: dict) -> float:
    """Score paper relevance using keyword matching in title and abstract."""
    all_terms = [t.lower() for t in prefs.get("topics", []) + prefs.get("keywords", [])]
    if not all_terms:
        return 0.5

    title_lower = title.lower()
    abstract_lower = abstract.lower()

    title_matches = sum(1 for t in all_terms if t in title_lower)
    abstract_matches = sum(1 for t in all_terms if t in abstract_lower)

    # score = (title_matches * 2 + abstract_matches) / total_keywords, capped at 1.0
    raw_score = (title_matches * 2 + abstract_matches) / len(all_terms)
    return min(1.0, raw_score)


def analyze_paper(client, paper: "Paper", prefs: dict) -> None:
    """Use Claude API to assign tags and confidence score to a paper.

    Note: We only have the abstract from the API, not the full paper text.
    Tag and confidence assignment is therefore based solely on title + abstract.

    Falls back to keyword matching if Claude API is unavailable.
    Tags are drawn from the user's topics + keywords preference list.
    """
    topics_and_keywords = prefs.get("topics", []) + prefs.get("keywords", [])

    if client is None or not ANTHROPIC_AVAILABLE:
        # Fallback: keyword matching
        text = (paper.title + " " + paper.abstract).lower()
        matched = [t for t in topics_and_keywords if t.lower() in text]
        paper.tags = matched
        paper.confidence = min(5, len(matched) * 2) if matched else 1
        return

    topics_str = "\n".join(f"- {t}" for t in topics_and_keywords)
    prompt = f"""You are a research paper classifier. Given a paper abstract and a list of research topics/keywords of interest, your job is to:
1. Assign relevant tags from the preference list that this paper matches
2. Give a confidence score 1-5 (5 = paper is deeply focused on these topics, 1 = barely related)

User preferences (topics + keywords):
{topics_str}

Paper title: {paper.title}
Abstract: {paper.abstract[:2000]}

Respond in JSON only, no explanation:
{{"tags": ["tag1", "tag2"], "confidence": 4}}

Only include tags that genuinely apply. Tags must come from the user preference list (topics or keywords). If nothing matches, return {{"tags": [], "confidence": 1}}."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text.strip()
                break

        # Strip markdown code fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        result = json.loads(text)
        paper.tags = result.get("tags", [])
        paper.confidence = int(result.get("confidence", 1))
    except Exception as e:
        print(f"  [analyze_paper] Error for '{paper.title[:50]}': {e} — falling back to keyword match")
        text = (paper.title + " " + paper.abstract).lower()
        matched = [t for t in topics_and_keywords if t.lower() in text]
        paper.tags = matched
        paper.confidence = min(5, len(matched) * 2) if matched else 1


def fetch_arxiv_metadata(arxiv_id: str, prefs: dict) -> Optional["Paper"]:
    """Fetch metadata for a single arXiv paper by ID."""
    url = "http://export.arxiv.org/api/query"
    params = {"id_list": arxiv_id}

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[arXiv metadata] Error fetching {arxiv_id}: {e}")
        return None

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return None

    entries = root.findall("atom:entry", ns)
    if not entries:
        return None

    try:
        entry = entries[0]
        raw_id = entry.find("atom:id", ns).text.strip()
        canonical_id = raw_id.split("/abs/")[-1].strip()

        title_el = entry.find("atom:title", ns)
        title = (title_el.text or "").strip().replace("\n", " ")

        abstract_el = entry.find("atom:summary", ns)
        abstract = (abstract_el.text or "").strip().replace("\n", " ")

        authors = []
        for author_el in entry.findall("atom:author", ns):
            name_el = author_el.find("atom:name", ns)
            if name_el is not None:
                authors.append((name_el.text or "").strip())

        published_el = entry.find("atom:published", ns)
        published_str = (published_el.text or "").strip()
        published_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        date_str = published_dt.strftime("%Y-%m-%d")

        score = compute_relevance(title, abstract, prefs)

        return Paper(
            id=f"arxiv:{canonical_id}",
            title=title,
            authors=authors,
            abstract=abstract,
            url=f"https://arxiv.org/abs/{canonical_id}",
            source="arxiv",
            date=date_str,
            relevance_score=round(score, 4),
            source_tags=[],
        )
    except Exception:
        return None


def fetch_arxiv(prefs: dict) -> list:
    """Fetch papers from arXiv API."""
    papers = []
    topics = prefs.get("topics", [])
    keywords = prefs.get("keywords", [])
    max_results = prefs.get("max_results_per_source", 20)
    days_back = prefs.get("days_lookback", 7)
    cutoff = datetime.now() - timedelta(days=days_back)

    terms = (topics + keywords)[:8]  # limit query complexity
    if not terms:
        return papers

    # Build OR query across all terms
    query_parts = [f'all:"{t}"' for t in terms]
    search_query = " OR ".join(query_parts)

    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results * 2,  # over-fetch to account for date filtering
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[arXiv] Error fetching: {e}")
        return papers

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        print(f"[arXiv] XML parse error: {e}")
        return papers

    for entry in root.findall("atom:entry", ns):
        try:
            raw_id = entry.find("atom:id", ns).text.strip()
            arxiv_id = raw_id.split("/abs/")[-1].strip()

            title_el = entry.find("atom:title", ns)
            title = (title_el.text or "").strip().replace("\n", " ")

            abstract_el = entry.find("atom:summary", ns)
            abstract = (abstract_el.text or "").strip().replace("\n", " ")

            authors = []
            for author_el in entry.findall("atom:author", ns):
                name_el = author_el.find("atom:name", ns)
                if name_el is not None:
                    authors.append((name_el.text or "").strip())

            published_el = entry.find("atom:published", ns)
            published_str = (published_el.text or "").strip()
            published_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))

            # Filter by date (compare naive datetimes)
            if published_dt.replace(tzinfo=None) < cutoff:
                continue

            date_str = published_dt.strftime("%Y-%m-%d")
            score = compute_relevance(title, abstract, prefs)

            papers.append(
                Paper(
                    id=f"arxiv:{arxiv_id}",
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    url=f"https://arxiv.org/abs/{arxiv_id}",
                    source="arxiv",
                    date=date_str,
                    relevance_score=round(score, 4),
                    source_tags=["arxiv"],
                )
            )
        except Exception:
            continue

    print(f"[arXiv] Fetched {len(papers)} papers within date range")
    return papers


def fetch_semantic_scholar(prefs: dict) -> list:
    """Fetch papers from Semantic Scholar public API."""
    papers = []
    topics = prefs.get("topics", [])
    keywords = prefs.get("keywords", [])
    max_results = prefs.get("max_results_per_source", 20)
    days_back = prefs.get("days_lookback", 7)
    cutoff = datetime.now() - timedelta(days=days_back)

    # Use first few terms for the search query
    terms = (topics + keywords)[:4]
    if not terms:
        return papers

    query = " ".join(terms[:3])
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "fields": "title,authors,abstract,url,year,publicationDate,externalIds",
        "limit": max_results,
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[Semantic Scholar] Error fetching: {e}")
        return papers

    for item in data.get("data", []):
        try:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            abstract = (item.get("abstract") or "").strip()

            # Date handling
            pub_date = item.get("publicationDate")
            if pub_date:
                try:
                    pub_dt = datetime.strptime(pub_date, "%Y-%m-%d")
                    if pub_dt < cutoff:
                        continue
                    date_str = pub_date
                except ValueError:
                    date_str = str(item.get("year", "unknown"))
            else:
                date_str = str(item.get("year", "unknown"))

            authors = [a.get("name", "") for a in (item.get("authors") or [])]

            # Determine canonical ID and URL
            ext_ids = item.get("externalIds") or {}
            if "ArXiv" in ext_ids:
                arxiv_id = ext_ids["ArXiv"]
                paper_id = f"arxiv:{arxiv_id}"
                paper_url = f"https://arxiv.org/abs/{arxiv_id}"
            elif "DOI" in ext_ids:
                doi = ext_ids["DOI"]
                paper_id = f"doi:{doi}"
                paper_url = item.get("url") or f"https://doi.org/{doi}"
            else:
                ss_id = item.get("paperId", "")
                if not ss_id:
                    continue
                paper_id = f"ss:{ss_id}"
                paper_url = item.get("url") or f"https://www.semanticscholar.org/paper/{ss_id}"

            score = compute_relevance(title, abstract, prefs)

            papers.append(
                Paper(
                    id=paper_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    url=paper_url,
                    source="semantic_scholar",
                    date=date_str,
                    relevance_score=round(score, 4),
                    source_tags=["semantic_scholar"],
                )
            )
        except Exception:
            continue

    print(f"[Semantic Scholar] Fetched {len(papers)} papers")
    return papers


def fetch_huggingface(prefs: dict) -> list:
    """Fetch curated daily papers from HuggingFace."""
    if not BS4_AVAILABLE:
        print("[HuggingFace] Skipping: beautifulsoup4 not installed (pip install beautifulsoup4)")
        return []

    papers = []
    days_back = prefs.get("days_lookback", 7)
    cutoff = datetime.now() - timedelta(days=days_back)

    try:
        resp = requests.get("https://huggingface.co/papers", timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"[HuggingFace] Error fetching page: {e}")
        return []

    # Extract arxiv IDs from /papers/XXXXXXX links
    arxiv_ids = []
    seen = set()
    try:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = re.match(r"^/papers/(\d{4}\.\d+)", href)
            if m:
                arxiv_id = m.group(1)
                if arxiv_id not in seen:
                    seen.add(arxiv_id)
                    arxiv_ids.append(arxiv_id)
    except Exception as e:
        print(f"[HuggingFace] Error parsing page: {e}")
        return []

    print(f"[HuggingFace] Found {len(arxiv_ids)} paper IDs, fetching metadata...")

    for arxiv_id in arxiv_ids:
        try:
            paper = fetch_arxiv_metadata(arxiv_id, prefs)
            if paper is None:
                continue

            # Check date filter
            try:
                pub_dt = datetime.strptime(paper.date, "%Y-%m-%d")
                if pub_dt < cutoff:
                    continue
            except ValueError:
                pass

            paper.source = "huggingface"
            paper.source_tags = ["huggingface"]
            papers.append(paper)
            time.sleep(0.5)  # be polite to arXiv rate limits
        except Exception:
            continue

    print(f"[HuggingFace] Fetched {len(papers)} papers within date range")
    return papers


def fetch_twitter(prefs: dict) -> list:
    """Fetch paper links from Twitter/X search (requires TWITTER_BEARER_TOKEN)."""
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        print("[Twitter] Skipping Twitter source: TWITTER_BEARER_TOKEN not set")
        return []

    papers = []
    days_back = prefs.get("days_lookback", 7)
    cutoff = datetime.now() - timedelta(days=days_back)

    # Build search query from preferences or use override
    search_query = prefs.get("twitter_search_query")
    if not search_query:
        topics = prefs.get("topics", [])
        keywords = prefs.get("keywords", [])
        terms = (topics + keywords)[:5]
        if not terms:
            print("[Twitter] Skipping: no topics or keywords configured")
            return []
        term_parts = " OR ".join(f'"{t}"' if " " in t else t for t in terms)
        search_query = f"(arxiv OR paper) ({term_parts})"

    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    params = {
        "query": search_query,
        "max_results": 100,
        "tweet.fields": "created_at,text",
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[Twitter] Error fetching tweets: {e}")
        return []

    # Extract arxiv IDs from tweet text
    arxiv_pattern = re.compile(r"arxiv\.org/abs/(\d{4}\.\d+)")
    seen_ids = set()
    arxiv_ids = []

    for tweet in data.get("data", []):
        text = tweet.get("text", "")
        for match in arxiv_pattern.finditer(text):
            arxiv_id = match.group(1)
            if arxiv_id not in seen_ids:
                seen_ids.add(arxiv_id)
                arxiv_ids.append(arxiv_id)

    print(f"[Twitter] Found {len(arxiv_ids)} unique arxiv IDs in tweets, fetching metadata...")

    for arxiv_id in arxiv_ids:
        try:
            paper = fetch_arxiv_metadata(arxiv_id, prefs)
            if paper is None:
                continue

            # Check date filter
            try:
                pub_dt = datetime.strptime(paper.date, "%Y-%m-%d")
                if pub_dt < cutoff:
                    continue
            except ValueError:
                pass

            paper.source = "twitter"
            paper.source_tags = ["twitter"]
            papers.append(paper)
            time.sleep(0.5)
        except Exception:
            continue

    print(f"[Twitter] Fetched {len(papers)} papers within date range")
    return papers


def main():
    prefs = load_preferences()
    sources = prefs.get("sources", ["arxiv"])
    # min_relevance_score in preferences.yaml is kept for backward compat but is UNUSED.
    # Filtering is done by confidence threshold (1-5 scale from Claude tag analysis).
    # Only papers with confidence >= 3 are forwarded to summarize.py.
    min_confidence = 3
    output_dir = Path(prefs.get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "papers").mkdir(parents=True, exist_ok=True)

    # Load existing cache to avoid re-processing
    cache_path = Path("papers_cache.json")
    if cache_path.exists():
        with open(cache_path) as f:
            cache = json.load(f)
    else:
        cache = {}

    all_papers = []

    if "arxiv" in sources:
        all_papers.extend(fetch_arxiv(prefs))
        time.sleep(1)  # be polite to arXiv rate limits

    if "semantic_scholar" in sources:
        all_papers.extend(fetch_semantic_scholar(prefs))

    if "huggingface" in sources:
        all_papers.extend(fetch_huggingface(prefs))

    if "twitter" in sources:
        all_papers.extend(fetch_twitter(prefs))

    # Deduplicate by ID, merging source_tags for papers seen from multiple sources
    seen_ids: dict = {}
    unique_papers = []
    for p in all_papers:
        if p.id not in seen_ids:
            seen_ids[p.id] = len(unique_papers)
            unique_papers.append(p)
        else:
            # Merge source_tags into the existing paper entry
            existing = unique_papers[seen_ids[p.id]]
            for tag in p.source_tags:
                if tag not in existing.source_tags:
                    existing.source_tags.append(tag)

    # Initialize Claude client for tag/confidence analysis
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    claude_client = None
    if api_key and ANTHROPIC_AVAILABLE:
        claude_client = anthropic.Anthropic(api_key=api_key)
        print(f"\n[analyze] Using Claude API for tag/confidence scoring ({len(unique_papers)} papers)...")
    else:
        print("\n[analyze] ANTHROPIC_API_KEY not set or anthropic not installed — using keyword fallback for tags/confidence")

    # Analyze papers in batches of 10 to respect rate limits
    batch_size = 10
    for i in range(0, len(unique_papers), batch_size):
        batch = unique_papers[i:i + batch_size]
        for paper in batch:
            analyze_paper(claude_client, paper, prefs)
        if claude_client and i + batch_size < len(unique_papers):
            time.sleep(1)  # 1s between batches to respect Claude rate limits

    # Filter by confidence threshold (replaces old relevance_score filter)
    filtered = [p for p in unique_papers if p.confidence >= min_confidence]

    # Only process papers not already in cache
    new_papers = [p for p in filtered if p.id not in cache]

    print(
        f"\nSummary: fetched={len(all_papers)}, unique={len(unique_papers)}, "
        f"confidence>={min_confidence}={len(filtered)}, new={len(new_papers)}"
    )
    # Note: min_relevance_score from preferences.yaml is not used for filtering.

    # Update cache with all papers that passed the threshold (not just new ones)
    for p in filtered:
        if p.id not in cache:
            cache[p.id] = {"title": p.title, "date": p.date}

    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)

    # Write new papers for summarize.py
    papers_data = [asdict(p) for p in new_papers]
    with open("filtered_papers.json", "w") as f:
        json.dump(papers_data, f, indent=2)

    print(f"Saved {len(new_papers)} new papers to filtered_papers.json")


if __name__ == "__main__":
    main()
