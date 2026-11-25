"""Diagnostic interactif du connecteur DataSportsAPI basketball.

L'outil n'affiche jamais la clé API. Il permet de vérifier la réponse réelle du
fournisseur et de lancer le parseur BPI sur un match LIVE sélectionné.
"""
import getpass
import sys
from pathlib import Path

# Permet l'import des modules à la racine même lorsque le script est lancé
# directement avec : python scripts/diagnose_datasportsapi_basketball.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bpi_live_data import (
    LiveDataError,
    extract_first_half_inputs,
    get_live_matches,
    get_match_statistics_diagnostic,
    is_halftime,
)


def _team_name(match, side):
    team = match.get(side) or {}
    return team.get("name") or f"{side} inconnu"


def _status(match):
    status = match.get("status") or {}
    if isinstance(status, dict):
        return " / ".join(
            str(status.get(key))
            for key in ("description", "shortName", "type")
            if status.get(key)
        ) or "statut inconnu"
    return str(status)


def _score(match):
    try:
        home = (match.get("homeScore") or {}).get("current")
        away = (match.get("awayScore") or {}).get("current")
        if home is None or away is None:
            return "score indisponible"
        return f"{home}-{away}"
    except (AttributeError, TypeError):
        return "score indisponible"


def show_live_matches(matches):
    print("\nMatchs basketball LIVE retournés par DataSportsAPI :")
    if not matches:
        print("Aucun match LIVE dans le flux à cet instant.")
        return
    for match in matches:
        print(
            f"ID {match.get('id')} | {_team_name(match, 'home')} - "
            f"{_team_name(match, 'away')} | {_score(match)} | {_status(match)}"
        )


def show_statistics(periods):
    print("\nPériodes et statistiques reçues (valeur / total si fourni) :")
    if not periods:
        print("Aucune période de statistiques reçue.")
        return
    for period in periods:
        print(f"\n[{period.get('period', 'période inconnue')}]")
        for group in period.get("groups") or []:
            group_name = group.get("name") or group.get("key") or "Groupe"
            print(f"  {group_name}")
            for item in group.get("items") or []:
                home = item.get("home") or {}
                away = item.get("away") or {}

                def value(side):
                    v, total = side.get("value"), side.get("total")
                    return f"{v}/{total}" if total is not None else str(v)

                print(
                    f"    {item.get('key')}: domicile {value(home)} | "
                    f"extérieur {value(away)}"
                )


def main():
    api_key = getpass.getpass("Clé DataSportsAPI (saisie masquée) : ").strip()
    if not api_key:
        print("Clé vide : arrêt.")
        return 2

    try:
        matches = get_live_matches(api_key)
        show_live_matches(matches)
        if not matches:
            return 0

        fixture_id = input(
            "\nSaisis l'ID du match à diagnostiquer (ou Entrée pour quitter) : "
        ).strip()
        if not fixture_id:
            return 0
        if not fixture_id.isdigit() or int(fixture_id) <= 0:
            print("ID invalide : un entier positif est attendu.")
            return 2

        selected = next(
            (match for match in matches if str(match.get("id")) == fixture_id),
            None,
        )
        if selected is None:
            print("Cet ID n'est pas dans la liste LIVE affichée. Arrêt sécurisé.")
            return 2

        response = get_match_statistics_diagnostic(int(fixture_id), api_key)
        diagnostic = response["diagnostic"]
        periods = response["periods"]
        print("\nDiagnostic de structure :")
        print(f"  Type data : {diagnostic.get('data_type')}")
        print(f"  Type periods : {diagnostic.get('periods_type')}")
        print(f"  Périodes : {diagnostic.get('period_names')}")
        show_statistics(periods)

        halftime_confirmed = is_halftime(selected)
        print(f"\nMi-temps détectée dans le statut API : {'oui' if halftime_confirmed else 'non'}")
        try:
            inputs = extract_first_half_inputs(
                periods, allow_all_period=halftime_confirmed
            )
        except LiveDataError as exc:
            print(f"\nPARSEUR BPI : REFUS (sécurité données)\n{exc}")
            return 1

        print("\nPARSEUR BPI : ACCEPTÉ")
        print("Statistiques normalisées Q1+Q2 :")
        for side in ("home", "away"):
            print(f"  {side}: {inputs[side]}")
        print("\nImportant : diagnostic API réussi, mais cela ne valide pas encore la calibration du modèle.")
        return 0

    except LiveDataError as exc:
        print(f"\nErreur connecteur : {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nDiagnostic interrompu.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
