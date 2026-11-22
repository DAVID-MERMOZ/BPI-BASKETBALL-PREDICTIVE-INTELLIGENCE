import io
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from engine import simulate_second_half

st.set_page_config(page_title="BPI V1.0", page_icon="🏀", layout="wide")
st.title("🏀 BPI V1.0 — Basketball Predictive Intelligence")
st.caption("Prototype expérimental — statistiques saisies manuellement à la mi-temps.")

if "prediction_history" not in st.session_state:
    st.session_state.prediction_history = []

with st.sidebar:
    st.header("Match")
    competition = st.selectbox("Compétition", ["NBA", "EuroLeague", "Autre"])
    game_date = st.date_input("Date du match")
    home = st.text_input("Équipe à domicile", "Équipe A")
    away = st.text_input("Équipe extérieure", "Équipe B")
    st.info("Saisis uniquement les informations connues à la mi-temps.")

st.subheader("Score à la mi-temps")
c1, c2 = st.columns(2)
with c1:
    home_ht = st.number_input(f"Points — {home}", min_value=0, max_value=100, value=54)
with c2:
    away_ht = st.number_input(f"Points — {away}", min_value=0, max_value=100, value=49)

st.subheader("Statistiques de la première mi-temps")
st.caption("Les champs inconnus peuvent rester à zéro. Vérifie les tentatives et réussites.")
cols = st.columns(4)

def number(label, value, key, maxv=100):
    return st.number_input(label, min_value=0, max_value=maxv, value=value, key=key)

with cols[0]:
    h_fga = number(f"{home} tirs tentés", 42, "h_fga")
    a_fga = number(f"{away} tirs tentés", 40, "a_fga")
with cols[1]:
    h_fgm = number(f"{home} tirs réussis", 21, "h_fgm")
    a_fgm = number(f"{away} tirs réussis", 19, "a_fgm")
with cols[2]:
    h_3pa = number(f"{home} tirs à 3 pts tentés", 17, "h_3pa", 80)
    a_3pa = number(f"{away} tirs à 3 pts tentés", 16, "a_3pa", 80)
with cols[3]:
    h_3pm = number(f"{home} tirs à 3 pts réussis", 7, "h_3pm", 80)
    a_3pm = number(f"{away} tirs à 3 pts réussis", 6, "a_3pm", 80)

cols = st.columns(4)
with cols[0]:
    h_tov = number(f"{home} pertes de balle", 6, "h_tov", 40)
    a_tov = number(f"{away} pertes de balle", 7, "a_tov", 40)
with cols[1]:
    h_orb = number(f"{home} rebonds offensifs", 5, "h_orb", 30)
    a_orb = number(f"{away} rebonds offensifs", 4, "a_orb", 30)
with cols[2]:
    h_ftm = number(f"{home} lancers francs réussis", 5, "h_ftm", 50)
    a_ftm = number(f"{away} lancers francs réussis", 5, "a_ftm", 50)
with cols[3]:
    h_fta = number(f"{home} lancers francs tentés", 6, "h_fta", 60)
    a_fta = number(f"{away} lancers francs tentés", 6, "a_fta", 60)

sims = st.select_slider("Nombre de simulations", options=[1000, 5000, 10000, 25000], value=10000)

if st.button("Analyser la deuxième mi-temps", type="primary"):
    invalid = (
        h_fgm > h_fga or a_fgm > a_fga or
        h_3pm > h_3pa or a_3pm > a_3pa or
        h_3pm > h_fgm or a_3pm > a_fgm or
        h_fta < h_ftm or a_fta < a_ftm or
        h_3pa > h_fga or a_3pa > a_fga
    )
    if invalid:
        st.error("Statistiques incohérentes : vérifie les tirs et les lancers francs.")
    elif not home.strip() or not away.strip() or home.strip() == away.strip():
        st.error("Renseigne deux noms d'équipes différents.")
    else:
        h = {"fga": h_fga, "fgm": h_fgm, "3pa": h_3pa, "3pm": h_3pm, "tov": h_tov, "orb": h_orb, "ftm": h_ftm, "fta": h_fta}
        a = {"fga": a_fga, "fgm": a_fgm, "3pa": a_3pa, "3pm": a_3pm, "tov": a_tov, "orb": a_orb, "ftm": a_ftm, "fta": a_fta}
        result = simulate_second_half(home_ht, away_ht, h, a, sims)
        st.warning("Attention : simulation exploratoire, non entraînée et non calibrée. Ce n'est pas une probabilité fiable ni un conseil de pari.")
        m1, m2, m3 = st.columns(3)
        m1.metric(f"Victoire {home}", f"{result['home_win']:.1f}%")
        m2.metric(f"Victoire {away}", f"{result['away_win']:.1f}%")
        m3.metric("Égalité à la fin du temps réglementaire", f"{result['tie']:.1f}%")
        st.subheader("Projection du score final")
        st.write(f"**{home} : {result['home_mean']:.1f} points** · **{away} : {result['away_mean']:.1f} points**")
        st.write(f"Total moyen : **{result['total_mean']:.1f}** · médian : **{result['total_median']:.0f}**")
        st.write(f"Intervalle exploratoire du total (10e–90e percentile) : **{result['total_p10']:.0f} à {result['total_p90']:.0f} points**")
        st.write(f"Intervalle exploratoire de la marge domicile (10e–90e percentile) : **{result['margin_p10']:.0f} à {result['margin_p90']:.0f} points**")
        st.subheader("Diagnostic du rythme et de l'efficacité")
        st.write(f"Possessions estimées à la pause : {result['home_possessions_ht']:.1f} — {result['away_possessions_ht']:.1f}. Rythme partagé supposé pour la seconde mi-temps : {result['pace_mean']:.1f} possessions.")
        st.write(f"Efficacité par possession supposée : {home} {result['home_ppp_assumed']:.2f} · {away} {result['away_ppp_assumed']:.2f} points.")
        st.session_state.prediction_history.append({
            "horodatage_utc": datetime.now(timezone.utc).isoformat(),
            "date_match": str(game_date), "competition": competition,
            "domicile": home, "exterieur": away,
            "score_pause_domicile": home_ht, "score_pause_exterieur": away_ht,
            "simulations": sims, "proba_victoire_domicile_pct": round(result["home_win"], 2),
            "proba_victoire_exterieur_pct": round(result["away_win"], 2),
            "score_final_moyen_domicile": round(result["home_mean"], 2),
            "score_final_moyen_exterieur": round(result["away_mean"], 2),
            "total_moyen": round(result["total_mean"], 2),
            "total_p10": round(result["total_p10"], 2), "total_p90": round(result["total_p90"], 2),
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
