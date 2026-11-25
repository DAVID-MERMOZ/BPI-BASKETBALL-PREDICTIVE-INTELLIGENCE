import unittest
from datetime import datetime, timezone
from bpi_market_pipeline import compare_fixture_market, compare_live_fixtures


class MarketPipelineTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 25, 7, 31, tzinfo=timezone.utc)
        self.fixture = {
            "id": 777,
            "home": {"name": "Philadelphia 76ers"},
            "away": {"name": "Miami Heat"},
            "start_time": "2026-11-25T22:10:00Z",
        }
        self.game = {
            "game_id": 1639746904, "competition": "NBA",
            "home": "Philadelphia 76ers", "away": "Miami Heat",
            "start_time": "2026-11-25T22:12:00Z",
            "providers": {"pinnacle": {
                "captured_at": "2026-11-25T07:30:05Z",
                "moneyline": {"home": 1.9, "away": 1.9},
            }},
            "periods": {},
        }

    def test_matched_fresh_market_is_comparison_only(self):
        result = compare_fixture_market(self.fixture, [self.game], now=self.now)
        self.assertEqual(result["status"], "MARKET_SNAPSHOT_AVAILABLE")
        self.assertEqual(result["fixture_id"], 777)
        self.assertEqual(result["hoopsapi_game_id"], 1639746904)
        self.assertEqual(len(result["fresh_markets"]), 1)
        self.assertIsNone(result["model_adjustment"])
        self.assertFalse(result["live_confirmed"])

    def test_unmatched_fixture_returns_no_market(self):
        result = compare_fixture_market(self.fixture, [], now=self.now)
        self.assertEqual(result["status"], "NO_MATCH")
        self.assertIsNone(result["market"])

    def test_stale_market_is_not_available(self):
        stale = dict(self.game)
        stale["providers"] = {"pinnacle": {
            "captured_at": "2026-11-25T06:00:00Z",
            "moneyline": {"home": 1.9, "away": 1.9},
        }}
        result = compare_fixture_market(self.fixture, [stale], now=self.now)
        self.assertEqual(result["status"], "NO_FRESH_MARKET")
        self.assertEqual(result["fresh_markets"], [])

    def test_batch_reuses_supplied_odds_list(self):
        results = compare_live_fixtures([self.fixture, self.fixture], [self.game], now=self.now)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["status"] == "MARKET_SNAPSHOT_AVAILABLE" for r in results))


if __name__ == "__main__":
    unittest.main()
