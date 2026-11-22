""""Connecteur DataSportsAPI et normalisation des statistiques basket LIVE."""
import unicodedata
import requests

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
        try:
            detail = (response.json().get("error") or {}).get("message")
        except Exception:
            detail = None
        raise LiveDataError(f"API indisponible (HTTP {response.status_code})" + (f" : {detail}" if detail else "."))
    try:
        return response.json()
    except ValueError as exc:
        raise LiveDataError("Réponse API illisible.") from exc


def find_live_match(home_name, away_name, api_key):
    """Recherche une seule correspondance exacte dans le flux basket en direct."""
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
            raise LiveDataError("Les équipes sont trouvées mais l'ordre domicile/extérieur est inversé.")
        if len(matches) > 1:
            raise LiveDataError("Plusieurs matchs correspondent. Précise la compétition ou sélectionne le match.")
        raise LiveDataError("Aucun match LIVE correspondant. Vérifie les noms et que le match est actuellement en cours.")
    return matches[0]


def get_match_statistics(fixture_id, api_key):
    payload = _get(f"/fixtures/{int(fixture_id)}/statistics", api_key)
    data = payload.get("data") or {}
    return data.get("periods") or []


def _period_values(period):
    values = {}
    for group in period.get("groups") or []:
        for item in group.get("items") or []:
            key = item.get("key")
            if key:
                values[key] = item
    return values


def extract_first_half_inputs(periods):
    """Convertit les statistiques des deux premiers quart-temps vers le schéma du moteur."""
    by_period = {p.get("period"): p for p in periods or []}
    first_two = [by_period.get("period1"), by_period.get("period2")]
    if not all(first_two):
        raise LiveDataError("Les statistiques des deux premiers quart-temps ne sont pas encore disponibles. Aucun champ n'a été rempli.")
    aliases = {
        "fga": "fieldGoalsAttempted",
        "fgm": "fieldGoalsMade",
        "3pa": "threePointersAttempted",
        "3pm": "threePointersMade",
        "tov": "turnovers",
        "orb": "offensiveRebounds",
        "ftm": "freeThrowsMade",
        "fta": "freeThrowsAttempted",
    }
    result = {"home": {}, "away": {}}
    for target, source in aliases.items():
        totals = {"home": 0, "away": 0}
        found = {"home": False, "away": False}
        for period in first_two:
            item = _period_values(period).get(source)
            if not item:
                continue
            for side in ("home", "away"):
                side_data = item.get(side) or {}
                value = side_data.get("value")
                if value is not None:
                    totals[side] += int(round(float(value)))
                    found[side] = True
        for side in ("home", "away"):
            result[side][target] = totals[side] if found[side] else None
    missing = [f"{side}.{key}" for side in ("home", "away") for key, value in result[side].items() if value is None]
    if missing:
        raise LiveDataError("Données statistiques incomplètes : " + ", ".join(missing) + ". Les champs ne seront pas remplis partiellement.")
    return result


def current_score(match):
    """Lit le score courant depuis les objets homeScore/awayScore."""
    scores = []
    for side in ("homeScore", "awayScore"):
        score = match.get(side) or {}
        value = score.get("current")
        if value is None:
            raise LiveDataError("Le fournisseur ne renvoie pas le score courant complet.")
        scores.append(int(value))
    return scores[0], scores[1]


def is_halftime(match):
    status = match.get("status") or {}
    description = " ".join(str(status.get(k) or "") for k in ("description", "shortName", "type")).casefold()
    return any(term in description for term in ("half time", "half-time", "halftime", "half break", "interval"))
