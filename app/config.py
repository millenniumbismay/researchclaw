from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

class Settings(BaseSettings):
    base_dir: Path = BASE_DIR
    output_dir: Path = BASE_DIR / "output"
    papers_dir: Path = BASE_DIR / "output" / "papers"
    summaries_dir: Path = BASE_DIR / "output" / "summaries"
    explorations_dir: Path = BASE_DIR / "output" / "explorations"
    paper_content_dir: Path = BASE_DIR / "output" / "paper_content"
    autoresearch_dir: Path = BASE_DIR / "output" / "autoresearch"
    feedback_path: Path = BASE_DIR / "feedback.json"
    mylist_path: Path = BASE_DIR / "mylist.json"
    prefs_path: Path = BASE_DIR / "preferences.yaml"
    crawl_history_path: Path = BASE_DIR / "crawl_history.json"

    model_config = ConfigDict(env_prefix="RESEARCHCLAW_")

settings = Settings()
