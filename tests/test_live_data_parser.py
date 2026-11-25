import unittest

from bpi_live_data import LiveDataError, extract_first_half_inputs


def item(key, home_value, home_total=None, away_value=None, away_total=None):
    return {
        "key": key,
        "home": {"value": home_value, "total": home_total},
        "away": {"value": away_value if away_value is not None else home_value,
                 "total": away_total if away_total is not None else home_total},
    }


def period(name, offset=0):
    # Structure conforme à l'enveloppe documentée : periods -> groups -> items.
    return {
        "period": name,
        "groups": [{
            "key": "scoring",
            "name": "Scoring",
            "items": [
                item("fieldGoalsMade", 10 + offset, 20 + offset, 9 + offset, 18 + offset),
                item("threePointersMade", 4 + offset, 8 + offset, 3 + offset, 6 + offset),
                item("freeThrowsMade", 5 + offset, 6 + offset, 3 + offset, 4 + offset),
                item("turnovers", 3 + offset, None, 4 + offset, None),
                item("offensiveRebounds", 2 + offset, None, 1 + offset, None),
            ],
        }],
    }


class LiveBasketballParserTests(unittest.TestCase):
    def test_period1_and_period2_are_added_and_ratio_totals_are_attempts(self):
        result = extract_first_half_inputs([period("period1"), period("period2", 1)])
        self.assertEqual(result["home"], {
            "fga": 41, "fgm": 21, "3pa": 17, "3pm": 9,
            "tov": 7, "orb": 5, "ftm": 11, "fta": 13,
        })
        self.assertEqual(result["away"], {
            "fga": 37, "fgm": 19, "3pa": 13, "3pm": 7,
            "tov": 9, "orb": 3, "ftm": 7, "fta": 9,
        })

    def test_aggregate_all_is_rejected_without_confirmed_halftime(self):
        with self.assertRaises(LiveDataError):
            extract_first_half_inputs([period("all")])

    def test_aggregate_all_is_allowed_when_halftime_is_confirmed(self):
        result = extract_first_half_inputs([period("all")], allow_all_period=True)
        self.assertEqual(result["home"]["fga"], 20)
        self.assertEqual(result["home"]["fgm"], 10)

    def test_missing_essential_basketball_stat_is_rejected(self):
        p = period("period1")
        p["groups"][0]["items"] = [
            x for x in p["groups"][0]["items"] if x["key"] != "fieldGoalsMade"
        ]
        with self.assertRaises(LiveDataError):
            extract_first_half_inputs([p, period("period2")])


if __name__ == "__main__":
    unittest.main()
