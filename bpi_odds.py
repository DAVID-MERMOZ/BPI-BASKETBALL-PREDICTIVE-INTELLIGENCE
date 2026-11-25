"""BPI Market Intelligence: lecture prudente des cotes DataSportsAPI.

Ce module compare le marché au modèle; il ne modifie jamais les probabilités du
modèle et ne produit aucun conseil de mise.
"""
from datetime import datetime, timezone
import requests

BASE_URL = "https://api.datasportsapi.com/v2"


class OddsError(Exception):
    """Erreur explicite de collecte ou de structure des cotes."""


def _request(path, api_key, timeout=15):
    try:
        response = requests.get(
            BASE_URL + path,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise OddsError(f"Connexion cotes impossible : {exc}") from exc
    if response.status_code == 401:
        raise OddsError("Clé DataSportsAPI refusée (HTTP 401).")
    if response.status_code == 403:
        raise OddsError("Accès aux cotes refusé (HTTP 403) : endpoint probablement non inclus au plan API.")
    if response.status_code == 429:
        raise OddsError("Limite de requêtes atteinte (HTTP 429).")
    if response.status_code >= 400:
        raise OddsError(f"Endpoint cotes indisponible (HTTP {response.status_code}).")
    try:
        payload = response.json()
    except ValueError as exc:
        raise OddsError("Réponse cotes JSON illisible.") from exc
    if not isinstance(payload, dict):
        raise OddsError("Structure cotes inattendue.")
    return payload


def get_fixture_odds(fixture_id, api_key):
    """Récupère les marchés d'un fixture précis; ne recherche pas par noms."""
    try:
        fixture_id = int(fixture_id)
    except (TypeError, ValueError) as exc:
        raise OddsError("fixture_id doit être un identifiant numérique.") from exc
    if fixture_id <= 0:
        raise OddsError("fixture_id invalide.")
    payload = _request(f"/fixtures/{fixture_id}/odds", api_key)
    data = payload.get("data")
    if isinstance(data, dict):
        markets = data.get("markets") or data.get("odds") or []
    elif isinstance(data, list):
        markets = data
    else:
        markets = []
    if not isinstance(markets, list):
        raise OddsError("Liste des marchés absente ou invalide.")
    return markets


def _decimal(choice, *keys):
    for key in keys:
        value = choice.get(key)
        if value is not None:
            try:
                number = float(value)
                if number > 1.0:
                    return number
            except (TypeError, ValueError):
                pass
    return None


def _choices(market):
    return market.get("choices") or market.get("outcomes") or market.get("selections") or []


def normalize_market(market):
    """Normalise un marché deux issues et calcule les probabilités sans marge."""
    if not isinstance(market, dict):
        return None
    live = market.get("live") is True
    suspended = market.get("suspended") is True
    choices = _choices(market)
    if not live or suspended or not isinstance(choices, list) or len(choices) != 2:
        return None
    parsed = []
    for choice in choices:
        if not isinstance(choice, dict):
            return None
        price = _decimal(choice, "decimal", "odds", "price", "current")
        if price is None:
            return None
        parsed.append({
            "name": str(choice.get("name") or choice.get("label") or choice.get("key") or "unknown"),
            "decimal": price,
            "opening_decimal": _decimal(choice, "openingDecimal", "opening", "openingOdds", "open"),
        })
    implied = [1.0 / item["decimal"] for item in parsed]
    total = sum(implied)
    if total <= 0:
        return None
    return {
        "key": market.get("key") or market.get("kind") or market.get("name") or "unknown",
        "period": market.get("period"),
        "line": market.get("line"),
        "live": True,
        "suspended": False,
        "updated_at": market.get("updatedAt") or market.get("updated_at"),
        "overround": total - 1.0,
        "outcomes": [
            {**item, "implied_probability": implied[i], "fair_probability": implied[i] / total}
            for i, item in enumerate(parsed)
        ],
    }


def analyze_live_odds(markets, model_probabilities=None, now=None):
    """Retourne snapshots utilisables et comparaison; abstention par défaut."""
    timestamp = now or datetime.now(timezone.utc).isoformat()
    usable = [item for item in (normalize_market(m) for m in markets or []) if item]
    comparisons = []
    if model_probabilities:
        for market in usable:
            for outcome in market["outcomes"]:
                model_p = model_probabilities.get(outcome["name"])
                if isinstance(model_p, (int, float)) and 0 <= model_p <= 1:
                    comparisons.append({
                        "market": market["key"],
                        "outcome": outcome["name"],
                        "model_raw": float(model_p),
                        "market_fair": outcome["fair_probability"],
                        "difference": float(model_p) - outcome["fair_probability"],
                    })
    return {
        "captured_at": timestamp,
        "status": "COMPARISON_ONLY" if usable else "NO_SIGNAL",
        "reason": None if usable else "Aucun marché live exploitable (absent, suspendu ou incomplet).",
        "markets": usable,
        "comparisons": comparisons,
        "adjusted_probabilities": None,
        "note": "Aucun ajustement du modèle : pondération marché non validée historiquement.",
    }
