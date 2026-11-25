import unittest

from bpi_odds import analyze_live_odds, normalize_market


class OddsNormalizationTests(unittest.TestCase):
    def test_two_way_market_removes_overround(self):
        market = normalize_market({
            "key": "moneyline", "live": True, "suspended": False,
            "choices": [
                {"name": "Home", "decimal": 1.8},
                {"name": "Away", "decimal": 2.0},
            ],
        })
        self.assertIsNotNone(market)
        self.assertAlmostEqual(sum(x["fair_probability"] for x in market["outcomes"]), 1.0)
        self.assertGreater(market["overround"], 0)

    def test_suspended_or_prematch_market_is_ignored(self):
        base = {"choices": [{"name": "Over", "decimal": 1.9}, {"name": "Under", "decimal": 1.9}]}
        self.assertIsNone(normalize_market({**base, "live": False}))
        self.assertIsNone(normalize_market({**base, "live": True, "suspended": True}))

    def test_missing_side_is_ignored_and_no_signal(self):
        result = analyze_live_odds([{
            "live": True, "suspended": False,
            "choices": [{"name": "Home", "decimal": 1.7}],
        }])
        self.assertEqual(result["status"], "NO_SIGNAL")
        self.assertIsNone(result["adjusted_probabilities"])

    def test_market_comparison_does_not_overwrite_model(self):
        result = analyze_live_odds([{
            "key": "moneyline", "live": True, "suspended": False,
            "choices": [{"name": "Home", "decimal": 2.0}, {"name": "Away", "decimal": 2.0}],
        }], {"Home": 0.6})
        self.assertEqual(result["status"], "COMPARISON_ONLY")
        self.assertEqual(result["comparisons"][0]["model_raw"], 0.6)
        self.assertIsNone(result["adjusted_probabilities"])


if __name__ == "__main__":
    unittest.main()
