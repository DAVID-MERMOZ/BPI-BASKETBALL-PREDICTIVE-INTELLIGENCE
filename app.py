import csv
import io
from datetime import datetime, timezone

import streamlit as st
from bpi_validation import validate_halftime_data
from engine import simulate_second_half
# Import du module sans importer directement une fonction récente :
# cela évite un ImportError si Streamlit Cloud charge temporairement un ancien
# fichier bpi_live_data.py pendant le redéploiement.
import bpi_live_data as live_data
find_live_match = live_data.find_live_match
_extract_first_half_inputs_legacy = live_data.extract_first_half_inputs


def render_simple_table(rows):
    """Affiche une liste de dictionnaires sans bibliothèque tabulaire externe."""
    if not rows:
        st.info("Aucune donnée à afficher.")
        return
    columns = list(rows[0].keys())
    def cell(value):
        text = "" if value is None else str(value)
        return text.replace("|", "\\|").replace("\\n", " ")
    header = "| " + " | ".join(cell(col) for col in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(cell(row.get(col)) for col in columns) + " |" for row in rows]
    st.markdown("\n".join([header, separator] + body))

def extract_first_half_inputs(periods, allow_all_period=False):
    """Compatibilité entre versions du connecteur pendant les redéploiements."""
    try:
        return _extract_first_half_inputs_legacy(periods, allow_all_period=allow_all_period)
    except TypeError as exc:
        if "allow_all_period" not in str(exc):
            raise
        # Ancien connecteur : convertir le cumul 'all' en une seule période
        # logique, avec une deuxième période vide pour éviter de doubler les valeurs.
        aggregate = next((p for p in (periods or []) if p.get("period") == "all"), None)
        if not (allow_all_period and aggregate):
            return _extract_first_half_inputs_legacy(periods)
        compatible_periods = [
            {"period": "period1", "groups": aggregate.get("groups") or []},
            {"period": "period2", "groups": []},
        ]
        return _extract_first_half_inputs_legacy(compatible_periods)

current_score = live_data.current_score
is_halftime = live_data.is_halftime
LiveDataError = live_data.LiveDataError

def get_match_statistics_diagnostic(fixture_id, api_key):
    if hasattr(live_data, "get_match_statistics_diagnostic"):
        return live_data.get_match_statistics_diagnostic(fixture_id, api_key)
    # Compatibilité avec une ancienne version du connecteur.
    periods = live_data.get_match_statistics(fixture_id, api_key)
    return {
        "periods": periods,
        "diagnostic": {
            "top_level_keys": ["compatibilite_ancienne_version"],
            "data_keys": [],
            "periods_type": "list",
            "period_names": [
                str(p.get("period", "inconnu"))
                for p in periods if isinstance(p, dict)
            ],
        },
    }

# Compatibilité avec une ancienne copie du module parfois conservée au déploiement.
# La fonction est normalement exportée par bpi_live_data.py ; ce repli évite
# que l'application entière plante si Streamlit charge une version antérieure.
def get_live_matches(api_key):
    if hasattr(live_data, "get_live_matches"):
        return live_data.get_live_matches(api_key)
    payload = live_data._get("/livescores", api_key, {"sport": "basketball"})
    data = payload.get("data") or []
    if not isinstance(data, list):
        raise LiveDataError("Format inattendu du tableau LIVE : la propriété data n'est pas une liste.")
    return data
from bpi_storage import init_db, save_prediction, list_predictions, record_final_score, export_database_bytes

st.set_page_config(page_title="BPI V1.0", page_icon="🏀", layout="wide")
st.title("🏀 BPI V1.0 — Basketball Predictive Intelligence")
st.caption("Prototype expérimental — aucune prédiction fiable sans données réelles et vérifiées.")
st.info("La collecte LIVE remplit automatiquement les champs lorsque le fournisseur publie toutes les statistiques requises. Les données manquantes ne sont jamais remplacées par des zéros.")

init_db()
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
st.caption("Commence par charger le tableau des matchs LIVE. Tu pourras sélectionner directement une rencontre, sans dépendre de la correspondance exacte des noms.")
if st.button("Afficher les matchs de basketball en direct"):
    try:
        api_key = st.secrets.get("DATASPORTSAPI_API_KEY", "")
        if not api_key:
            st.error("Clé API absente. Ajoute DATASPORTSAPI_API_KEY dans les Secrets Streamlit.")
        else:
            st.session_state["bpi_live_list"] = get_live_matches(api_key)
            st.success(f"{len(st.session_state['bpi_live_list'])} match(s) LIVE renvoyé(s) par le fournisseur.")
    except LiveDataError as exc:
        st.error(str(exc))

live_list = st.session_state.get("bpi_live_list") or []
selected_live = None
if live_list:
    live_options = {}
    for game in live_list:
        hn = (game.get("home") or {}).get("name") or "Domicile inconnu"
        an = (game.get("away") or {}).get("name") or "Extérieur inconnu"
        league = (game.get("league") or {}).get("name") or "Compétition inconnue"
        label = f"{hn} vs {an} — {league} — ID {game.get('id')}"
        live_options[label] = game
    selected_label = st.selectbox("Sélectionne le match à collecter", list(live_options.keys()))
    selected_live = live_options[selected_label]
    # La sélection LIVE fournit elle-même les noms : aucune saisie manuelle requise.
    selected_home_name = (selected_live.get("home") or {}).get("name")
    selected_away_name = (selected_live.get("away") or {}).get("name")
    if selected_home_name and selected_away_name:
        home, away = selected_home_name, selected_away_name

if st.button("Collecter et remplir automatiquement", type="secondary"):
    try:
        api_key = st.secrets.get("DATASPORTSAPI_API_KEY", "")
        if not api_key:
            st.error("Clé API absente. Ajoute DATASPORTSAPI_API_KEY dans les Secrets Streamlit.")
        elif selected_live is None and (not home.strip() or not away.strip()):
            st.error("Sélectionne un match LIVE ou renseigne manuellement les deux équipes.")
        else:
            live_match = selected_live if selected_live is not None else find_live_match(home, away, api_key)
            collection = get_match_statistics_diagnostic(live_match["id"], api_key)
            periods = collection["periods"]
            st.session_state["bpi_live_match"] = live_match
            st.session_state["bpi_live_periods"] = periods
            st.session_state["bpi_live_diagnostic"] = collection["diagnostic"]
            halftime_confirmed = is_halftime(live_match)
            if not halftime_confirmed:
                st.session_state["bpi_live_match"] = live_match
                st.session_state["bpi_live_periods"] = periods
                st.warning("Match identifié, mais le statut du fournisseur ne confirme pas la mi-temps. Aucun score ni statistique ne sera prérempli pour éviter d'utiliser des données en cours.")
            else:
                first_half = extract_first_half_inputs(periods, allow_all_period=True)
                # Repère les statistiques optionnelles absentes afin de l'indiquer clairement.
                source_periods = periods
                if not all(any(p.get("period") == key for p in periods) for key in ("period1", "period2")):
                    source_periods = [p for p in periods if p.get("period") == "all"]
                available_keys = {
                    item.get("key")
                    for period in source_periods
                    for group in (period.get("groups") or [])
                    for item in (group.get("items") or [])
                }
                missing_optional = []
                for metric, aliases in {
                    "pertes de balle": {"turnovers", "turnover"},
                    "rebonds offensifs": {"offensiveRebounds", "offensive_rebounds", "offensive rebounds"},
                }.items():
                    if not available_keys.intersection(aliases):
                        missing_optional.append(metric)
                st.session_state["bpi_live_missing_optional"] = missing_optional
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

# Diagnostic visible directement, sans menu déroulant.
if st.session_state.get("bpi_live_match"):
    match = st.session_state["bpi_live_match"]
    st.markdown("### Résultat de la collecte LIVE")
    st.write(f"**{match.get('home', {}).get('name')}** — **{match.get('away', {}).get('name')}**")
    st.caption(f"Compétition : {(match.get('league') or {}).get('name', 'indisponible')} · Statut : {(match.get('status') or {}).get('description', 'indisponible')} · ID fournisseur : {match.get('id')}")
    periods = st.session_state.get("bpi_live_periods") or []
    diagnostic = st.session_state.get("bpi_live_diagnostic") or {}
    if st.session_state.get("bpi_data_filled"):
        st.success("Préremplissage effectué à partir des statistiques disponibles à la mi-temps.")
        missing_optional = st.session_state.get("bpi_live_missing_optional") or []
        if missing_optional:
            st.warning("Le fournisseur ne transmet pas : " + ", ".join(missing_optional) + ". Le moteur utilise une approximation neutre pour ces variables; la fiabilité de l'estimation est réduite. Vérifie les données avant toute analyse.")
    elif not periods:
        st.warning("Aucune statistique par période n'a été reçue. Le fournisseur n'a peut-être pas encore publié les statistiques de ce match.")
    else:
        st.info("Des périodes ont été reçues, mais le préremplissage automatique n'a pas été confirmé.")
    st.markdown("**Diagnostic technique — informations à communiquer**")
    st.write(f"- Nombre de périodes reçues : {len(periods)}")
    st.write("- Périodes détectées : " + (", ".join(diagnostic.get("period_names", [])) or "aucune"))
    st.write("- Clés de la réponse : " + (", ".join(diagnostic.get("top_level_keys", [])) or "indisponibles"))
    st.write("- Clés de l'objet data : " + (", ".join(diagnostic.get("data_keys", [])) or "aucune"))
    st.write("- Type du champ periods : " + str(diagnostic.get("periods_type", "diagnostic indisponible")))
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
            render_simple_table(rows)

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
        quality_errors, quality_warnings = validate_halftime_data(home_ht, away_ht, h, a)
        if quality_errors:
            for message in quality_errors:
                st.error(message)
            st.stop()
        if quality_warnings:
            for message in quality_warnings:
                st.warning(message)
            if not data_verified:
                st.error("Analyse suspendue : confirme explicitement les écarts signalés après vérification auprès de la source.")
                st.stop()
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
        prediction_record = {
            "horodatage_utc": datetime.now(timezone.utc).isoformat(),
            "date_match": str(game_date), "competition": competition,
            "domicile": home, "exterieur": away,
            "score_pause_domicile": home_ht, "score_pause_exterieur": away_ht,
            "statistiques_mi_temps_domicile": h,
            "statistiques_mi_temps_exterieur": a,
            "source_donnees": "DataSportsAPI_LIVE" if st.session_state.get("bpi_data_filled", False) else "saisie_manuelle_verifiee",
            "qualite_donnees_avertissements": quality_warnings,
            "simulations": sims, "proba_victoire_domicile_pct": round(home_win, 2) if home_win is not None else None,
            "proba_victoire_exterieur_pct": round(away_win, 2) if away_win is not None else None,
            "score_final_moyen_domicile": round(home_mean, 2),
            "score_final_moyen_exterieur": round(away_mean, 2),
            "total_moyen": round(total_mean, 2),
            "total_p10": round(total_p10, 2) if total_p10 is not None else None, "total_p90": round(total_p90, 2) if total_p90 is not None else None,
            "statut_modele": "prototype_non_calibre"
        }
        prediction_id = save_prediction(prediction_record)
        prediction_record["id_stockage"] = prediction_id
        st.session_state.prediction_history.append(prediction_record)
        st.success(f"Analyse enregistrée dans la base locale BPI (ID {prediction_id}).")
        st.caption("Les hypothèses restent simplifiées : pas de fautes d'équipe, rotations, blessures, play-by-play ni ajustements tactiques.")

st.divider()
st.subheader("Base historique BPI")
st.caption("Les analyses sont enregistrées dans SQLite. Sur Streamlit Cloud, le disque local peut être réinitialisé lors d'un redémarrage ou redéploiement : télécharge régulièrement une sauvegarde.")
stored = list_predictions()
if stored:
    display_rows = []
    for row in stored:
        display_rows.append({
            "ID": row["id"], "Date": row["game_date"], "Compétition": row["competition"],
            "Domicile": row["home_team"], "Extérieur": row["away_team"],
            "Pause": str(row["halftime_home"]) + "-" + str(row["halftime_away"]),
            "Score final": (str(row["final_home"]) + "-" + str(row["final_away"]) if row["final_home"] is not None else "À saisir")
        })
    render_simple_table(display_rows)
    pending = [row for row in stored if row["final_home"] is None]
    if pending:
        st.markdown("**Enregistrer le résultat final d'un match terminé**")
        options = {"ID " + str(r["id"]) + " — " + r["home_team"] + " vs " + r["away_team"] + " (" + str(r["game_date"]) + ")": r for r in pending}
        selected_label = st.selectbox("Analyse concernée", list(options.keys()))
        selected = options[selected_label]
        rc1, rc2 = st.columns(2)
        with rc1:
            final_home = st.number_input("Score final — " + selected["home_team"], min_value=0, max_value=250, value=0, key="db_final_home")
        with rc2:
            final_away = st.number_input("Score final — " + selected["away_team"], min_value=0, max_value=250, value=0, key="db_final_away")
        if st.button("Enregistrer le score final"):
            if final_home == 0 and final_away == 0:
                st.error("Saisis le score final réel.")
            elif record_final_score(selected["id"], final_home, final_away):
                st.success("Résultat final enregistré comme cible historique, jamais comme variable d'entrée à la mi-temps.")
                st.rerun()
    db_bytes = export_database_bytes()
    st.download_button("Télécharger la sauvegarde complète SQLite", data=db_bytes, file_name="bpi_history.sqlite3", mime="application/vnd.sqlite3")
else:
    st.info("La base est prête, mais aucune prédiction n'y est encore enregistrée.")

st.subheader("Historique des analyses de cette session")
if st.session_state.prediction_history:
    history = st.session_state.prediction_history
    render_simple_table(history)
    output = io.StringIO()
    fieldnames = list(history[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(history)
    csv_bytes = output.getvalue().encode("utf-8-sig")
    st.download_button("Télécharger l'historique CSV", data=csv_bytes, file_name="bpi_historique_predictions.csv", mime="text/csv")
else:
    st.info("Aucune analyse enregistrée dans cette session. L'historique sera perdu à la fermeture de la session si tu ne télécharges pas le CSV.")
