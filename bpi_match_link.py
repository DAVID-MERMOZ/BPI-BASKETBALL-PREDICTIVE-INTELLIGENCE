"""Correspondance prudente entre fixtures DataSportsAPI et matchs HoopsAPI.

Les identifiants des deux fournisseurs ne sont jamais supposés identiques.
La liaison exige les deux équipes dans le même ordre et une heure de début
proche. Les cas ambigus ou incomplets sont rejetés (NO_MATCH/AMBIGUOUS).
"""
from datetime import datetime, timezone
import unicodedata


def _norm(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(value.casefold().replace(".", " ").replace("-", " ").split())


def _time(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _fixture_team(fixture, side):
    value = fixture.get(side)
    if isinstance(value, dict):
        return value.get("name") or value.get("shortName")
    return value


def match_hoopsapi_game(fixture, odds_games, max_start_delta_minutes=180):
    """Associe un fixture live à un match odds, ou refuse la liaison.

    Le fixture doit contenir home/away et une heure dans start_time,
    startTime ou date. Le match HoopsAPI doit contenir home/away/start_time.
    Aucun rapprochement inversé ni alias approximatif n'est autorisé.
    """
    if not isinstance(fixture, dict) or not isinstance(odds_games, list):
        return {"status": "NO_MATCH", "reason": "Entrées invalides.", "game": None}
    home = _norm(_fixture_team(fixture, "home"))
    away = _norm(_fixture_team(fixture, "away"))
    ftime = _time(fixture.get("start_time") or fixture.get("startTime") or fixture.get("date"))
    if not home or not away or ftime is None:
        return {"status": "NO_MATCH", "reason": "Équipes ou heure du fixture absentes.", "game": None}

    candidates = []
    for game in odds_games:
        if not isinstance(game, dict):
            continue
        if _norm(game.get("home")) != home or _norm(game.get("away")) != away:
            continue
        gtime = _time(game.get("start_time"))
        if gtime is None:
            continue
        delta = abs((gtime - ftime).total_seconds()) / 60
        if delta <= max_start_delta_minutes:
            candidates.append((delta, game))

    if not candidates:
        return {"status": "NO_MATCH", "reason": "Aucune correspondance exacte équipes + horaire.", "game": None}
    candidates.sort(key=lambda item: item[0])
    if len(candidates) > 1 and abs(candidates[1][0] - candidates[0][0]) < 1:
        return {"status": "AMBIGUOUS", "reason": "Plusieurs matchs correspondent avec un écart horaire quasi identique.", "game": None}
    delta, game = candidates[0]
    return {
        "status": "MATCHED",
        "reason": None,
        "game": game,
        "time_delta_minutes": round(delta, 2),
        "fixture_id": fixture.get("id") or fixture.get("fixtureId") or fixture.get("fixture_id"),
        "hoopsapi_game_id": game.get("game_id"),
    }
