"""Jinja2 환경 + render_skeleton + index 갱신.

CLAUDE.md §2: renderer 는 mcp_clients/collectors/fallbacks 를 import 하지 않는다.
analyzer 결과 + meta 정보가 ``ctx`` dict 로 들어와 HTML 문자열을 만든다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_KST = timezone(timedelta(hours=9))

from src.config import OUTPUT_DIR, TEMPLATE_DIR

logger = logging.getLogger(__name__)


def _env():
    """Jinja2 환경 lazy-init (Jinja 미설치시 명확한 에러)."""
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError("jinja2 미설치") from exc

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=False,
        lstrip_blocks=False,
    )
    return env


def render_skeleton(ctx: dict[str, Any]) -> str:
    """``dashboard.html.j2`` 를 ``ctx`` 로 렌더 → HTML 문자열."""
    env = _env()
    template = env.get_template("dashboard.html.j2")
    return template.render(**ctx)


def update_ticker_index(ticker: str, *, output_dir: Path = OUTPUT_DIR) -> Path:
    """``data/output/{ticker}/index.html`` 갱신."""
    folder = output_dir / ticker
    folder.mkdir(parents=True, exist_ok=True)

    reports = []
    for f in sorted(folder.glob("*.html"), reverse=True):
        if f.name == "index.html":
            continue
        if f.name.endswith(".validation.json"):
            continue
        date_part = f.stem
        size_kb = max(1, f.stat().st_size // 1024)
        reports.append({"date": date_part, "href": f.name, "size_kb": size_kb})

    env = _env()
    template = env.get_template("ticker_index.html.j2")
    html = template.render(
        ticker=ticker,
        name="",
        market="",
        reports=reports,
    )
    out = folder / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def update_root_index(*, output_dir: Path = OUTPUT_DIR) -> Path:
    """``data/output/index.html`` 갱신."""
    output_dir.mkdir(parents=True, exist_ok=True)
    tickers = []
    for child in sorted(output_dir.iterdir()):
        if not child.is_dir():
            continue
        if not (child.name.isdigit() and len(child.name) == 6):
            continue
        reports = [
            f for f in child.glob("*.html") if f.name != "index.html"
        ]
        if not reports:
            continue
        latest = max(reports, key=lambda f: f.stem)
        tickers.append(
            {
                "ticker": child.name,
                "name": "",
                "latest_date": latest.stem,
                "count": len(reports),
            }
        )

    env = _env()
    template = env.get_template("root_index.html.j2")
    html = template.render(
        tickers=tickers,
        generated_at=datetime.now(_KST).strftime("%Y-%m-%d %H:%M KST"),
    )
    out = output_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
