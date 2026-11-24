# Déploiement BPI sur Cloudflare Workers (offre gratuite)

Ce Worker remplace l'exécution périodique GitHub Actions pour la surveillance LIVE.
Le dépôt GitHub reste privé. Aucun secret n'est stocké dans le code.

## Prérequis
- Compte Cloudflare Workers Free.
- Les trois valeurs déjà détenues par l'utilisateur : `DATASPORTSAPI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- Un namespace Cloudflare Workers KV.

## Configuration dans le tableau de bord Cloudflare
1. Ouvrir Workers & Pages et créer un Worker nommé `bpi-live-monitor`.
2. Coller le contenu de `cloudflare-worker/worker.js` dans l'éditeur, puis déployer.
3. Dans Settings > Bindings, ajouter un binding **KV namespace** :
   - Variable name : `BPI_STATE`
   - KV namespace : créer `BPI_STATE` (ou sélectionner ce namespace).
4. Dans Settings > Variables and Secrets, ajouter les trois secrets (type Secret) :
   - `DATASPORTSAPI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. Dans Settings > Triggers > Cron Triggers, ajouter `*/5 * * * *` (toutes les 5 minutes, UTC).
6. Redéployer si Cloudflare le demande.

## Limites et prudence
- Le plan Workers Free documente 100 000 requêtes/jour, 5 Cron Triggers par compte et 10 ms de CPU par invocation Cron. Ce Worker utilise une simulation réduite à 1 200 tirages pour respecter le budget CPU; il faut vérifier les journaux d'exécution réels.
- Le fournisseur DataSportsAPI peut imposer ses propres quotas. Un cycle toutes les 5 minutes représente jusqu'à 288 appels de liste LIVE par jour, plus un appel statistiques par match à la mi-temps. Vérifier le quota de l'abonnement API.
- KV sert à éviter les alertes répétées pour le même identifiant de match. L'état expire après 14 jours.
- Ce prototype ne garantit ni la détection de toutes les mi-temps (le statut fournisseur doit correspondre aux libellés reconnus), ni l'exhaustivité des statistiques.
- Les résultats restent exploratoires, non entraînés et non calibrés. Aucune recommandation de pari ou de mise.
- Aucun moyen de paiement n'est requis par les quotas gratuits publiés, mais Cloudflare peut demander une vérification selon le pays, le compte ou les règles anti-abus. Ne pas activer de plan payant.
