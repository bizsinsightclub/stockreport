"""peers.auto_select 결정성 / exclude / degrade fallback 테스트.

pykrx 의존을 mock 으로 주입한다.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.meta.peers import auto_select, validate_override  # noqa: E402


def _cap_provider(_today):
    df = pd.DataFrame(
        {
            "시가총액": [
                3_000_000_000_000,  # target
                2_500_000_000_000,  # peer1
                2_000_000_000_000,  # peer2
                1_800_000_000_000,  # peer3
                1_500_000_000_000,  # peer4
                1_200_000_000_000,  # peer5
                1_000_000_000_000,  # peer6
            ],
        },
        index=["329180", "010140", "042660", "009540", "005380", "005930", "000660"],
    )
    return df


def _sector_provider_match():
    df = pd.DataFrame(
        {
            "업종코드": ["35100", "35100", "35100", "35100", "27000", "33000", "33000"],
            "업종명": ["조선", "조선", "조선", "조선", "자동차", "반도체", "반도체"],
        },
        index=["329180", "010140", "042660", "009540", "005380", "005930", "000660"],
    )
    return df


def _sector_provider_empty():
    return pd.DataFrame(columns=["업종코드", "업종명"])


class PeersTest(unittest.TestCase):
    def test_top_n_deterministic(self) -> None:
        sel = auto_select(
            "329180",
            sector_code="35100",
            n=3,
            today_yyyymmdd="20260509",
            market_cap_provider=_cap_provider,
            sector_provider=_sector_provider_match,
        )
        self.assertEqual(sel.peers, ["010140", "042660", "009540"])
        self.assertFalse(sel.degraded)

    def test_excludes_target(self) -> None:
        sel = auto_select(
            "329180",
            sector_code="35100",
            n=10,
            today_yyyymmdd="20260509",
            market_cap_provider=_cap_provider,
            sector_provider=_sector_provider_match,
        )
        self.assertNotIn("329180", sel.peers)

    def test_degrade_when_sector_unavailable(self) -> None:
        sel = auto_select(
            "329180",
            sector_code="",
            n=3,
            today_yyyymmdd="20260509",
            market_cap_provider=_cap_provider,
            sector_provider=_sector_provider_empty,
        )
        self.assertTrue(sel.degraded)
        self.assertNotIn("329180", sel.peers)
        # 시총 desc 상위 3 (target 제외)
        self.assertEqual(sel.peers, ["010140", "042660", "009540"])

    def test_validate_override_dedup_and_self_exclude(self) -> None:
        out = validate_override(["010140", "010140", "329180", "042660"], "329180")
        self.assertEqual(out, ["010140", "042660"])


if __name__ == "__main__":
    unittest.main()
