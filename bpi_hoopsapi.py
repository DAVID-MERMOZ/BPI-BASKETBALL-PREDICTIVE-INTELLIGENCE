"""Connecteur indépendant HoopsAPI pour les cotes basketball.

Le flux /games fournit des snapshots de cotes. Un snapshot n'est pas à lui
seul une preuve que le match est en direct : le statut du match doit être
confirmé par une source de fixtures (par exemple DataSportsAPI).
Les probabilités de marché restent séparées du modèle BPI.
"""
from datetime import datetime, timezone
import requests

BASE_URL = "https://hoopsapi.com/api/v1"


class HoopsAPIError(Exception):
    """Erreur explicite d'accès ou de structure HoopsAPI."""


def _parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def fetch_games(api_key, competition="NBA", timeout=20):
    """Récupère les matchs et snapshots de cotes d'une compétition."""
    if not api_key or not str(api_key).strip():
        raise HoopsAPIError("Clé HoopsAPI absente.")
    try:
        response = requests.get(
            f"{BASE_URL}/games",
            params={"competition": competition},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise HoopsAPIError(f"Connexion HoopsAPI impossible : {exc}") from exc
    if response.status_code == 401:
        raise HoopsAPIError("Clé HoopsAPI refusée (HTTP 401).")
    if response.status_code == 403:
        raise HoopsAPIError("Accès HoopsAPI refusé (HTTP 403).")
    if response.status_code == 429:
        raise HoopsAPIError("Quota HoopsAPI atteint (HTTP 429).")
    if response.status_code >= 400:
        raise HoopsAPIError(f"HoopsAPI indisponible (HTTP {response.status_code}).")
    try:
        payload = response.json()
    except ValueError as exc:
        raise HoopsAPIError("Réponse HoopsAPI JSON illisible.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("games"), list):
        raise HoopsAPIError("Réponse HoopsAPI inattendue : liste games absente.")
    return payload["games"]


def _price(value):
    try:
        number = float(value)
        return number if number > 1.0 else None
    except (TypeError, ValueError):
        return None


def _fair_pair(first, second):
    a, b = _price(first), _price(second)
    if a is None or b is None:
        return None
    ia, ib = 1.0 / a, 1.0 / b
    total = ia + ib
    return {
        "first_decimal": a,
        "second_decimal": b,
        "overround": total - 1.0,
        "first_fair_probability": ia / total,
        "second_fair_probability": ib / total,
    }


def normalize_game(game, now=None, max_age_seconds=900):
    """Normalise les marchés présents sans les déclarer LIVE sans preuve.

    Retourne les marchés de providers et periods. Les périodes disponibles
    dans l'échantillon sont ft, h1, h2, q1, q2, q3 et q4.
    """
    if not isinstance(game, dict):
        return None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    result = {
        "source": "HoopsAPI",
        "game_id": game.get("game_id"),
        "competition": game.get("competition"),
        "home": game.get("home"),
        "away": game.get("away"),
        "start_time": game.get("start_time"),
        "updated_at": game.get("updated_at"),
        "match_status": game.get("status"),
        "live_confirmed": False,
        "providers": [],
        "markets": [],
    }
    provider_data = game.get("providers")
    if isinstance(provider_data, dict):
        for provider, data in provider_data.items():
            if not isinstance(data, dict):
                continue
            captured = _parse_time(data.get("captured_at"))
            age = (now - captured).total_seconds() if captured else None
            fresh = age is not None and -60 <= age <= max_age_seconds
            for market_name, sides in (
                ("moneyline", ("home", "away")),
                ("handicap", ("home", "away")),
                ("over_under", ("over", "under")),
            ):
                market = data.get(market_name)
                if not isinstance(market, dict):
                    continue
                pair = _fair_pair(market.get(sides[0]), market.get(sides[1]))
                if pair is None:
                    continue
                result["markets"].append({
                    "provider": provider,
                    "period": "ft",
                    "market": market_name,
                    "line": market.get("line"),
                    "captured_at": data.get("captured_at"),
                    "age_seconds": age,
                    "fresh": fresh,
                    "live_confirmed": False,
                    **pair,
                })
            for market_name in ("team_total_home", "team_total_away"):
                market = data.get(market_name)
                if not isinstance(market, dict):
                    continue
                pair = _fair_pair(market.get("over"), market.get("under"))
                if pair is None:
                    continue
                result["markets"].append({
                    "provider": provider,
                    "period": "ft",
                    "market": market_name,
                    "line": market.get("line"),
                    "captured_at": data.get("captured_at"),
                    "age_seconds": age,
                    "fresh": fresh,
                    "live_confirmed": False,
                    **pair,
                })
            result["providers"].append({
                "name": provider,
                "captured_at": data.get("captured_at"),
                "fresh": fresh,
            })
    periods = game.get("periods")
    if isinstance(periods, dict):
        for period, providers in periods.items():
            if not isinstance(providers, dict):
                continue
            for provider, markets in providers.items():
                if not isinstance(markets, dict):
                    continue
                for market_name, sides in (
                    ("moneyline", ("home", "away")),
                    ("spread", ("home", "away")),
                    ("total", ("over", "under")),
                    ("team_total_home", ("over", "under")),
                    ("team_total_away", ("over", "under")),
                ):
                    market = markets.get(market_name)
                    if not isinstance(market, dict):
                        continue
                    pair = _fair_pair(market.get(sides[0]), market.get(sides[1]))
                    if pair is None:
                        continue
                    result["markets"].append({
                        "provider": provider,
                        "period": period,
                        "market": market_name,
                        "line": market.get("line"),
                        "captured_at": None,
                        "age_seconds": None,
                        "fresh": None,
                        "live_confirmed": False,
                        **pair,
                    })
    return result


def analyze_game_odds(game, now=None, max_age_seconds=900):
    """Retourne comparaison de marché seulement; aucun ajustement du modèle."""
    normalized = normalize_game(game, now=now, max_age_seconds=max_age_seconds)
    if normalized is None:
        return {
            "status": "NO_SIGNAL",
            "reason": "Match ou structure HoopsAPI invalide.",
            "game": None,
            "adjusted_probabilities": None,
        }
    fresh = [m for m in normalized["markets"] if m["fresh"] is True]
    normalized["fresh_provider_markets"] = fresh
    status = "MARKET_SNAPSHOT_AVAILABLE" if fresh else "NO_FRESH_MARKET"
    return {
        "status": status,
        "reason": None if fresh else "Aucun snapshot fournisseur horodaté et suffisamment récent.",
        "game": normalized,
        "adjusted_probabilities": None,
        "note": "Snapshot de cotes, pas une confirmation LIVE. Statut du match à confirmer indépendamment.",
    }
