# BPI V1.0 — prototype basketball mi-temps

## Fonctionnalités actuelles
- Interface Streamlit en français pour saisir un match et ses statistiques à la mi-temps.
- Simulation Monte Carlo exploratoire du score final et de la deuxième mi-temps.
- Contrôles de cohérence sur les statistiques saisies.
- Historique des analyses dans la session Streamlit et export CSV téléchargeable.
- Schéma CSV pour constituer un jeu de données historique.

## Lancer
Python 3.10+ recommandé.

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Limites importantes
Le moteur actuel est un prototype à hypothèses simplifiées : il n'est pas entraîné sur des matchs historiques et ses probabilités ne sont pas calibrées. Les sorties ne constituent pas des prévisions fiables ni des conseils de pari. L'historique en mémoire de session n'est pas une base persistante : télécharge le CSV pour le conserver. Aucune API live n'est encore connectée.

Ne jamais utiliser les statistiques finales comme variables d'entrée d'une prédiction à la mi-temps : elles servent uniquement de cibles historiques.

## Feuille de route
1. Collecter des historiques horodatés et fiables NBA/EuroLeague avec données strictement disponibles à la pause.
2. Persister matchs, prédictions et résultats dans une base durable.
3. Construire une validation chronologique hors échantillon, sans fuite de données.
4. Entraîner des modèles de marge finale, total final et marchés de deuxième mi-temps.
5. Évaluer MAE/RMSE, Brier/Log Loss et calibration avant d'afficher des probabilités fiables.
6. Brancher une API live après vérification de la couverture, des coûts et des droits d'utilisation.

## Dépendances et secrets
Les dépendances sont déclarées dans `requirements.txt`. Les clés API, lorsqu'elles seront nécessaires, devront être ajoutées aux Secrets de l'hébergeur et jamais commitées dans GitHub.
