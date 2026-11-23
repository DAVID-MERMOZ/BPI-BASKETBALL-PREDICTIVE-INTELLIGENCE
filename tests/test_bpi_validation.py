import unittest

from bpi_validation import validate_halftime_data


class HalftimeValidationTests(unittest.TestCase):
    def setUp(self):
        self.home = {"fga": 20, "fgm": 10, "3pa": 8, "3pm": 4,
                     "tov": 3, "orb": 2, "ftm": 5, "fta": 6}
        self.away = {"fga": 18, "fgm": 9, "3pa": 6, "3pm": 3,
                     "tov": 4, "orb": 1, "ftm": 3, "fta": 4}

    def test_valid_inputs_have_no_errors_or_warnings(self):
        errors, warnings = validate_halftime_data(37, 24, self.home, self.away)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_impossible_shooting_counts_are_rejected(self):
        bad = dict(self.home, **{"3pm": 9})
        errors, _ = validate_halftime_data(47, 24, bad, self.away)
        self.assertTrue(any("3 points réussis supérieurs" in e for e in errors))

    def test_score_mismatch_is_warning_not_silent_correction(self):
        errors, warnings = validate_halftime_data(38, 24, self.home, self.away)
        self.assertEqual(errors, [])
        self.assertTrue(any("score reconstruit" in w for w in warnings))

    def test_missing_stat_is_rejected(self):
        bad = dict(self.home)
        del bad["tov"]
        errors, _ = validate_halftime_data(37, 24, bad, self.away)
        self.assertTrue(any("statistiques manquantes" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
