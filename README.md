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

## Tester
Depuis la racine du dépôt :

```bash
python -m unittest discover -s tests -v
```

## Diagnostic réel DataSportsAPI (basketball LIVE)
Le script interactif interroge le fournisseur avec ta clé saisie masquée, liste les matchs LIVE, puis permet de sélectionner un ID. Il affiche les périodes et les clés statistiques reçues, et vérifie si le parseur BPI accepte les données Q1+Q2. La clé n'est pas affichée ni écrite dans un fichier.

```bash
python scripts/diagnose_datasportsapi_basketball.py
```

Le diagnostic exige une clé DataSportsAPI valide et un match LIVE avec statistiques disponibles. Un refus du parseur signifie que les données reçues sont insuffisantes pour une prédiction sûre; ne contourne pas ce refus en inventant des valeurs.

## Tester une simulation manuellement
La signature de `simulate_second_half` est :

```python
simulate_second_half(home_ht, away_ht, home_stats, away_stats, n=10000, seed=None)
```

Les deux scores à la mi-temps sont donc les deux premiers arguments, puis viennent les dictionnaires de statistiques domicile et extérieur. Exemple :

```bash
python -c "from engine import simulate_second_half; print(simulate_second_half(45,42,{'fga':40,'fgm':18,'3pa':15,'3pm':5,'fta':8,'ftm':6,'tov':7,'orb':4},{'fga':38,'fgm':16,'3pa':14,'3pm':4,'fta':10,'ftm':8,'tov':9,'orb':5},n=10000,seed=42))"
```

## Limites importantes
Le moteur actuel est un prototype à hypothèses simplifiées : il n'est pas entraîné sur des matchs historiques et ses probabilités ne sont pas calibrées. Les sorties ne constituent pas des prévisions fiables ni des conseils de pari. L'historique en mémoire de session n'est pas une base persistante : télécharge le CSV pour le conserver. Un connecteur LIVE DataSportsAPI est présent pour rechercher les matchs en cours et récupérer les statistiques disponibles. Sa couverture dépend de la compétition et du fournisseur; chaque réponse doit être vérifiée en conditions réelles.

Ne jamais utiliser les statistiques finales comme variables d'entrée d'une prédiction à la mi-temps : elles servent uniquement de cibles historiques.

## Objectif de couverture : basketball multi-compétitions
BPI vise les matchs de basketball de toutes les compétitions couvertes par des données fiables, et non un modèle limité à la NBA, à l'EuroLeague ou à un championnat unique. Le champ `competition` du jeu de données sert à identifier le contexte de chaque match.

La stratégie cible est un modèle global multi-compétitions, avec prise en compte des différences de ligue, saison, format et niveau de jeu. Lorsque le volume de données le permet, des ajustements hiérarchiques ou spécifiques aux compétitions pourront corriger les écarts de rythme et d'efficacité sans entraîner un modèle isolé pour chaque championnat. Une compétition peu représentée ne sera pas déclarée calibrée sur la seule base des résultats d'autres ligues.

## Feuille de route
1. Collecter des historiques fiables de nombreuses compétitions et saisons, avec les seules variables réellement disponibles à la mi-temps; enregistrer la compétition, le format, la source et les métadonnées nécessaires à la comparabilité. Le schéma est défini dans `data/halftime_training_schema.csv`.
2. Vérifier la comparabilité des règles et formats (durée des périodes, prolongations, compétitions masculines/féminines, niveaux) et séparer les cas incompatibles si nécessaire.
3. Persister matchs, prédictions horodatées et résultats dans une base durable.
4. Construire une validation chronologique hors échantillon, globale et ventilée par compétition, saison et niveau de couverture, sans fuite de données.
5. Entraîner un modèle global multi-compétitions et tester des ajustements hiérarchiques par compétition lorsque les données sont suffisantes.
6. Évaluer MAE/RMSE, Brier/Log Loss, calibration globale et calibration par compétition; surveiller les compétitions peu représentées et refuser d'afficher des probabilités fiables lorsque les données sont insuffisantes.
7. Étendre la collecte LIVE aux compétitions effectivement prises en charge par le fournisseur, après vérification de la couverture, des coûts et des droits d'utilisation.

## Dépendances et secrets
Les dépendances sont déclarées dans `requirements.txt`. Les clés API, lorsqu'elles seront nécessaires, devront être ajoutées aux Secrets de l'hébergeur et jamais commitées dans GitHub.
