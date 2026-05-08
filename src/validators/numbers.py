"""HTML ↔ raw JSON 숫자 대조 v2.

규칙 (CLAUDE.md §3.2 + 본 plan §6):
1. BeautifulSoup 으로 HTML 파싱.
2. ``<script>``, ``<style>``, ``<svg>`` 서브트리 제거.
3. ``data-noverify="true"`` 요소 제거.
4. 가시 텍스트에서 토큰: ``1,234,567`` / ``1234.5`` / ``12.3%``.
5. raw JSON 의 모든 numeric leaf 와 multiset 비교 (±0.1% 허용).

CLAUDE.md §2 모듈 의존성: validators 는 다른 src 모듈을 import 하지 않는다.
파일 시스템 + 인자만으로 동작 (UNIT 테스트 친화).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 1,234.56 / 1234 / 12.3% — 음수 부호 포함
_NUMBER_RE = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|-?\d+(?:\.\d+)?%?")

# raw JSON 에서 미리 walk-skip 할 키들 (시간/ID 등 노이즈)
_SKIP_KEYS = frozenset(
    {
        "fetched_at",
        "modify_date",
        "rcept_no",
        "rcept_dt",
        "rcept_date",
        "corp_code",
        "stock_code",
        "rcpNo",
    }
)

# 너무 작은 정수 (0, 1, …, 5 등) 는 데이터 매칭이 어려운 노이즈 → 제외
_TRIVIAL_INTS = frozenset({"0", "1", "2", "3", "4", "5"})


def _parse_number(token: str) -> float | None:
    if not token:
        return None
    t = token.replace(",", "").rstrip("%")
    try:
        return float(t)
    except ValueError:
        return None


def _walk_numbers(obj: Any, out: list[float], *, depth: int = 0) -> None:
    if depth > 12:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _SKIP_KEYS:
                continue
            _walk_numbers(v, out, depth=depth + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_numbers(v, out, depth=depth + 1)
    elif isinstance(obj, bool):
        return  # bool 도 int 의 subtype 이므로 명시 제외
    elif isinstance(obj, (int, float)):
        try:
            out.append(float(obj))
        except (ValueError, OverflowError):
            return
    elif isinstance(obj, str):
        # raw JSON 의 문자열 내 숫자도 허용 (e.g. "190,430")
        for m in _NUMBER_RE.findall(obj):
            v = _parse_number(m)
            if v is not None:
                out.append(v)


def _collect_raw_numbers(raw_dir: Path, ticker: str) -> list[float]:
    out: list[float] = []
    if not raw_dir.exists():
        return out
    for f in raw_dir.glob(f"{ticker}_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            _walk_numbers(data, out)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("raw json 파싱 실패 %s: %s", f, exc)
    # 시총 랭킹/섹터/거시 등 ticker 무관 파일도 비교에 포함
    for f in raw_dir.glob("_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            _walk_numbers(data, out)
        except (json.JSONDecodeError, OSError):
            pass
    return out


def _extract_html_numbers(html: str) -> list[str]:
    try:
        from bs4 import BeautifulSoup, Comment
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError("beautifulsoup4 미설치") from exc

    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "svg"]):
        tag.decompose()

    for tag in soup.find_all(attrs={"data-noverify": "true"}):
        tag.decompose()

    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()

    text = soup.get_text(" ", strip=True)
    return _NUMBER_RE.findall(text)


def _is_match(needle: float, haystack: list[float], *, tol: float = 0.001) -> bool:
    """needle 이 haystack 에 ±tol(상대) 또는 절대값 0.5 이내로 존재?

    정수형(예: 종가 190,430)은 정확히 일치해야 하지만 반올림으로 1차이가
    날 수 있으므로 절대 ≤0.5 도 허용한다.
    """
    if not haystack:
        return False
    needle_abs = abs(needle)
    for v in haystack:
        if v == needle:
            return True
        if abs(v - needle) <= 0.5:
            return True
        if needle_abs > 0 and abs(v - needle) / max(needle_abs, abs(v)) <= tol:
            return True
    return False


def verify_html_against_raw(
    html_path: Path,
    raw_dir: Path,
    *,
    ticker: str,
) -> dict[str, Any]:
    """HTML 내 숫자를 raw JSON 모음과 대조.

    Returns dict with: checked, matched, noisy, unmatched, examples,
    css_class, note.
    """
    html = html_path.read_text(encoding="utf-8")
    raw_numbers = _collect_raw_numbers(raw_dir, ticker)
    raw_set = list(set(round(v, 4) for v in raw_numbers))

    tokens = _extract_html_numbers(html)

    checked = 0
    matched = 0
    noisy = 0
    unmatched_examples: list[str] = []

    for tok in tokens:
        # 사소한 0/1/… 은 노이즈로 취급
        clean = tok.replace(",", "").rstrip("%")
        if clean in _TRIVIAL_INTS:
            noisy += 1
            continue
        v = _parse_number(tok)
        if v is None:
            noisy += 1
            continue
        checked += 1
        if _is_match(v, raw_set):
            matched += 1
        else:
            if len(unmatched_examples) < 5:
                unmatched_examples.append(tok)

    unmatched = checked - matched
    ratio = (unmatched / checked) if checked else 0.0
    css_class = "fail" if ratio > 0.05 else "pass"

    note = ""
    if not raw_numbers:
        note = "raw 데이터 없음 — 검증 불가"
        css_class = "fail"

    return {
        "checked": checked,
        "matched": matched,
        "noisy": noisy,
        "unmatched": unmatched,
        "examples": unmatched_examples,
        "css_class": css_class,
        "note": note,
    }


def write_sidecar(result: dict[str, Any], html_path: Path) -> Path:
    """``{stem}.validation.json`` 사이드카 저장."""
    out = html_path.with_suffix(".validation.json")
    out.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return out
