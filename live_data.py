"""Connecteur DataSportsAPI : recherche stricte d'un match de basketball en direct."""
import requests
import unicodedata

BASE_URL = "https://api.datasportsapi.com/v2"


class LiveDataError(Exception):
    pass


def _norm(value):
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return " ".join(value.casefold().replace(".", " ").replace("-", " ").split())


def _get(path, api_key, params=None):
    try:
        response = requests.get(
            BASE_URL + path,
            headers={"Authorization": f"Bearer {api_key}"},
            params=params,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise LiveDataError(f"Connexion API impossible : {exc}") from exc
    if response.status_code == 401:
        raise LiveDataError("Clé API refusée. Vérifie DATASPORTSAPI_API_KEY dans les Secrets Streamlit.")
    if response.status_code == 429:
        raise LiveDataError("Quota ou limite de requêtes API atteint. Réessaie plus tard.")
    if response.status_code >= 400:
        raise LiveDataError(f"API indisponible (HTTP {response.status_code}).")
    try:
        return response.json()
    except ValueError as exc:
        raise LiveDataError("Réponse API illisible.") from exc


def find_live_match(home_name, away_name, api_key):
    """Retourne uniquement une correspondance exacte domicile/extérieur non ambiguë."""
    payload = _get("/livescores", api_key, {"sport": "basketball"})
    games = payload.get("data") or []
    wanted_home, wanted_away = _norm(home_name), _norm(away_name)
    matches = [
        game for game in games
        if _norm((game.get("home") or {}).get("name")) == wanted_home
        and _norm((game.get("away") or {}).get("name")) == wanted_away
    ]
    if len(matches) != 1:
        reverse = [
            game for game in games
            if _norm((game.get("home") or {}).get("name")) == wanted_away
            and _norm((game.get("away") or {}).get("name")) == wanted_home
        ]
        if reverse:
            raise LiveDataError("Les équipes sont trouvées mais l'ordre domicile/extérieur ne correspond pas. Vérifie les noms.")
        if len(matches) > 1:
            raise LiveDataError("Plusieurs matchs correspondent exactement. Sélection manuelle nécessaire.")
        raise LiveDataError("Aucun match LIVE avec ces noms exacts. Vérifie l'orthographe, la compétition ou le statut du match.")
    return matches[0]


def get_match_statistics(fixture_id, api_key):
    payload = _get(f"/fixtures/{int(fixture_id)}/statistics", api_key)
    return (payload.get("data") or {}).get("periods") or []
