import io
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from engine import simulate_second_half
from bpi_live_data import (find_live_match, get_match_statistics, extract_first_half_inputs, current_score, is_halftime, LiveDataError)

st.set_page_config(page_title="BPI V1.0", page_icon="🏀", layout="wide")
st.title("🏀 BPI V1.0 — Basketball Predictive Intelligence")
st.caption("Prototype expérimental — aucune prédiction fiable sans données réelles et vérifiées.")
st.info("La collecte LIVE remplit automatiquement les champs lorsque le fournisseur publie toutes les statistiques requises. Les données manquantes ne sont jamais remplacées par des zéros.")

if "prediction_history" not in st.session_state:
    st.session_state.prediction_history = []


st.subheader("Match")
st.caption("Renseigne les deux équipes pour préparer l'analyse ou rechercher le match en direct.")
team_cols = st.columns(2)
with team_cols[0]:
    home = st.text_input("Équipe à domicile", "", key="home_team")
with team_cols[1]:
    away = st.text_input("Équipe extérieure", "", key="away_team")
competition = st.selectbox("Compétition", ["NBA", "EuroLeague", "Autre"])
game_date = st.date_input("Date du match")
data_verified = st.checkbox("Je confirme que le score et toutes les statistiques saisies proviennent de données réelles vérifiées.", key="data_verified")

st.subheader("Collecte automatique des données LIVE")
st.caption("Saisis les deux équipes puis lance la collecte. BPI récupère le match et tente de remplir le score et les statistiques des deux premiers quart-temps.")
if st.button("Collecter et remplir automatiquement", type="secondary"):
    try:
        api_key = st.secrets.get("DATASPORTSAPI_API_KEY", "")
        if not api_key:
            st.error("Clé API absente. Ajoute DATASPORTSAPI_API_KEY dans les Secrets Streamlit.")
        elif not home.strip() or not away.strip():
            st.error("Renseigne les deux équipes dans le panneau Match.")
        else:
            live_match = find_live_match(home, away, api_key)
            periods = get_match_statistics(live_match["id"], api_key)
            first_half = extract_first_half_inputs(periods)
            if not is_halftime(live_match):
                st.session_state["bpi_live_match"] = live_match
                st.session_state["bpi_live_periods"] = periods
                st.warning("Match identifié et statistiques reçues, mais le fournisseur ne confirme pas la mi-temps. Les champs de score ne sont pas remplis pour éviter d'utiliser un score en cours comme score de pause.")
            else:
                home_score, away_score = current_score(live_match)
                st.session_state["home_ht"] = home_score
                st.session_state["away_ht"] = away_score
                for side, prefix in (("home", "h"), ("away", "a")):
                    for metric, value in first_half[side].items():
                        st.session_state[f"{prefix}_{metric}"] = value
                st.session_state["bpi_live_match"] = live_match
                st.session_state["bpi_live_periods"] = periods
                st.session_state["bpi_data_filled"] = True
                st.success("Données LIVE récupérées et champs préremplis. Vérifie-les avant de lancer l'analyse.")
    except LiveDataError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Erreur pendant la collecte : {exc}")

if st.session_state.get("bpi_live_match"):
    match = st.session_state["bpi_live_match"]
    st.write(f"**{match.get('home', {}).get('name')}** — **{match.get('away', {}).get('name')}**")
    st.caption(f"Compétition : {(match.get('league') or {}).get('name', 'indisponible')} · Statut : {(match.get('status') or {}).get('description', 'indisponible')} · ID fournisseur : {match.get('id')}")
    periods = st.session_state.get("bpi_live_periods") or []
    if periods:
        with st.expander("Contrôle des statistiques reçues du fournisseur", expanded=False):
            for period in periods:
                st.write(f"Période : {period.get('period', 'inconnue')}")
                rows = []
                for group in period.get("groups", []):
                    for item in group.get("items", []):
                        rows.append({
                            "Statistique": item.get("name") or item.get("key"),
                            "Domicile": (item.get("home") or {}).get("display", (item.get("home") or {}).get("value")),
                            "Extérieur": (item.get("away") or {}).get("display", (item.get("away") or {}).get("value")),
                        })
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if st.session_state.get("bpi_data_filled"):
        st.success("Préremplissage effectué à partir des statistiques des quart-temps 1 et 2.")

st.subheader("Score à la mi-temps")
c1, c2 = st.columns(2)
with c1:
    home_ht = st.number_input(f"Points — {home}", min_value=0, max_value=150, value=0, key="home_ht")
with c2:
    away_ht = st.number_input(f"Points — {away}", min_value=0, max_value=150, value=0, key="away_ht")

st.subheader("Statistiques de la première mi-temps")
st.caption("Les champs inconnus peuvent rester à zéro. Vérifie les tentatives et réussites.")
cols = st.columns(4)

def number(label, value, key, maxv=100):
    return st.number_input(label, min_value=0, max_value=maxv, value=value, key=key)

with cols[0]:
    h_fga = number(f"{home} tirs tentés", 0, "h_fga")
    a_fga = number(f"{away} tirs tentés", 0, "a_fga")
with cols[1]:
    h_fgm = number(f"{home} tirs réussis", 0, "h_fgm")
    a_fgm = number(f"{away} tirs réussis", 0, "a_fgm")
with cols[2]:
    h_3pa = number(f"{home} tirs à 3 pts tentés", 0, "h_3pa", 80)
    a_3pa = number(f"{away} tirs à 3 pts tentés", 0, "a_3pa", 80)
with cols[3]:
    h_3pm = number(f"{home} tirs à 3 pts réussis", 0, "h_3pm", 80)
    a_3pm = number(f"{away} tirs à 3 pts réussis", 0, "a_3pm", 80)

cols = st.columns(4)
with cols[0]:
    h_tov = number(f"{home} pertes de balle", 0, "h_tov", 40)
    a_tov = number(f"{away} pertes de balle", 0, "a_tov", 40)
with cols[1]:
    h_orb = number(f"{home} rebonds offensifs", 0, "h_orb", 30)
    a_orb = number(f"{away} rebonds offensifs", 0, "a_orb", 30)
with cols[2]:
    h_ftm = number(f"{home} lancers francs réussis", 0, "h_ftm", 50)
    a_ftm = number(f"{away} lancers francs réussis", 0, "a_ftm", 50)
with cols[3]:
    h_fta = number(f"{home} lancers francs tentés", 0, "h_fta", 60)
    a_fta = number(f"{away} lancers francs tentés", 0, "a_fta", 60)

sims = st.select_slider("Nombre de simulations", options=[1000, 5000, 10000, 25000], value=10000)

if st.button("Analyser la deuxième mi-temps", type="primary"):
    invalid = (
        h_fgm > h_fga or a_fgm > a_fga or
        h_3pm > h_3pa or a_3pm > a_3pa or
        h_3pm > h_fgm or a_3pm > a_fgm or
        h_fta < h_ftm or a_fta < a_ftm or
        h_3pa > h_fga or a_3pa > a_fga
    )
    stats_values = [h_fga, a_fga, h_fgm, a_fgm, h_3pa, a_3pa, h_3pm, a_3pm,
                    h_tov, a_tov, h_orb, a_orb, h_ftm, a_ftm, h_fta, a_fta]
    if not (data_verified or st.session_state.get("bpi_data_filled", False)):
        st.error("Analyse bloquée : confirme d'abord que les données saisies sont réelles et vérifiées.")
    elif home_ht == 0 and away_ht == 0:
        st.error("Score de mi-temps manquant : renseigne le score réel.")
    elif all(v == 0 for v in stats_values):
        st.error("Statistiques manquantes : aucune simulation ne sera faite avec des statistiques vides.")
    elif invalid:
        st.error("Statistiques incohérentes : vérifie les tirs et les lancers francs.")
    elif not home.strip() or not away.strip() or home.strip() == away.strip():
        st.error("Renseigne deux noms d'équipes différents.")
    else:
        h = {"fga": h_fga, "fgm": h_fgm, "3pa": h_3pa, "3pm": h_3pm, "tov": h_tov, "orb": h_orb, "ftm": h_ftm, "fta": h_fta}
        a = {"fga": a_fga, "fgm": a_fgm, "3pa": a_3pa, "3pm": a_3pm, "tov": a_tov, "orb": a_orb, "ftm": a_ftm, "fta": a_fta}
        result = simulate_second_half(home_ht, away_ht, h, a, sims)
        # Compatibilité avec une ancienne version du moteur qui ne renvoyait pas total_mean.
        # Normalisation défensive : l'interface reste compatible avec plusieurs schémas du moteur.
        home_mean = result.get("home_mean", float(home_ht))
        away_mean = result.get("away_mean", float(away_ht))
        total_mean = result.get("total_mean", home_mean + away_mean)
        total_median = result.get("total_median", total_mean)
        home_win = result.get("home_win")
        away_win = result.get("away_win")
        tie = result.get("tie")
        total_p10 = result.get("total_p10")
        total_p90 = result.get("total_p90")
        margin_p10 = result.get("margin_p10")
        margin_p90 = result.get("margin_p90")
        home_possessions = result.get("home_possessions_ht")
        away_possessions = result.get("away_possessions_ht")
        pace_mean = result.get("pace_mean")
        home_ppp = result.get("home_ppp_assumed")
        away_ppp = result.get("away_ppp_assumed")
        st.warning("Attention : simulation exploratoire, non entraînée et non calibrée. Ce n'est pas une probabilité fiable ni un conseil de pari.")
        m1, m2, m3 = st.columns(3)
        m1.metric(f"Victoire {home}", f"{home_win:.1f}%" if home_win is not None else "Indisponible")
        m2.metric(f"Victoire {away}", f"{away_win:.1f}%" if away_win is not None else "Indisponible")
        m3.metric("Égalité à la fin du temps réglementaire", f"{tie:.1f}%" if tie is not None else "Indisponible")
        st.subheader("Projection du score final")
        st.write(f"**{home} : {home_mean:.1f} points** · **{away} : {away_mean:.1f} points**")
        st.write(f"Total moyen : **{total_mean:.1f}** · médian : **{total_median:.0f}**")
        st.write(f"Intervalle exploratoire du total (10e–90e percentile) : **{total_p10:.0f} à {total_p90:.0f} points**" if total_p10 is not None and total_p90 is not None else "Intervalle du total : indisponible dans cette version du moteur.")
        st.write(f"Intervalle exploratoire de la marge domicile (10e–90e percentile) : **{margin_p10:.0f} à {margin_p90:.0f} points**" if margin_p10 is not None and margin_p90 is not None else "Intervalle de marge : indisponible dans cette version du moteur.")
        st.subheader("Diagnostic du rythme et de l'efficacité")
        st.write(f"Possessions estimées à la pause : {home_possessions:.1f} — {away_possessions:.1f}. Rythme partagé supposé pour la seconde mi-temps : {pace_mean:.1f} possessions." if None not in (home_possessions, away_possessions, pace_mean) else "Diagnostic des possessions : indisponible dans cette version du moteur.")
        st.write(f"Efficacité par possession supposée : {home} {home_ppp:.2f} · {away} {away_ppp:.2f} points." if home_ppp is not None and away_ppp is not None else "Efficacité par possession : indisponible dans cette version du moteur.")
        st.session_state.prediction_history.append({
            "horodatage_utc": datetime.now(timezone.utc).isoformat(),
            "date_match": str(game_date), "competition": competition,
            "domicile": home, "exterieur": away,
            "score_pause_domicile": home_ht, "score_pause_exterieur": away_ht,
            "simulations": sims, "proba_victoire_domicile_pct": round(home_win, 2) if home_win is not None else None,
            "proba_victoire_exterieur_pct": round(away_win, 2) if away_win is not None else None,
            "score_final_moyen_domicile": round(home_mean, 2),
            "score_final_moyen_exterieur": round(away_mean, 2),
            "total_moyen": round(total_mean, 2),
            "total_p10": round(total_p10, 2) if total_p10 is not None else None, "total_p90": round(total_p90, 2) if total_p90 is not None else None,
            "statut_modele": "prototype_non_calibre"
        })
        st.success("Analyse terminée. Elle est ajoutée à l'historique de cette session.")
        st.caption("Les hypothèses restent simplifiées : pas de fautes d'équipe, rotations, blessures, play-by-play ni ajustements tactiques.")

st.divider()
st.subheader("Historique des analyses de cette session")
if st.session_state.prediction_history:
    history = pd.DataFrame(st.session_state.prediction_history)
    st.dataframe(history, use_container_width=True)
    csv = history.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Télécharger l'historique CSV", data=csv, file_name="bpi_historique_predictions.csv", mime="text/csv")
else:
    st.info("Aucune analyse enregistrée dans cette session. L'historique sera perdu à la fermeture de la session si tu ne télécharges pas le CSV.")
