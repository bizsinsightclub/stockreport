"""LLM 슬롯 내 ``<span data-cite="file:path:value">`` claim-level 검증.

CLAUDE.md §3.3 (Phase 2):
- 모든 numeric claim 은 ``<span data-cite="file:json-path:value">token</span>`` 으로 wrap.
- raw_dir 안의 file 을 json-path 따라가서 value 와 일치 확인.
- wrap 안 된 numeric token 은 의무 위반 (uncited).

CLAUDE.md §2 모듈 의존성: validators 는 다른 src 모듈을 import 하지 않는다.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_NUMBER_RE = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|-?\d+(?:\.\d+)?%?")

# 표준 기술지표 lookback / 통계 상수 — raw 에 있을 수 없으므로 cite 의무 면제
_STANDARD_LOOKBACKS = frozenset({"52", "60", "90", "100", "120", "200", "252"})


def _is_trivial(token: str) -> bool:
    """cite 의무에서 면제할 trivial 상수 판단.

    - 소수점/퍼센트는 항상 cite 의무 (의미 있는 수치)
    - 0~31 정수: 일자/지표 기간 (RSI 14, MA20 등)
    - 1900~2100 정수: 연도
    - 표준 lookback (52w, 60일, 200일 등)
    """
    if "." in token or "%" in token:
        return False
    clean = token.replace(",", "")
    try:
        n = int(clean)
    except ValueError:
        return False
    if 0 <= n <= 31:
        return True
    if 1900 <= n <= 2100:
        return True
    if clean in _STANDARD_LOOKBACKS:
        return True
    return False


def _parse_number(token: str) -> float | None:
    if not token:
        return None
    t = token.replace(",", "").rstrip("%")
    try:
        return float(t)
    except ValueError:
        return None


def _follow_path(obj: Any, path: str) -> Any:
    """JSON path "data.signals.rsi" 또는 "data.records.0.종가" 따라가기."""
    if not path:
        return obj
    cur: Any = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                idx = int(part)
            except ValueError:
                return None
            cur = cur[idx] if 0 <= idx < len(cur) else None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _value_match(claim: float, raw: Any, *, tol: float = 0.001) -> bool:
    """수치 매칭 — ±0.1% 또는 ±0.5 절대 허용."""
    if isinstance(raw, bool):
        return False
    raw_num: float | None
    if isinstance(raw, (int, float)):
        raw_num = float(raw)
    elif isinstance(raw, str):
        raw_num = _parse_number(raw)
    else:
        return False
    if raw_num is None:
        return False
    if claim == raw_num:
        return True
    if abs(claim - raw_num) <= 0.5:
        return True
    base = max(abs(claim), abs(raw_num))
    if base > 0 and abs(claim - raw_num) / base <= tol:
        return True
    return False


def verify_html_citations(html_path: Path, raw_dir: Path) -> dict[str, Any]:
    """HTML 의 모든 LLM 슬롯에 대해 ``<span data-cite>`` 검증 + 의무 위반 체크."""
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("beautifulsoup4 미설치") from exc

    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    raw_cache: dict[str, Any] = {}

    def _load_raw(fname: str) -> Any:
        if fname in raw_cache:
            return raw_cache[fname]
        p = raw_dir / fname
        if not p.exists():
            raw_cache[fname] = None
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = None
        raw_cache[fname] = data
        return data

    cite_total = 0
    cite_matched = 0
    uncited_total = 0
    examples_mismatched: list[str] = []
    examples_uncited: list[str] = []

    slots = soup.find_all(attrs={"data-llm-slot": True})
    for slot in slots:
        # (a) data-cite 검증
        for span in slot.find_all("span", attrs={"data-cite": True}):
            cite = span.get("data-cite", "") or ""
            parts = cite.split(":", 2)
            cite_total += 1
            if len(parts) != 3:
                if len(examples_mismatched) < 5:
                    examples_mismatched.append(f"형식오류:{cite}")
                continue
            fname, path, value_str = parts
            claim = _parse_number(value_str)
            if claim is None:
                claim = _parse_number(span.get_text(strip=True))
            if claim is None:
                if len(examples_mismatched) < 5:
                    examples_mismatched.append(f"수치파싱실패:{cite}")
                continue
            data = _load_raw(fname)
            if data is None:
                if len(examples_mismatched) < 5:
                    examples_mismatched.append(f"파일없음:{fname}")
                continue
            raw_val = _follow_path(data, path)
            if _value_match(claim, raw_val):
                cite_matched += 1
            elif len(examples_mismatched) < 5:
                examples_mismatched.append(
                    f"불일치:{fname}:{path} claim={claim} raw={raw_val}"
                )

        # (b) 의무 위반 — slot 안 numeric token 중 cite span 안 들어간 것
        cited_texts: list[str] = [
            sp.get_text() for sp in slot.find_all("span", attrs={"data-cite": True})
        ]
        full_text = slot.get_text(" ", strip=True)
        all_tokens = _NUMBER_RE.findall(full_text)
        cited_tokens: list[str] = []
        for ct in cited_texts:
            cited_tokens.extend(_NUMBER_RE.findall(ct))

        remaining = list(all_tokens)
        for ct in cited_tokens:
            if ct in remaining:
                remaining.remove(ct)

        for tok in remaining:
            if _is_trivial(tok):
                continue
            uncited_total += 1
            if len(examples_uncited) < 5:
                examples_uncited.append(tok)

    total_claims = cite_total + uncited_total
    matched = cite_matched
    unmatched = (cite_total - cite_matched) + uncited_total
    ratio = (unmatched / total_claims) if total_claims else 0.0

    if total_claims == 0:
        css_class = "pending"  # LLM 슬롯이 아직 작성되지 않음 (사이드카 없음)
        note = "LLM 슬롯 미작성 — citation 검증 보류"
    else:
        css_class = "fail" if ratio > 0.05 else "pass"
        parts = []
        if cite_total - cite_matched > 0:
            parts.append(f"불일치 {cite_total - cite_matched}")
        if uncited_total > 0:
            parts.append(f"uncited {uncited_total}")
        note = " · ".join(parts)

    return {
        "cite_total": cite_total,
        "cite_matched": cite_matched,
        "uncited": uncited_total,
        "checked": total_claims,
        "matched": matched,
        "unmatched": unmatched,
        "examples_mismatched": examples_mismatched,
        "examples_uncited": examples_uncited,
        "css_class": css_class,
        "note": note,
    }


def write_citations_sidecar(result: dict[str, Any], html_path: Path) -> Path:
    """``{stem}.citations.json`` 사이드카 저장."""
    out = html_path.with_suffix(".citations.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
