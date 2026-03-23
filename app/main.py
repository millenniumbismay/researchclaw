"""FastAPI app factory for ResearchClaw."""

import markdown as md_lib
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings

def create_app() -> FastAPI:
    app = FastAPI(title="ResearchClaw UI")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Ensure required dirs exist
    settings.summaries_dir.mkdir(parents=True, exist_ok=True)
    settings.explorations_dir.mkdir(parents=True, exist_ok=True)

    # Static files
    app.mount("/static", StaticFiles(directory=str(settings.base_dir / "static")), name="static")

    # Register routers
    from app.routes import papers, mylist, explorations, settings as settings_routes, feedback
    app.include_router(papers.router)
    app.include_router(mylist.router)
    app.include_router(explorations.router)
    app.include_router(settings_routes.router)
    app.include_router(feedback.router)

    @app.get("/", response_class=HTMLResponse)
    async def root():
        template_path = settings.base_dir / "templates" / "index.html"
        return template_path.read_text(encoding="utf-8")

    @app.get("/output", response_class=HTMLResponse)
    async def output_index():
        index_path = settings.output_dir / "index.md"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="output/index.md not found — run the crawl first")
        content = index_path.read_text()
        body = md_lib.markdown(content, extensions=["tables", "fenced_code"])
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>ResearchClaw — Index</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0f1117; color: #e4e6f0;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    padding: 40px 24px 80px; line-height: 1.65;
  }}
  .content {{ max-width: 800px; margin: 0 auto; }}
  h1, h2, h3 {{ font-weight: 700; margin: 1.4em 0 0.5em; line-height: 1.3; }}
  h1 {{ font-size: 1.8rem; }} h2 {{ font-size: 1.3rem; color: #c8cae0; }} h3 {{ font-size: 1.05rem; color: #a8aacc; }}
  p {{ margin: 0.6em 0; }}
  a {{ color: #7c6af7; }} a:hover {{ text-decoration: underline; }}
  code {{ background: #1a1d27; border-radius: 4px; padding: 2px 6px; font-size: 0.88em; }}
  pre {{ background: #1a1d27; border-radius: 8px; padding: 16px; overflow-x: auto; margin: 1em 0; }}
  pre code {{ background: none; padding: 0; }}
  hr {{ border: none; border-top: 1px solid #2a2d3e; margin: 2em 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1em 0; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #2a2d3e; font-size: 0.9rem; }}
  th {{ color: #6b7080; font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; }}
  .back {{ display: inline-block; margin-bottom: 28px; color: #7c6af7; font-size: 0.9rem; }}
</style>
</head>
<body>
<div class="content">
  <a href="/" class="back">← Back to ResearchClaw</a>
  {body}
</div>
</body>
</html>"""
        return html

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    return app


app = create_app()
