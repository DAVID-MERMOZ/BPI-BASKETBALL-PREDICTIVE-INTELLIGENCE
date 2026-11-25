import unittest
from datetime import datetime, timezone

from bpi_hoopsapi import analyze_game_odds, normalize_game, fetch_competitions, HoopsAPIError


SAMPLE = {
    "game_id": 1639746904,
    "competition": "NBA",
    "home": "Philadelphia 76ers",
    "away": "Miami Heat",
    "start_time": "2026-11-25T22:10:00Z",
    "updated_at": "2026-11-25T07:04:05Z",
    "providers": {
        "pinnacle": {
            "moneyline": {"home": 1.892, "away": 1.99},
            "handicap": {"line": -1, "home": 1.925, "away": 1.961},
            "over_under": {"line": 237.5, "over": 1.909, "under": 1.943},
            "captured_at": "2026-11-25T07:30:05Z",
        }
    },
    "periods": {
        "ft": {
            "pinnacle": {
                "moneyline": {"home": 1.892, "away": 1.99},
                "spread": {"line": -1, "home": 1.925, "away": 1.961},
                "total": {"line": 237.5, "over": 1.909, "under": 1.943},
            }
        },
        "h1": {
            "pinnacle": {
                "moneyline": {"home": 1.8, "away": 2.05},
                "total": {"line": 118.5, "over": 1.9, "under": 1.9},
            }
        },
    },
}


class HoopsAPITests(unittest.TestCase):
    def test_normalizes_multiple_providers_and_periods(self):
        result = normalize_game(
            SAMPLE, now=datetime(2026, 11, 25, 7, 31, tzinfo=timezone.utc)
        )
        self.assertEqual(result["game_id"], 1639746904)
        self.assertFalse(result["live_confirmed"])
        self.assertIn("h1", {m["period"] for m in result["markets"]})
        self.assertIn("ft", {m["period"] for m in result["markets"]})
        self.assertGreaterEqual(len(result["markets"]), 5)

    def test_fair_probabilities_sum_to_one(self):
        result = normalize_game(
            SAMPLE, now=datetime(2026, 11, 25, 7, 31, tzinfo=timezone.utc)
        )
        market = next(m for m in result["markets"]
                      if m["provider"] == "pinnacle"
                      and m["period"] == "ft"
                      and m["market"] == "moneyline")
        self.assertAlmostEqual(
            market["first_fair_probability"] + market["second_fair_probability"],
            1.0,
        )
        self.assertGreater(market["overround"], 0)

    def test_stale_snapshot_is_not_usable(self):
        result = analyze_game_odds(
            SAMPLE, now=datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(result["status"], "NO_FRESH_MARKET")
        self.assertIsNone(result["adjusted_probabilities"])

    def test_fresh_snapshot_is_not_claimed_live(self):
        result = analyze_game_odds(
            SAMPLE, now=datetime(2026, 11, 25, 7, 31, tzinfo=timezone.utc)
        )
        self.assertEqual(result["status"], "MARKET_SNAPSHOT_AVAILABLE")
        self.assertFalse(result["game"]["live_confirmed"])
        self.assertIsNone(result["adjusted_probabilities"])


    def test_fetch_competitions_parses_catalog(self):
        from unittest.mock import patch
        class Response:
            status_code = 200
            def json(self):
                return {"count": 2, "competitions": [
                    {"pinnacle_id": 487, "name": "NBA", "container": "USA", "event_count": 10},
                    {"pinnacle_id": 493, "name": "NCAA", "container": "USA", "event_count": 66},
                ]}
        with patch("bpi_hoopsapi.requests.get", return_value=Response()):
            result = fetch_competitions("test-key")
        self.assertEqual([x["name"] for x in result], ["NBA", "NCAA"])
        self.assertEqual(result[1]["pinnacle_id"], 493)

    def test_fetch_competitions_rejects_unexpected_schema(self):
        from unittest.mock import patch
        class Response:
            status_code = 200
            def json(self):
                return {"items": []}
        with patch("bpi_hoopsapi.requests.get", return_value=Response()):
            with self.assertRaises(HoopsAPIError):
                fetch_competitions("test-key")

    def test_invalid_prices_are_ignored(self):
        bad = {"game_id": 1, "providers": {"book": {
            "moneyline": {"home": 1.8, "away": None},
            "captured_at": "2026-11-25T07:30:05Z",
        }}}
        result = normalize_game(
            bad, now=datetime(2026, 11, 25, 7, 31, tzinfo=timezone.utc)
        )
        self.assertEqual(result["markets"], [])


if __name__ == "__main__":
    unittest.main()
