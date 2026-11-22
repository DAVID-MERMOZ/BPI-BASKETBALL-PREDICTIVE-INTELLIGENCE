# BPI V1.0 — prototype basketball mi-temps

## Première version
- Interface Streamlit en français pour saisir un match et ses statistiques à la mi-temps.
- Simulation Monte Carlo exploratoire de la deuxième mi-temps.
- Schéma CSV pour construire un historique de matchs.
- Emplacements pour les clés API (aucune clé secrète ne doit être commitée).

## Lancer en local
Python 3.10+ recommandé.

```bash
python -m venv .venv
# Windows : .venv\\Scripts\\activate
# macOS/Linux : source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## État et limites
Cette livraison est un **prototype fonctionnel**, pas un modèle ML entraîné ni un système de prédiction calibré. Les sorties sont exploratoires et ne garantissent aucun résultat. Aucune API live n'est encore branchée : les matchs sont saisis manuellement. Le prototype ne doit pas être utilisé comme fondement autonome d'une décision de pari.

Ne jamais utiliser les statistiques finales comme variables d'entrée d'une prédiction à la mi-temps : elles servent uniquement de cibles historiques.

## Feuille de route
1. Vérifier la couverture NBA/EuroLeague et les conditions des fournisseurs de données.
2. Constituer un historique avec statistiques disponibles à la pause et résultats finaux.
3. Construire une validation chronologique hors échantillon, sans fuite de données.
4. Entraîner des modèles de marge finale et de total final.
5. Évaluer MAE/RMSE, Brier/Log Loss et calibration avant d'afficher des probabilités fiables.
6. Ajouter le flux live, la persistance des matchs et les contrôles de qualité.

## Fournisseurs à évaluer
- Sportradar : données live et play-by-play, accès soumis à abonnement et droits.
- Basketball API : couverture multi-compétitions à vérifier avant toute dépendance.
