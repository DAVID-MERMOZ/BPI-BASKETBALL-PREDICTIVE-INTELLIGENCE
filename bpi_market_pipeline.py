"""Pipeline de comparaison fixtures DataSportsAPI / cotes HoopsAPI.

HoopsAPI est interrogée une fois par compétition, puis les snapshots sont
rattachés aux fixtures LIVE par équipes + horaire. Les cotes ne modifient
jamais les probabilités du moteur BPI.
"""
from bpi_hoopsapi import analyze_game_odds
from bpi_match_link import match_hoopsapi_game


def compare_fixture_market(fixture, hoops_games, now=None, max_start_delta_minutes=180,
                           max_age_seconds=900):
    """Compare un fixture à un snapshot HoopsAPI, avec refus en cas de doute."""
    linked = match_hoopsapi_game(
        fixture, hoops_games, max_start_delta_minutes=max_start_delta_minutes
    )
    if linked["status"] != "MATCHED":
        return {
            "status": linked["status"],
            "reason": linked["reason"],
            "fixture_id": fixture.get("id") if isinstance(fixture, dict) else None,
            "market": None,
            "model_adjustment": None,
        }

    analysis = analyze_game_odds(
        linked["game"], now=now, max_age_seconds=max_age_seconds
    )
    return {
        "status": analysis["status"],
        "reason": analysis["reason"],
        "fixture_id": linked["fixture_id"],
        "hoopsapi_game_id": linked["hoopsapi_game_id"],
        "time_delta_minutes": linked["time_delta_minutes"],
        "match": {
            "home": linked["game"].get("home"),
            "away": linked["game"].get("away"),
            "competition": linked["game"].get("competition"),
            "start_time": linked["game"].get("start_time"),
        },
        "market": analysis["game"],
        "fresh_markets": (
            analysis["game"].get("fresh_provider_markets", [])
            if analysis["game"] else []
        ),
        "model_adjustment": None,
        "live_confirmed": False,
        "note": (
            "Comparaison de snapshots uniquement. Le statut LIVE provient "
            "du flux fixtures DataSportsAPI; les cotes HoopsAPI ne le prouvent pas."
        ),
    }


def compare_live_fixtures(fixtures, hoops_games, now=None,
                          max_start_delta_minutes=180, max_age_seconds=900):
    """Traite un lot de fixtures à partir d'un seul lot HoopsAPI déjà téléchargé."""
    results = []
    for fixture in fixtures or []:
        result = compare_fixture_market(
            fixture, hoops_games, now=now,
            max_start_delta_minutes=max_start_delta_minutes,
            max_age_seconds=max_age_seconds,
        )
        results.append(result)
    return results
