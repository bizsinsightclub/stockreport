"""공시 카테고리 분류 + 수주 금액·상대방 정규식 추출."""

from __future__ import annotations

import re
from typing import Any

from src.config import DISCLOSURE_CATEGORY_RULES

_AMOUNT_PATTERNS = [
    re.compile(r"계약금액\s*[:：]?\s*([0-9,]+)\s*(원|백만원|억원|십억원|조원)?"),
    re.compile(r"공급금액\s*[:：]?\s*([0-9,]+)\s*(원|백만원|억원|십억원|조원)?"),
    re.compile(r"(?:거래)?금액\s*[:：]?\s*([0-9,]+)\s*(원|백만원|억원|십억원|조원)?"),
]
_COUNTERPARTY_PATTERNS = [
    re.compile(r"계약상대방\s*[:：]?\s*([^\n,;\(]+)"),
    re.compile(r"매각상대방\s*[:：]?\s*([^\n,;\(]+)"),
]


def _classify_one(title: str) -> str:
    for cat, pat in DISCLOSURE_CATEGORY_RULES:
        if re.search(pat, title or ""):
            return cat
    return "기타"


def _extract_amount(text: str) -> str | None:
    for pat in _AMOUNT_PATTERNS:
        m = pat.search(text)
        if m:
            unit = m.group(2) or "원"
            return f"{m.group(1)}{unit}"
    return None


def _extract_counterparty(text: str) -> str | None:
    for pat in _COUNTERPARTY_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1).strip()
    return None


def classify(disclosure_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """원본 공시 list[dict] → 정규화된 list[dict].

    출력 row 키: rcept_dt, category, title, rcept_no, dart_url, amount?, counterparty?, fallback_text
    """
    out: list[dict[str, Any]] = []
    for r in disclosure_records:
        title = str(r.get("report_nm") or r.get("title") or "")
        rcept_no = str(r.get("rcept_no") or r.get("rcept_id") or "")
        rcept_dt = str(r.get("rcept_dt") or r.get("rcept_date") or "")
        body = str(r.get("body") or r.get("content") or title)

        category = _classify_one(title)
        amount = _extract_amount(body)
        counterparty = _extract_counterparty(body)

        # 룰 기반 fallback 한 줄 (Phase 2 LLM 으로 대체 가능)
        bits: list[str] = [category]
        if amount:
            bits.append(f"금액 {amount}")
        if counterparty:
            bits.append(f"상대방 {counterparty}")
        fallback_text = " · ".join(bits) if bits else "—"

        url = (
            f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
            if rcept_no
            else ""
        )
        out.append(
            {
                "rcept_dt": rcept_dt,
                "category": category,
                "title": title,
                "rcept_no": rcept_no,
                "dart_url": url,
                "amount": amount,
                "counterparty": counterparty,
                "fallback_text": fallback_text,
            }
        )
    return out


def category_counts(classified: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in classified:
        cat = r.get("category", "기타")
        counts[cat] = counts.get(cat, 0) + 1
    return counts
