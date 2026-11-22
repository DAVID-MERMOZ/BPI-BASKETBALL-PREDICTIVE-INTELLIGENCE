import streamlit as st
from engine import simulate_second_half

st.set_page_config(page_title="BPI V1.0", page_icon="🏀", layout="wide")
st.title("🏀 BPI V1.0 — Basketball Predictive Intelligence")
st.caption("Prototype expérimental — saisie manuelle à la mi-temps, sans API live ni modèle entraîné.")

with st.sidebar:
    st.header("Match")
    competition = st.selectbox("Compétition", ["NBA", "EuroLeague", "Autre"])
    home = st.text_input("Équipe à domicile", "Équipe A")
    away = st.text_input("Équipe extérieure", "Équipe B")
    st.info("Saisis uniquement les données réellement connues à la mi-temps.")

st.subheader("Score à la mi-temps")
c1, c2 = st.columns(2)
with c1:
    home_ht = st.number_input(f"Points — {home}", min_value=0, max_value=100, value=54)
with c2:
    away_ht = st.number_input(f"Points — {away}", min_value=0, max_value=100, value=49)

st.subheader("Statistiques de la première mi-temps")
st.caption("Les champs inconnus peuvent rester à zéro. Les valeurs doivent être cohérentes.")
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
        h_fta < h_ftm or a_fta < a_ftm
    )
    if invalid:
        st.error("Statistiques incohérentes : vérifie les réussites et les tentatives.")
    else:
        result = simulate_second_half(
            home_ht, away_ht,
            {"fga": h_fga, "fgm": h_fgm, "3pa": h_3pa, "3pm": h_3pm, "tov": h_tov, "orb": h_orb, "ftm": h_ftm, "fta": h_fta},
            {"fga": a_fga, "fgm": a_fgm, "3pa": a_3pa, "3pm": a_3pm, "tov": a_tov, "orb": a_orb, "ftm": a_ftm, "fta": a_fta},
            sims
        )
        st.warning("Résultats exploratoires uniquement : modèle non entraîné et probabilités non calibrées.")
        m1, m2, m3 = st.columns(3)
        m1.metric(f"Victoire {home}", f"{result['home_win']:.1f}%")
        m2.metric(f"Victoire {away}", f"{result['away_win']:.1f}%")
        m3.metric("Égalité après temps réglementaire", f"{result['tie']:.1f}%")
        st.subheader("Projection du score final")
        st.write(f"**{home} : {result['home_mean']:.0f} points** | **{away} : {result['away_mean']:.0f} points**")
        st.write(f"Total médian : **{result['total_median']:.0f} points**")
        st.write(f"Intervalle exploratoire 10e–90e percentile : **{result['total_p10']:.0f} à {result['total_p90']:.0f}**")
        st.subheader("Lecture statistique")
        st.write(result["notes"])
        st.caption(f"Compétition : {competition} · Simulations exécutées : {sims:,} · Aucune cote bookmaker intégrée.")
