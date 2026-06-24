from __future__ import annotations

from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from .dependencies import get_store
from .models import ContextQuery
from .store import CodeMeshReadStore


router = APIRouter(default_response_class=HTMLResponse)


@router.get("/ui")
async def dashboard(store: CodeMeshReadStore = Depends(get_store)) -> HTMLResponse:
    health = await store.health()
    repositories = await store.list_repositories(limit=8)
    runs = await store.list_ingestion_runs(limit=8)

    body = f"""
        <section class="toolbar">
            <form action="/ui/search" method="get" class="search-form">
                <input name="query" type="search" placeholder="Search indexed context" required>
                <input name="repository_id" placeholder="Repository id or alias">
                <button type="submit">Search</button>
            </form>
        </section>
        <section class="grid">
            <div class="panel">
                <h2>Service</h2>
                <dl class="metrics">
                    <div><dt>Status</dt><dd>{_badge(health.status)}</dd></div>
                    <div><dt>Checked</dt><dd>{_value(health.checked_at)}</dd></div>
                    <div><dt>Components</dt><dd>{len(health.components)}</dd></div>
                </dl>
            </div>
            <div class="panel">
                <h2>Repositories</h2>
                {_repository_table(repositories.repositories)}
                <p class="actions"><a href="/ui/repositories">View all repositories</a></p>
            </div>
        </section>
        <section class="panel">
            <h2>Recent Ingestion Runs</h2>
            {_run_table(runs.runs)}
            <p class="actions"><a href="/ui/runs">View all runs</a></p>
        </section>
    """
    return _page("Dashboard", body, active="dashboard")


@router.get("/ui/repositories")
async def repositories(store: CodeMeshReadStore = Depends(get_store)) -> HTMLResponse:
    response = await store.list_repositories(limit=100)
    body = f"""
        <section class="panel">
            <h2>Repositories</h2>
            {_repository_table(response.repositories, detailed=True)}
        </section>
    """
    return _page("Repositories", body, active="repositories")


@router.get("/ui/repositories/{repository_id:path}")
async def repository_detail(
    repository_id: str,
    store: CodeMeshReadStore = Depends(get_store),
) -> HTMLResponse:
    status = await store.get_repository_status(repository_id)
    runs = await store.list_ingestion_runs(repository_id=status.repository_id, limit=20)
    repository = status.repository

    if repository is None:
        heading = _value(status.repository_id)
        repository_panel = '<p class="empty">Repository metadata is not available.</p>'
    else:
        heading = _value(repository.alias or repository.repository_id)
        repository_panel = f"""
            <dl class="metrics metrics-wide">
                <div><dt>Repository ID</dt><dd>{_value(repository.repository_id)}</dd></div>
                <div><dt>Root</dt><dd>{_value(repository.root_path)}</dd></div>
                <div><dt>Branch</dt><dd>{_value(repository.branch)}</dd></div>
                <div><dt>Commit</dt><dd>{_short_value(repository.commit)}</dd></div>
                <div><dt>Last Stage</dt><dd>{_badge(repository.last_stage)}</dd></div>
                <div><dt>Last Seen</dt><dd>{_value(repository.last_seen_at)}</dd></div>
            </dl>
        """

    body = f"""
        <section class="title-row">
            <div>
                <h1>{heading}</h1>
                <p class="muted">Repository status and recent ingestion history.</p>
            </div>
            <a class="button-link" href="/repositories/{quote(repository_id, safe="")}">JSON</a>
        </section>
        <section class="grid">
            <div class="panel">
                <h2>Repository</h2>
                {repository_panel}
            </div>
            <div class="panel">
                <h2>Freshness</h2>
                <dl class="metrics">
                    <div><dt>Status</dt><dd>{_badge(status.freshness.get("status"))}</dd></div>
                    <div><dt>Stale</dt><dd>{_value(status.freshness.get("is_stale"))}</dd></div>
                    <div><dt>Generated</dt><dd>{_value(status.generated_at)}</dd></div>
                </dl>
            </div>
        </section>
        <section class="panel">
            <h2>Refresh</h2>
            <dl class="metrics metrics-wide">
                <div><dt>Status</dt><dd>{_badge(status.refresh.get("status"))}</dd></div>
                <div><dt>Changed</dt><dd>{_value(status.refresh.get("changed"))}</dd></div>
                <div><dt>Latest Run</dt><dd>{_value(status.refresh.get("latest_run_id"))}</dd></div>
                <div><dt>Finished</dt><dd>{_value(status.refresh.get("finished_at"))}</dd></div>
                <div><dt>Diagnostics</dt><dd>{_value(status.refresh.get("diagnostic_count"))}</dd></div>
                <div><dt>Action</dt><dd>{_value(status.refresh.get("recommended_action"))}</dd></div>
            </dl>
            <p class="muted">{_value(status.refresh.get("detail"))}</p>
        </section>
        <section class="panel">
            <h2>Counts</h2>
            {_count_table(status.counts)}
        </section>
        <section class="panel">
            <h2>Recent Runs</h2>
            {_run_table(runs.runs)}
        </section>
    """
    return _page("Repository", body, active="repositories")


@router.get("/ui/runs")
async def ingestion_runs(
    repository_id: str | None = None,
    store: CodeMeshReadStore = Depends(get_store),
) -> HTMLResponse:
    response = await store.list_ingestion_runs(repository_id=repository_id, limit=100)
    body = f"""
        <section class="toolbar">
            <form action="/ui/runs" method="get" class="search-form narrow">
                <input name="repository_id" placeholder="Repository id or alias" value="{_attr(repository_id)}">
                <button type="submit">Filter</button>
            </form>
        </section>
        <section class="panel">
            <h2>Ingestion Runs</h2>
            {_run_table(response.runs)}
        </section>
    """
    return _page("Ingestion Runs", body, active="runs")


@router.get("/ui/search")
async def search(
    query: str | None = None,
    repository_id: str | None = None,
    limit: int = Query(default=12, ge=1, le=50),
    store: CodeMeshReadStore = Depends(get_store),
) -> HTMLResponse:
    results = None
    if query:
        results = await store.search_context(
            ContextQuery(
                query=query,
                repository_id=repository_id or None,
                limit=limit,
                expand_context=False,
                include_context_relationships=False,
            )
        )

    body = f"""
        <section class="toolbar">
            <form action="/ui/search" method="get" class="search-form">
                <input name="query" type="search" placeholder="Search indexed context" value="{_attr(query)}" required>
                <input name="repository_id" placeholder="Repository id or alias" value="{_attr(repository_id)}">
                <input name="limit" type="number" min="1" max="50" value="{limit}">
                <button type="submit">Search</button>
            </form>
        </section>
        <section class="panel">
            <h2>Search Results</h2>
            {_search_results(results)}
        </section>
    """
    return _page("Search", body, active="search")


def _page(title: str, body: str, *, active: str) -> HTMLResponse:
    nav = "".join(
        _nav_link(label, href, active == key)
        for key, label, href in [
            ("dashboard", "Dashboard", "/ui"),
            ("repositories", "Repositories", "/ui/repositories"),
            ("runs", "Runs", "/ui/runs"),
            ("search", "Search", "/ui/search"),
        ]
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} - CodeMesh</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fa;
      --surface: #ffffff;
      --surface-alt: #eef3f8;
      --text: #17202a;
      --muted: #5d6b7a;
      --line: #d8e0e8;
      --accent: #0f766e;
      --accent-strong: #0b5f59;
      --warn: #8a5a00;
      --bad: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    header {{
      background: var(--surface);
      border-bottom: 1px solid var(--line);
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .shell {{ max-width: 1180px; margin: 0 auto; padding: 0 20px; }}
    .topbar {{ display: flex; align-items: center; justify-content: space-between; min-height: 58px; gap: 20px; }}
    .brand {{ font-size: 18px; font-weight: 700; color: var(--text); text-decoration: none; }}
    nav {{ display: flex; gap: 4px; flex-wrap: wrap; }}
    nav a {{ color: var(--muted); text-decoration: none; padding: 8px 10px; border-radius: 6px; }}
    nav a.active, nav a:hover {{ color: var(--text); background: var(--surface-alt); }}
    main {{ padding: 24px 0 40px; }}
    h1 {{ font-size: 24px; margin: 0; }}
    h2 {{ font-size: 16px; margin: 0 0 14px; }}
    a {{ color: var(--accent-strong); }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }}
    .panel, .toolbar {{ background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
    .title-row {{ display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 16px; }}
    .muted, .empty {{ color: var(--muted); }}
    .actions {{ margin: 12px 0 0; }}
    .button-link, button {{
      appearance: none;
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #fff;
      border-radius: 6px;
      padding: 8px 12px;
      text-decoration: none;
      font: inherit;
      cursor: pointer;
      white-space: nowrap;
    }}
    button:hover, .button-link:hover {{ background: var(--accent-strong); border-color: var(--accent-strong); }}
    .search-form {{ display: grid; grid-template-columns: minmax(220px, 1fr) minmax(180px, 280px) 84px 84px; gap: 10px; }}
    .search-form.narrow {{ grid-template-columns: minmax(220px, 360px) 84px; }}
    input {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      color: var(--text);
      font: inherit;
      background: #fff;
    }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 9px 8px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }}
    th {{ color: var(--muted); font-size: 12px; font-weight: 600; text-transform: uppercase; }}
    tr:last-child td {{ border-bottom: 0; }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 0; }}
    .metrics-wide {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .metrics div {{ background: var(--surface-alt); border-radius: 6px; padding: 10px; min-width: 0; }}
    dt {{ color: var(--muted); font-size: 12px; margin-bottom: 4px; }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
    .badge {{ display: inline-block; background: var(--surface-alt); color: var(--text); border: 1px solid var(--line); border-radius: 999px; padding: 2px 8px; }}
    .badge.completed, .badge.healthy {{ color: var(--accent-strong); border-color: #9ad4cd; background: #e8f6f4; }}
    .badge.failed, .badge.unhealthy {{ color: var(--bad); border-color: #f2b8b5; background: #fff0ef; }}
    .badge.unknown {{ color: var(--warn); border-color: #ebd28a; background: #fff7da; }}
    .result-list {{ display: grid; gap: 12px; }}
    .result {{ border-bottom: 1px solid var(--line); padding-bottom: 12px; }}
    .result:last-child {{ border-bottom: 0; padding-bottom: 0; }}
    .result-title {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }}
    .preview {{ margin: 8px 0 0; color: var(--muted); white-space: pre-wrap; }}
    @media (max-width: 820px) {{
      .topbar, .title-row {{ align-items: flex-start; flex-direction: column; }}
      .grid, .metrics, .metrics-wide {{ grid-template-columns: 1fr; }}
      .search-form, .search-form.narrow {{ grid-template-columns: 1fr; }}
      th.optional, td.optional {{ display: none; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="shell topbar">
      <a class="brand" href="/ui">CodeMesh</a>
      <nav>{nav}</nav>
    </div>
  </header>
  <main class="shell">{body}</main>
</body>
</html>"""
    return HTMLResponse(html)


def _nav_link(label: str, href: str, active: bool) -> str:
    class_name = "active" if active else ""
    return f'<a class="{class_name}" href="{href}">{escape(label)}</a>'


def _repository_table(repositories: list, *, detailed: bool = False) -> str:
    if not repositories:
        return '<p class="empty">No repositories have been indexed.</p>'

    optional_heading = '<th class="optional">Root</th>' if detailed else ""
    rows = []
    for repository in repositories:
        identity = repository.alias or repository.repository_id
        href = f"/ui/repositories/{quote(repository.repository_id, safe='')}"
        optional_cell = (
            f'<td class="optional">{_value(repository.root_path)}</td>'
            if detailed
            else ""
        )
        rows.append(
            "<tr>"
            f'<td><a href="{href}">{_value(identity)}</a><br><span class="muted">{_value(repository.repository_id)}</span></td>'
            f"<td>{_value(repository.node_count)}</td>"
            f"<td>{_value(repository.relationship_count)}</td>"
            f"<td>{_value(repository.content_count)}</td>"
            f"<td>{_badge(repository.last_stage)}</td>"
            f"{optional_cell}"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Repository</th><th>Nodes</th><th>Edges</th><th>Content</th><th>Stage</th>"
        f"{optional_heading}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _run_table(runs: list) -> str:
    if not runs:
        return '<p class="empty">No ingestion runs are available.</p>'

    rows = []
    for run in runs:
        repo_href = f"/ui/repositories/{quote(run.repository_id, safe='')}"
        rows.append(
            "<tr>"
            f'<td>{_value(run.run_id)}<br><span class="muted">{_value(run.language)} / {_value(run.parser_name)}</span></td>'
            f'<td><a href="{repo_href}">{_value(run.repository_id)}</a></td>'
            f"<td>{_badge(run.stage)}</td>"
            f"<td>{_value(run.node_count)}</td>"
            f"<td>{_value(run.relationship_count)}</td>"
            f"<td>{_value(run.content_count)}</td>"
            f'<td class="optional">{_value(run.started_at)}</td>'
            f'<td class="optional">{_value(run.finished_at)}</td>'
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Run</th><th>Repository</th><th>Stage</th><th>Nodes</th>"
        '<th>Edges</th><th>Content</th><th class="optional">Started</th>'
        f'<th class="optional">Finished</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
    )


def _count_table(counts: dict) -> str:
    if not counts:
        return '<p class="empty">No count diagnostics are available.</p>'

    rows = [
        f"<tr><td>{_value(key)}</td><td>{_value(value)}</td></tr>"
        for key, value in sorted(counts.items())
    ]
    return f"<table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _search_results(results: object | None) -> str:
    if results is None:
        return '<p class="empty">Enter a query to inspect indexed context.</p>'

    hits = getattr(results, "hits", [])
    if not hits:
        return '<p class="empty">No matching context was found.</p>'

    items = []
    for hit in hits:
        location = f"{hit.file_path}:{hit.start_line}-{hit.end_line}"
        preview = f'<p class="preview">{_value(hit.preview)}</p>' if hit.preview else ""
        items.append(
            '<article class="result">'
            '<div class="result-title">'
            f'<div><strong>{_value(location)}</strong><br><span class="muted">{_value(hit.node_id)}</span></div>'
            f'<div>{_badge(hit.kind)} <span class="muted">{hit.score:.3f}</span></div>'
            "</div>"
            f"{preview}"
            "</article>"
        )
    return f'<div class="result-list">{"".join(items)}</div>'


def _badge(value: object | None) -> str:
    text = str(value) if value is not None and value != "" else "unknown"
    class_name = escape(text.lower().replace(" ", "-"))
    return f'<span class="badge {class_name}">{escape(text)}</span>'


def _value(value: object | None) -> str:
    if value is None or value == "":
        return "-"
    return escape(str(value))


def _short_value(value: object | None, length: int = 12) -> str:
    if value is None or value == "":
        return "-"
    text = str(value)
    if len(text) <= length:
        return escape(text)
    return f'<span title="{escape(text)}">{escape(text[:length])}</span>'


def _attr(value: object | None) -> str:
    return escape(str(value), quote=True) if value is not None else ""
