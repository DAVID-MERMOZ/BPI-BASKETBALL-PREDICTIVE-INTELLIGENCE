import numpy as np

def _rate(stats):
    # Approximation grossière des possessions de la première mi-temps.
    return max(25.0, stats["fga"] - stats["orb"] + stats["tov"] + 0.44 * stats["fta"])

def simulate_second_half(home_ht, away_ht, h, a, n=10000, seed=42):
    rng = np.random.default_rng(seed)
    hp, ap = _rate(h), _rate(a)
    pace = float(np.clip((hp + ap) / 2, 30, 65))

    # Rétraction partielle vers une efficacité neutre : hypothèse de prototype.
    h_ppp = 0.55 * (home_ht / hp if hp else 1.05) + 0.45 * 1.05
    a_ppp = 0.55 * (away_ht / ap if ap else 1.05) + 0.45 * 1.05

    h_pos = rng.normal(pace, 4.5, n).clip(25, 70)
    a_pos = rng.normal(pace, 4.5, n).clip(25, 70)
    h_eff = rng.normal(h_ppp, 0.18, n).clip(0.65, 1.65)
    a_eff = rng.normal(a_ppp, 0.18, n).clip(0.65, 1.65)
    h_second = rng.poisson(h_pos * h_eff)
    a_second = rng.poisson(a_pos * a_eff)

    hf, af = home_ht + h_second, away_ht + a_second
    totals = hf + af
    return {
        "home_win": float(np.mean(hf > af) * 100),
        "away_win": float(np.mean(af > hf) * 100),
        "tie": float(np.mean(hf == af) * 100),
        "home_mean": float(np.mean(hf)),
        "away_mean": float(np.mean(af)),
        "total_median": float(np.median(totals)),
        "total_p10": float(np.percentile(totals, 10)),
        "total_p90": float(np.percentile(totals, 90)),
        "notes": (
            f"Possessions estimées en première mi-temps : {hp:.1f} pour l'équipe à domicile "
            f"et {ap:.1f} pour l'équipe extérieure. L'efficacité observée est partiellement "
            "ramenée vers une base neutre. Les fautes, rotations, blessures, force des adversaires, "
            "contexte de compétition et ajustements tactiques ne sont pas modélisés."
        ),
    }
