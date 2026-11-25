import os
import tempfile
import unittest

from bpi_odds_history import OddsHistory


class OddsHistoryTests(unittest.TestCase):
    def test_snapshots_are_persisted_and_movement_is_computed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "odds.sqlite3")
            history = OddsHistory(path)
            first = {"captured_at": "2026-11-25T10:00:00+00:00", "markets": [{
                "key": "moneyline", "period": "full", "line": None,
                "outcomes": [{"name": "Home", "decimal": 1.8}, {"name": "Away", "decimal": 2.0}],
            }]}
            second = {"captured_at": "2026-11-25T10:05:00+00:00", "markets": [{
                "key": "moneyline", "period": "full", "line": None,
                "outcomes": [{"name": "Home", "decimal": 1.7}, {"name": "Away", "decimal": 2.1}],
            }]}
            self.assertEqual(history.record(42, first), 1)
            self.assertEqual(history.record(42, second), 1)
            result = history.movement(42, "moneyline", "full")
            self.assertEqual(result["status"], "OBSERVED_MOVEMENT")
            self.assertAlmostEqual(result["changes"][0]["delta"], -0.1)

    def test_one_snapshot_is_not_called_a_movement(self):
        with tempfile.TemporaryDirectory() as folder:
            history = OddsHistory(os.path.join(folder, "odds.sqlite3"))
            history.record(7, {"captured_at": "2026-11-25T10:00:00Z", "markets": [{
                "key": "total", "outcomes": [{"name": "Over", "decimal": 1.9},
                                             {"name": "Under", "decimal": 1.9}],
            }]})
            self.assertEqual(history.movement(7, "total")["status"], "INSUFFICIENT_HISTORY")


if __name__ == "__main__":
    unittest.main()
