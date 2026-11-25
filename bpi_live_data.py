"""Connecteur DataSportsAPI et normalisation des statistiques basket LIVE."""
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


def get_live_matches(api_key):
    """Retourne le tableau LIVE basket complet, sans filtrage fragile par nom."""
    payload = _get("/livescores", api_key, {"sport": "basketball"})
    data = payload.get("data") or []
    if not isinstance(data, list):
        raise LiveDataError("Format inattendu du tableau LIVE : la propriété data n'est pas une liste.")
    return data


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


def get_match_statistics_diagnostic(fixture_id, api_key):
    """Retourne les périodes et un diagnostic structurel sans exposer de données sensibles."""
    payload = _get(f"/fixtures/{int(fixture_id)}/statistics", api_key)
    if not isinstance(payload, dict):
        raise LiveDataError("Réponse statistiques inattendue : l'objet JSON principal n'est pas un dictionnaire.")
    data = payload.get("data")
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return {
            "periods": [],
            "diagnostic": {
                "top_level_keys": sorted(str(k) for k in payload.keys()),
                "data_type": type(data).__name__,
                "data_keys": [],
                "periods_type": "absent",
                "period_names": [],
            },
        }
    periods = data.get("periods")
    valid_periods = periods if isinstance(periods, list) else []
    names = [
        str(p.get("period", "inconnu"))
        for p in valid_periods
        if isinstance(p, dict)
    ]
    return {
        "periods": valid_periods,
        "diagnostic": {
            "top_level_keys": sorted(str(k) for k in payload.keys()),
            "data_type": type(data).__name__,
            "data_keys": sorted(str(k) for k in data.keys()),
            "periods_type": type(periods).__name__ if periods is not None else "absent",
            "period_names": names,
            "period_count": len(valid_periods),
        },
    }


def get_match_statistics(fixture_id, api_key):
    """Compatibilité : retourne uniquement la liste normalisée des périodes."""
    return get_match_statistics_diagnostic(fixture_id, api_key)["periods"]


def _period_values(period):
    values = {}
    for group in period.get("groups") or []:
        for item in group.get("items") or []:
            key = item.get("key")
            if key:
                values[key] = item
    return values


def extract_first_half_inputs(periods, allow_all_period=False):
    """Extrait Q1+Q2, ou 'all' seulement si la mi-temps est confirmée."""
    by_period = {p.get("period"): p for p in periods or []}
    first_two = [by_period.get("period1"), by_period.get("period2")]
    if not all(first_two):
        aggregate = by_period.get("all")
        if allow_all_period and aggregate:
            first_two = [aggregate]
        else:
            received = [str(p.get("period")) for p in periods or [] if p.get("period")]
            detail = ", ".join(received) if received else "aucune période"
            raise LiveDataError("Statistiques Q1+Q2 indisponibles. Périodes reçues : " + detail + ". La période 'all' ne sera utilisée que si la mi-temps est confirmée par le fournisseur.")

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
    attempts_from_made = {
        "fga": "fieldGoalsMade",
        "3pa": "threePointersMade",
        "fta": "freeThrowsMade",
    }
    optional = {"tov", "orb"}
    result = {"home": {}, "away": {}}
    missing_required = []

    for target, source in aliases.items():
        totals = {"home": 0, "away": 0}
        missing_optional = {"home": False, "away": False}
        for period in first_two:
            period_name = str(period.get("period", "unknown"))
            values = _period_values(period)
            item = values.get(source)
            for side in ("home", "away"):
                side_data = (item or {}).get(side) or {}
                value = side_data.get("value")
                if value is None and target in attempts_from_made:
                    made_item = values.get(attempts_from_made[target])
                    made_side = (made_item or {}).get(side) or {}
                    value = made_side.get("total")
                if value is None:
                    if target in optional:
                        missing_optional[side] = True
                    else:
                        missing_required.append(f"{side}.{target} ({period_name})")
                else:
                    totals[side] += int(round(float(value)))
        for side in ("home", "away"):
            result[side][target] = 0 if target in optional and missing_optional[side] else totals[side]

    if missing_required:
        raise LiveDataError(
            "Données essentielles incomplètes par période : "
            + ", ".join(missing_required)
            + ". Aucun préremplissage effectué."
        )
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
