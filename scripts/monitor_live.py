"""Surveillance des matchs de basket à la mi-temps et alertes Telegram BPI.

Le moteur appelé est un prototype exploratoire non entraîné/non calibré.
Aucune recommandation de mise n'est produite.
"""
import json
import logging
import os
import sys
from pathlib import Path

# Permet l’import des modules situés à la racine quand le script est lancé par chemin.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

from bpi_live_data import (
    LiveDataError,
    current_score,
    extract_first_half_inputs,
    get_live_matches,
    get_match_statistics_diagnostic,
    is_halftime,
)
from bpi_validation import validate_halftime_data
from engine import simulate_second_half

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
STATE_PATH = Path("data/telegram_notified.json")


def _name(obj):
    if isinstance(obj, dict):
        return obj.get("name") or obj.get("shortName") or obj.get("displayName") or "Équipe inconnue"
    return str(obj or "Équipe inconnue")


def _fixture_id(match):
    return match.get("id") or match.get("fixtureId") or match.get("fixture_id")


def _competition(match):
    for key in ("competition", "tournament", "league"):
        value = match.get(key)
        if value:
            return _name(value)
    return "Compétition non précisée"


def _load_state():
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        logging.warning("État de déduplication illisible; démarrage avec un état vide.")
        return {}


def _save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _telegram_send(token, chat_id, message):
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError("Telegram a refusé l'envoi du message.")


def _prediction_message(match, home, away, score_h, score_a, stats_h, stats_a, result, warnings):
    total = result["total_mean"]
    margin = result["home_mean"] - result["away_mean"]
    favorite = home if margin > 0 else away if margin < 0 else "Équilibre"
    quality = "Données complètes" if not warnings else "Données avec réserves : " + " ".join(warnings)
    return (
        "🏀 BPI — ALERTE MI-TEMPS\n"
        f"{home} {score_h}–{score_a} {away}\n"
        f"Compétition : {_competition(match)}\n\n"
        "SIMULATION EXPLORATOIRE — NON CALIBRÉE\n"
        f"Équipe projetée en tête : {favorite}\n"
        f"Probabilité simulée victoire domicile : {result['home_win']:.1f}%\n"
        f"Probabilité simulée victoire extérieur : {result['away_win']:.1f}%\n"
        f"Score final moyen simulé : {result['home_mean']:.1f}–{result['away_mean']:.1f}\n"
        f"Total moyen simulé : {total:.1f}\n"
        f"Intervalle central 80% du total : {result['total_p10']:.0f}–{result['total_p90']:.0f}\n\n"
        f"Contrôle des données : {quality}\n"
        "⚠️ Prototype non entraîné et non calibré : ces pourcentages ne sont pas des probabilités fiables. "
        "Aucune recommandation de pari ni de mise. Vérification humaine requise."
    )


def main():
    api_key = os.getenv("DATASPORTSAPI_API_KEY", "").strip()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    missing = [key for key, value in (
        ("DATASPORTSAPI_API_KEY", api_key),
        ("TELEGRAM_BOT_TOKEN", token),
        ("TELEGRAM_CHAT_ID", chat_id),
    ) if not value]
    if missing:
        raise SystemExit("Secrets GitHub manquants : " + ", ".join(missing))

    state = _load_state()
    matches = get_live_matches(api_key)
    logging.info("%d match(s) LIVE reçus du fournisseur.", len(matches))
    sent = 0

    for match in matches:
        if not isinstance(match, dict) or not is_halftime(match):
            continue
        fixture_id = _fixture_id(match)
        if fixture_id is None:
            logging.warning("Match à la pause ignoré : identifiant fournisseur absent.")
            continue
        key = str(fixture_id)
        if key in state:
            continue

        try:
            home = _name(match.get("home"))
            away = _name(match.get("away"))
            score_h, score_a = current_score(match)
            diagnostic = get_match_statistics_diagnostic(fixture_id, api_key)
            stats = extract_first_half_inputs(diagnostic["periods"], allow_all_period=True)
            errors, warnings = validate_halftime_data(
                score_h, score_a, stats["home"], stats["away"]
            )
            if errors:
                logging.warning("Match %s ignoré : validation bloquante : %s", key, " | ".join(errors))
                continue
            result = simulate_second_half(score_h, score_a, stats["home"], stats["away"])
            message = _prediction_message(
                match, home, away, score_h, score_a,
                stats["home"], stats["away"], result, warnings
            )
            _telegram_send(token, chat_id, message)
            state[key] = {
                "status": "telegram_sent",
                "home": home,
                "away": away,
                "halftime_score": [score_h, score_a],
            }
            _save_state(state)
            sent += 1
            logging.info("Alerte envoyée pour le match %s.", key)
        except (LiveDataError, requests.RequestException, ValueError, TypeError, RuntimeError) as exc:
            logging.warning("Match %s non traité : %s", key, exc)

    _save_state(state)
    logging.info("Surveillance terminée : %d alerte(s) envoyée(s).", sent)


if __name__ == "__main__":
    main()
