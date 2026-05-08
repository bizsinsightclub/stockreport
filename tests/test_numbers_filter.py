"""validators/numbers.py v2 — SVG/script/data-noverify 노이즈 필터 검증."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.validators import numbers as numbers_validator  # noqa: E402


_HTML = """<!DOCTYPE html>
<html lang="ko">
<body>
  <p>현재가 <td>1,234</td>원</p>

  <svg><path d="M123,45 L67.8 89 L9999.99 8138500"></path></svg>

  <script>var x=12345; var y=99999;</script>

  <div class="chart-card" data-noverify="true">
    <div class="plotly-graph-div">99999.123</div>
  </div>

  <div class="validation" data-noverify="true">
    환각 검증: HTML 내 숫자 195개 중 39개 일치
  </div>
</body>
</html>
"""


class NumbersValidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmp.name)
        self.html_path = self.tmpdir / "report.html"
        self.html_path.write_text(_HTML, encoding="utf-8")
        self.raw_dir = self.tmpdir / "raw"
        self.raw_dir.mkdir()
        # raw에 1234 가 들어있으면 visible 1,234 가 매칭되어야 함
        (self.raw_dir / "329180_price.json").write_text(
            json.dumps(
                {
                    "data": [{"종가": 1234, "거래량": 500}],
                    "source": "test",
                    "tool_args": {},
                    "fetched_at": "2026-01-01T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_filter_excludes_svg_script_noverify(self) -> None:
        result = numbers_validator.verify_html_against_raw(
            self.html_path, self.raw_dir, ticker="329180"
        )
        # 가시 1,234 만 카운트 — 195/39/156 같은 메타 노이즈는 data-noverify 로 제외
        self.assertEqual(result["checked"], 1, f"checked={result['checked']} unexpected (result={result})")
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["unmatched"], 0)

    def test_unmatched_when_no_raw(self) -> None:
        # raw 디렉토리 비우기
        for f in self.raw_dir.glob("*.json"):
            f.unlink()
        # 추가로 raw 와 매치 안되는 숫자도 보이게
        self.html_path.write_text(
            "<html><body><td>9999</td></body></html>", encoding="utf-8"
        )
        result = numbers_validator.verify_html_against_raw(
            self.html_path, self.raw_dir, ticker="329180"
        )
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["unmatched"], 1)
        self.assertEqual(result["css_class"], "fail")


if __name__ == "__main__":
    unittest.main()
