import unittest
from bpi_match_link import match_hoopsapi_game


class MatchLinkTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {
            "id": 777,
            "home": {"name": "Philadelphia 76ers"},
            "away": {"name": "Miami Heat"},
            "start_time": "2026-11-25T22:10:00Z",
        }
        self.game = {
            "game_id": 1639746904,
            "home": "Philadelphia 76ers",
            "away": "Miami Heat",
            "start_time": "2026-11-25T22:12:00Z",
        }

    def test_exact_teams_and_close_start_time_match(self):
        result = match_hoopsapi_game(self.fixture, [self.game])
        self.assertEqual(result["status"], "MATCHED")
        self.assertEqual(result["fixture_id"], 777)
        self.assertEqual(result["hoopsapi_game_id"], 1639746904)

    def test_rejects_reversed_teams(self):
        reversed_game = dict(self.game, home="Miami Heat", away="Philadelphia 76ers")
        self.assertEqual(match_hoopsapi_game(self.fixture, [reversed_game])["status"], "NO_MATCH")

    def test_rejects_large_time_difference(self):
        late = dict(self.game, start_time="2026-11-26T03:00:00Z")
        self.assertEqual(match_hoopsapi_game(self.fixture, [late])["status"], "NO_MATCH")

    def test_rejects_missing_fixture_time(self):
        fixture = dict(self.fixture)
        fixture.pop("start_time")
        self.assertEqual(match_hoopsapi_game(fixture, [self.game])["status"], "NO_MATCH")

    def test_ambiguous_matches_are_rejected(self):
        second = dict(self.game, game_id=999)
        result = match_hoopsapi_game(self.fixture, [self.game, second])
        self.assertEqual(result["status"], "AMBIGUOUS")
        self.assertIsNone(result["game"])


if __name__ == "__main__":
    unittest.main()
