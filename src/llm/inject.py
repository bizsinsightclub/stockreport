"""LLM 사이드카 → 슬롯 inject + citation wrap.

CLAUDE.md §3.3 (Phase 2, 2026-05-09 도입).

사이드카 JSON 구조 (``data/llm/{ticker}/{date}.json``)::

    {
      "ticker": "329180",
      "as_of": "2026-05-08",
      "generated_at": "2026-05-09T...",
      "slots": {
        "<slot_id>": {
          "raw_text": "RSI(14) 61.2, 중립권 ...",
          "citations": [
            {"token": "61.2", "file": "329180_enriched.json",
             "path": "data.signals.rsi", "value": 61.2}
          ]
        }
      }
    }

각 slot raw_text 안에서 citation token 을 ``<span data-cite="file:path:value">``
로 wrap. citation 이 없는 슬롯은 raw_text 그대로 반환 (validator 가 uncited 로 잡음).
"""

from __future__ import annotations

import json
import logging
import re
from html import escape
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _format_value(v: Any) -> str:
    """data-cite value 직렬화. float 는 trailing 0 제거, int 는 그대로."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return f"{v:g}"
    if isinstance(v, int):
        return str(v)
    return str(v)


def _wrap_text(raw_text: str, citations: list[dict[str, Any]]) -> str:
    """citation token 을 마커로 임시 교체 → 일괄 wrap. 동일 token 의 cite 가
    여러 번 있으면 등장 순서대로 1회씩 매칭."""
    if not raw_text:
        return ""
    if not citations:
        return raw_text

    sorted_cites = sorted(
        enumerate(citations),
        key=lambda kv: -len(str(kv[1].get("token", ""))),
    )

    placeholders: list[tuple[str, str]] = []
    out = raw_text
    for i, c in sorted_cites:
        token = str(c.get("token") or "")
        if not token:
            continue
        file_ = str(c.get("file") or "")
        path = str(c.get("path") or "")
        value_ = _format_value(c.get("value"))
        cite_attr = escape(f"{file_}:{path}:{value_}", quote=True)
        wrap = f'<span data-cite="{cite_attr}">{escape(token)}</span>'
        marker = f"\x00CITE{i}\x01"
        if token in out:
            out = out.replace(token, marker, 1)
            placeholders.append((marker, wrap))
        else:
            logger.warning("LLM citation token 미발견: %r", token)

    for marker, wrap in placeholders:
        out = out.replace(marker, wrap)
    return out


def load_sidecar(ticker: str, report_date_iso: str, llm_dir: Path) -> dict[str, Any] | None:
    """``data/llm/{ticker}/{date}.json`` 로드. 없으면 None."""
    path = llm_dir / ticker / f"{report_date_iso}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("사이드카 로드 실패 %s: %s", path, exc)
        return None


def inject_slots(sidecar: dict[str, Any] | None) -> dict[str, str]:
    """사이드카 → ``{slot_id: html_with_citation_spans}``.

    None 또는 slots 비어있으면 빈 dict (호출부가 fallback 사용).
    ``lens`` 구조 (3 level × 3 timeframe = 9 텍스트/섹션) 는 ``inject_lens`` 가 처리.
    """
    if not sidecar or not isinstance(sidecar.get("slots"), dict):
        return {}
    out: dict[str, str] = {}
    for slot_id, payload in sidecar["slots"].items():
        if slot_id == "lens":
            continue  # lens 는 inject_lens 로 분리 처리
        if not isinstance(payload, dict):
            continue
        raw_text = str(payload.get("raw_text") or payload.get("text") or "")
        citations = payload.get("citations") or []
        if not isinstance(citations, list):
            citations = []
        out[slot_id] = _wrap_text(raw_text, citations)
    return out


# 섹션별 9-코멘트 키 (3 level × 3 timeframe). 사이드카 / 템플릿 양쪽 동일.
LENS_KEYS: tuple[str, ...] = (
    "beg_1d", "beg_3d", "beg_1w",
    "int_1d", "int_3d", "int_1w",
    "exp_1d", "exp_3d", "exp_1w",
)


def inject_lens(sidecar: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    """``slots.lens`` → ``{section_id: {key: html_with_citations}}``.

    sidecar 구조::

        {"slots": {"lens": {"s2_tech": {"beg_1d": {"raw_text", "citations"}, ...}}}}

    각 9 키 (LENS_KEYS) 의 텍스트를 wrap. 비어 있으면 결과 dict 에서 생략 (템플릿이
    fallback 으로 비워둠).
    """
    if not sidecar or not isinstance(sidecar.get("slots"), dict):
        return {}
    lens_root = sidecar["slots"].get("lens")
    if not isinstance(lens_root, dict):
        return {}

    out: dict[str, dict[str, str]] = {}
    for section_id, sec_payload in lens_root.items():
        if not isinstance(sec_payload, dict):
            continue
        sec_out: dict[str, str] = {}
        for key, item in sec_payload.items():
            if key not in LENS_KEYS or not isinstance(item, dict):
                continue
            raw_text = str(item.get("raw_text") or "")
            citations = item.get("citations") or []
            if not isinstance(citations, list):
                citations = []
            if raw_text:
                sec_out[key] = _wrap_text(raw_text, citations)
        if sec_out:
            out[section_id] = sec_out
    return out
