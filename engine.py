"""Moteur Monte Carlo exploratoire BPI.

Ce moteur n'est pas entraîné sur un historique réel et ses sorties ne sont pas calibrées.
Il sert à tester le pipeline et doit être remplacé/étalonné après constitution des données.
"""
import numpy as np


def estimate_possessions(stats):
    """Approximation standard des possessions d'une équipe sur une période."""
    return max(1.0, stats["fga"] - stats["orb"] + stats["tov"] + 0.44 * stats["fta"])


def simulate_second_half(home_ht, away_ht, h, a, n=10000, seed=None):
    if n < 1000:
        raise ValueError("Utiliser au moins 1 000 simulations.")
    hp = estimate_possessions(h)
    ap = estimate_possessions(a)
    # Le rythme partagé évite de supposer deux volumes de possessions indépendants.
    pace_mean = float(np.clip((hp + ap) / 2, 25, 65))
    rng = np.random.default_rng(seed)

    # Régression prudente vers une efficacité neutre. Hypothèse provisoire,
    # non estimée sur une base historique.
    h_observed = home_ht / hp
    a_observed = away_ht / ap
    h_ppp = float(np.clip(0.55 * h_observed + 0.45 * 1.05, 0.65, 1.65))
    a_ppp = float(np.clip(0.55 * a_observed + 0.45 * 1.05, 0.65, 1.65))

    # Une fluctuation commune du rythme conserve une corrélation entre équipes.
    pace = rng.normal(pace_mean, 3.5, n).clip(20, 72)
    h_eff = rng.normal(h_ppp, 0.16, n).clip(0.60, 1.75)
    a_eff = rng.normal(a_ppp, 0.16, n).clip(0.60, 1.75)
    h_second = rng.poisson(pace * h_eff)
    a_second = rng.poisson(pace * a_eff)

    home_final = home_ht + h_second
    away_final = away_ht + a_second
    totals = home_final + away_final
    margins = home_final - away_final
    return {
        "home_win": float(np.mean(margins > 0) * 100),
        "away_win": float(np.mean(margins < 0) * 100),
        "tie": float(np.mean(margins == 0) * 100),
        "home_mean": float(np.mean(home_final)),
        "away_mean": float(np.mean(away_final)),
        "total_mean": float(np.mean(totals)),
        "total_median": float(np.median(totals)),
        "total_p10": float(np.percentile(totals, 10)),
        "total_p90": float(np.percentile(totals, 90)),
        "margin_p10": float(np.percentile(margins, 10)),
        "margin_p90": float(np.percentile(margins, 90)),
        "home_possessions_ht": float(hp),
        "away_possessions_ht": float(ap),
        "pace_mean": pace_mean,
        "home_ppp_assumed": h_ppp,
        "away_ppp_assumed": a_ppp,
    }
