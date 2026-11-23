# Données historiques BPI — schéma multi-compétitions

Le fichier `halftime_training_schema.csv` définit une ligne par match terminé. Les colonnes de statistiques `*_ht` décrivent uniquement les informations connues à la mi-temps. Les colonnes `*_final_points` sont des cibles de résultat et ne doivent jamais entrer dans les variables explicatives d'une prédiction à la mi-temps.

## Métadonnées indispensables
- `provider` et `provider_game_id` : traçabilité de la source et dédoublonnage.
- `competition`, `competition_country`, `season` : contexte de compétition.
- `period_format` et `period_minutes` : distinguer les formats (quatre quart-temps, deux mi-temps, etc.). Ne pas mélanger sans contrôle les formats incompatibles.
- `gender_category` et `competition_level` : documenter les différences de catégorie et de niveau lorsque connues.
- `overtime_periods` : nombre de prolongations jouées; zéro si aucune, vide si inconnu.
- `home_regulation_points` et `away_regulation_points` : score à la fin du temps réglementaire si la source le fournit. Les scores `*_final_points` incluent les prolongations lorsqu'elles ont eu lieu.
- `data_quality_status` : statut de contrôle, par exemple `verified`, `partial`, `rejected`. Seules les lignes vérifiées doivent alimenter l'entraînement.
- `source_last_updated_utc` : horodatage de dernière mise à jour connue de la source.

## Règles anti-fuite
1. Les variables `*_final_points`, `*_regulation_points` et `overtime_periods` sont des résultats ou métadonnées postérieures à la mi-temps; elles ne sont jamais des entrées d'un modèle pré-match/mi-temps.
2. Pour une prédiction à la mi-temps, utiliser uniquement les scores et statistiques effectivement disponibles à cet instant.
3. Séparer entraînement et test chronologiquement par date, jamais par tirage aléatoire simple.
4. Dédupliquer avec la source et l'identifiant du match; conserver la provenance.
5. Ne pas déclarer une compétition calibrée si son échantillon indépendant est insuffisant.

Le schéma ne signifie pas que ces données sont déjà collectées. Il prépare une collecte cohérente sur plusieurs compétitions et saisons.