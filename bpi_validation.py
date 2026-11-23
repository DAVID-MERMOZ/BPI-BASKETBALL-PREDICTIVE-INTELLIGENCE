"""Validation stricte des données de mi-temps avant toute simulation.

Les contrôles distinguent les impossibilités mathématiques (erreurs bloquantes)
des écarts de cohérence du score (avertissements à examiner).
"""

REQUIRED_STATS = ("fga", "fgm", "3pa", "3pm", "ftm", "fta")
OPTIONAL_STATS = ("tov", "orb")


def validate_team_stats(stats, side="équipe"):
    errors = []
    warnings = []
    missing = [key for key in REQUIRED_STATS if key not in stats or stats[key] is None]
    if missing:
        return [f"{side}: statistiques essentielles manquantes ({', '.join(missing)})."], warnings
    for key in OPTIONAL_STATS:
        if key not in stats or stats[key] is None:
            warnings.append(f"{side}: {key} indisponible; l'estimation des possessions utilisera une approximation sans correction rebonds offensifs/pertes de balle.")
            stats[key] = 0

    for key in REQUIRED_STATS + OPTIONAL_STATS:
        value = stats[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{side}: {key} doit être numérique.")
        elif value < 0 or int(value) != value:
            errors.append(f"{side}: {key} doit être un entier positif ou nul.")

    if errors:
        return errors, warnings

    if stats["fgm"] > stats["fga"]:
        errors.append(f"{side}: tirs réussis supérieurs aux tirs tentés.")
    if stats["3pm"] > stats["3pa"]:
        errors.append(f"{side}: tirs à 3 points réussis supérieurs aux tentatives.")
    if stats["3pa"] > stats["fga"]:
        errors.append(f"{side}: tentatives à 3 points supérieures aux tirs tentés.")
    if stats["3pm"] > stats["fgm"]:
        errors.append(f"{side}: tirs à 3 points réussis supérieurs aux tirs réussis totaux.")
    if stats["ftm"] > stats["fta"]:
        errors.append(f"{side}: lancers francs réussis supérieurs aux tentatives.")
    possessions = stats["fga"] - stats["orb"] + stats["tov"] + 0.44 * stats["fta"]
    if possessions <= 0:
        errors.append(f"{side}: estimation des possessions nulle ou négative.")
    return errors, warnings


def validate_halftime_data(home_score, away_score, home_stats, away_stats):
    """Retourne (errors, warnings); aucune correction silencieuse des valeurs."""
    errors = []
    warnings = []
    for label, score in (("domicile", home_score), ("extérieur", away_score)):
        if not isinstance(score, (int, float)) or isinstance(score, bool) or score < 0 or int(score) != score:
            errors.append(f"Score {label}: valeur invalide.")
    if errors:
        return errors, warnings

    for side, score, stats in (
        ("Domicile", home_score, home_stats),
        ("Extérieur", away_score, away_stats),
    ):
        team_errors, team_warnings = validate_team_stats(stats, side)
        errors.extend(team_errors)
        warnings.extend(team_warnings)
        if not team_errors:
            # Score théorique: 2 points par panier + bonus du tir à 3 pts + LF.
            expected = 2 * stats["fgm"] + stats["3pm"] + stats["ftm"]
            if expected != score:
                warnings.append(
                    f"{side}: score saisi ({score}) différent du score reconstruit "
                    f"à partir des tirs ({expected}); vérifier la définition des statistiques."
                )
    return errors, warnings
