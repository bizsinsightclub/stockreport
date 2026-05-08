"""더미 fixtures 로 dashboard 골격을 렌더하는 smoke test.

실 데이터·MCP 없이 동작. 실행::

    python test_render.py

성공 시 ``data/output/329180/{today}.html`` 가 생성되고 console 에 검증 결과
요약이 출력된다.
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.analyzers import disclosure as disclosure_analyzer  # noqa: E402
from src.analyzers import financials as financials_analyzer  # noqa: E402
from src.analyzers import flow as flow_analyzer  # noqa: E402
from src.analyzers import macro as macro_analyzer  # noqa: E402
from src.analyzers import peer as peer_analyzer  # noqa: E402
from src.analyzers import price as price_analyzer  # noqa: E402
from src.config import (  # noqa: E402
    DISCLAIMER_EN,
    DISCLAIMER_KO,
    OUTPUT_DIR,
    RAW_DIR,
)
from src.renderer import charts as chart_builder  # noqa: E402
from src.renderer import html as html_renderer  # noqa: E402
from src.validators import numbers as numbers_validator  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("test_render")


FIXTURES = ROOT / "tests" / "fixtures"
TICKER = "329180"
NAME = "HD현대중공업"
PEERS = {"010140": "삼성중공업", "042660": "한화오션"}


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def main() -> int:
    today = date.today()
    raw_dir = RAW_DIR / today.isoformat()
    raw_dir.mkdir(parents=True, exist_ok=True)

    # raw 복제 (validation이 raw_dir에서 읽으므로)
    for f in FIXTURES.glob("*.json"):
        shutil.copy(f, raw_dir / f.name)

    price_meta = _load("329180_price.json")
    flow_meta = _load("329180_flow.json")
    disc_meta = _load("329180_disclosures.json")
    fin_meta = _load("329180_financials.json")
    macro_meta = _load("_macro_USDKRW.json")
    peer_metas = {pt: _load(f"{pt}_price.json") for pt in PEERS}

    enriched_price = price_analyzer.enrich(price_meta["data"])
    signals = price_analyzer.latest_signals(enriched_price)
    header = price_analyzer.header_summary(enriched_price)

    enriched_flow = flow_analyzer.enrich(flow_meta["data"])
    classified = disclosure_analyzer.classify(disc_meta["data"])
    fin_df = financials_analyzer.normalize(fin_meta["data"])

    peer_records = {pt: m["data"] for pt, m in peer_metas.items()}
    normalized_peer = peer_analyzer.normalized_frame(
        TICKER, price_meta["data"], peer_records, lookback_days=180
    )

    peer_rows = [
        peer_analyzer.valuation_row(TICKER, NAME, price_meta["data"]),
    ]
    for pt, recs in peer_records.items():
        peer_rows.append(peer_analyzer.valuation_row(pt, PEERS[pt], recs))

    macro_df = macro_analyzer.normalize_usdkrw(macro_meta["data"])
    macro_value, macro_delta = macro_analyzer.latest_value(macro_df)
    macro_dir = "up" if (macro_delta or 0) > 0 else ("down" if (macro_delta or 0) < 0 else "flat")
    macro_cards = [
        {"name": "USD/KRW", "value": macro_value, "delta": macro_delta, "direction": macro_dir}
    ]

    slots = {
        "brief": price_analyzer.fallback_brief(enriched_price, TICKER),
        "s1_price": price_analyzer.fallback_s1_price(enriched_price),
        "s2_tech": price_analyzer.fallback_s2_tech(signals),
        "s4_peer": peer_analyzer.fallback_s4_peer(TICKER, normalized_peer),
        "s4_macro": macro_analyzer.fallback_s4_macro("USD/KRW", macro_df),
    }

    ctx = {
        "ticker": TICKER,
        "name": NAME,
        "market": "KOSPI",
        "sector_name": "조선",
        "as_of": header.get("as_of") or today.isoformat(),
        "as_of_compact": (header.get("as_of") or today.isoformat()).replace("-", ""),
        "header": header,
        "signals": signals,
        "slots": slots,
        "disclosures": classified,
        "peer_rows": peer_rows,
        "peer_note": "",
        "macro_cards": macro_cards,
        "macro_skipped": [],
        "chart_price": chart_builder.price_chart(enriched_price),
        "chart_flow": chart_builder.flow_chart(enriched_flow),
        "chart_peer": chart_builder.peer_normalized_chart(normalized_peer, TICKER),
        "chart_financials": chart_builder.financials_bars(fin_df),
        "chart_macro": chart_builder.macro_chart("USD/KRW", macro_df),
        "sources_text": "pykrx · DART · KRX",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "disclaimer_ko": DISCLAIMER_KO,
        "disclaimer_en": DISCLAIMER_EN,
        "validation": None,
    }

    out_dir = OUTPUT_DIR / TICKER
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{today.isoformat()}.html"

    html1 = html_renderer.render_skeleton(ctx)
    out_path.write_text(html1, encoding="utf-8")

    val = numbers_validator.verify_html_against_raw(out_path, raw_dir, ticker=TICKER)
    numbers_validator.write_sidecar(val, out_path)
    ctx["validation"] = val
    out_path.write_text(html_renderer.render_skeleton(ctx), encoding="utf-8")

    html_renderer.update_ticker_index(TICKER)
    html_renderer.update_root_index()

    log.info(
        "renderered=%s checked=%d matched=%d unmatched=%d (%s)",
        out_path,
        val["checked"],
        val["matched"],
        val["unmatched"],
        val["css_class"],
    )

    # 골격 검증 (assertions)
    body = out_path.read_text(encoding="utf-8")
    assert 'data-llm-slot="brief"' in body
    assert 'data-llm-slot="s1_price"' in body
    assert 'data-llm-slot="s2_tech"' in body
    assert 'data-llm-slot="s3_disc_0"' in body
    assert 'data-llm-slot="s4_peer"' in body
    assert 'data-llm-slot="s4_macro"' in body
    assert "01 / FIVE" in body and "07 / FIVE" in body  # 7 sections
    assert 'class="signals"' in body
    assert 'class="validation' in body
    assert "<footer>" in body
    assert 'lang="ko"' in body
    assert "HD현대중공업" in body or NAME in body

    log.info("smoke OK — %s", out_path)
    print(f"[OK] {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
