import unittest

from engine import simulate_second_half


class SecondHalfSimulationTests(unittest.TestCase):
    def setUp(self):
        self.home = {
            "fga": 40, "fgm": 18, "3pa": 15, "3pm": 5,
            "fta": 8, "ftm": 6, "tov": 7, "orb": 4,
        }
        self.away = {
            "fga": 38, "fgm": 16, "3pa": 14, "3pm": 4,
            "fta": 10, "ftm": 8, "tov": 9, "orb": 5,
        }

    def test_simulation_returns_probabilities_and_score_estimates(self):
        result = simulate_second_half(
            45, 42, self.home, self.away, n=10000, seed=42
        )
        self.assertAlmostEqual(
            result["home_win"] + result["away_win"] + result["tie"],
            100.0,
            places=8,
        )
        self.assertGreater(result["home_mean"], 45)
        self.assertGreater(result["away_mean"], 42)
        self.assertLessEqual(result["total_p10"], result["total_median"])
        self.assertLessEqual(result["total_median"], result["total_p90"])

    def test_same_seed_reproduces_same_result(self):
        first = simulate_second_half(
            45, 42, self.home, self.away, n=10000, seed=42
        )
        second = simulate_second_half(
            45, 42, self.home, self.away, n=10000, seed=42
        )
        self.assertEqual(first, second)

    def test_too_few_simulations_are_rejected(self):
        with self.assertRaises(ValueError):
            simulate_second_half(
                45, 42, self.home, self.away, n=999, seed=42
            )


if __name__ == "__main__":
    unittest.main()
