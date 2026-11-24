# BPI Worker — déploiement Beacon

Ce Worker surveille les matchs de basketball à la mi-temps, simule une projection exploratoire et envoie une alerte Telegram. Le moteur n'est ni entraîné ni calibré : les pourcentages ne sont pas des probabilités fiables et ne constituent pas des conseils de pari.

## Architecture gratuite visée

- **Beacon Workers Free** : exécution JavaScript et déclenchement Cron (si la capacité Cron est activée pour la plateforme).
- **Upstash Redis Free** : stockage persistant de déduplication via REST. Le code utilise une réservation atomique `SET NX EX` avant l'envoi Telegram afin d'éviter les doublons concurrents.
- **DataSportsAPI** : source de matchs et statistiques.
- **Telegram Bot API** : livraison des alertes.

Le plan gratuit Beacon ne fournit pas de base D1, KV ou Durable Objects. Upstash est donc utilisé pour conserver l'état sans payer Beacon Plus. Upstash Free annonce 1 base, 250 MB et 500 000 commandes/mois; les limites peuvent évoluer.

## Secrets à configurer dans Beacon

- `DATASPORTSAPI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`

Ne jamais inscrire ces valeurs dans le dépôt GitHub, un fichier public ou une conversation.

## Déclenchement

Le fichier `.beacon/config.json` déclare un Cron toutes les 5 minutes en UTC. Le déploiement Cron ne fonctionnera que si Beacon indique `crons: true` dans `GET /v1/capabilities`. Sinon, ne pas prétendre que la surveillance automatique est active : il faudra choisir un planificateur HTTP externe compatible.

## Limites et tests obligatoires

1. Vérifier la disponibilité réelle des Cron Beacon avant déploiement.
2. Vérifier que le compte DataSportsAPI autorise le volume de requêtes envisagé.
3. Tester Upstash REST et l'opération atomique de déduplication.
4. Tester l'envoi Telegram sur un match de test contrôlé.
5. Vérifier les logs d'exécution et le comportement sur données incomplètes.
6. Vérifier les quotas Beacon et Upstash.

Le Worker ne doit pas être déclaré opérationnel avant ces tests.
