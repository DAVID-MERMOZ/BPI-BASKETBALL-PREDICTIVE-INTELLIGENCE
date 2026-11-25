# Déploiement BPI sur Google Apps Script

Cette version remplace le déclencheur Cloudflare pour la surveillance automatique. Le script tourne sur l'infrastructure Google, indépendamment du téléphone. Il ne nécessite ni Wrangler ni serveur personnel.

## 1. Créer le projet Apps Script

1. Ouvrir https://script.google.com/home/start avec le compte Google qui hébergera BPI.
2. Créer un projet et le nommer `BPI Halftime Monitor`.
3. Ouvrir le fichier `Code.gs`, supprimer son contenu et y coller le contenu de [google-apps-script/Code.gs](Code.gs).
4. Enregistrer.

## 2. Ajouter les secrets (ne jamais les mettre dans le code)

Dans Apps Script : **Paramètres du projet** (icône engrenage) > **Propriétés du script** > **Ajouter une propriété de script**.

Ajouter ces trois noms exactement, avec les valeurs provenant des comptes du propriétaire :

- `DATASPORTSAPI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Ne pas coller ces valeurs dans GitHub, dans un message ou dans un journal.

## 3. Vérifier la configuration et Telegram

1. Dans la liste des fonctions en haut, choisir `checkBpiConfiguration`, puis cliquer **Exécuter**.
2. Accepter les autorisations Google demandées.
3. Ouvrir le journal d'exécution : les trois propriétés doivent apparaître comme CONFIGURÉES, sans afficher leurs valeurs.
4. Choisir `testBpiTelegram` et cliquer **Exécuter**.
5. Vérifier la réception du message de test dans le chat Telegram ciblé.

Ne pas installer le déclencheur tant que le test Telegram n'est pas reçu.

## 4. Vérifier la collecte LIVE

Exécuter `testBpiLiveScan`. Le journal donne le nombre de matchs LIVE et ceux dont le statut fournisseur indique explicitement la mi-temps. Un match au premier quart-temps ou au troisième quart-temps ne doit pas déclencher d'alerte.

## 5. Activer la surveillance automatique

Après réception du test Telegram et vérification des secrets :

1. Choisir `installBpiFiveMinuteTrigger`.
2. Cliquer **Exécuter** et accepter les autorisations si Google les demande.
3. Dans la barre latérale **Déclencheurs** (icône horloge), vérifier qu'un déclencheur de `monitorBpiHalftime` est présent et planifié toutes les 5 minutes.

Le déclencheur peut démarrer avec quelques minutes de décalage. Apps Script n'est pas un système temps réel : les heures d'exécution peuvent varier.

## Fonctionnement et limites

- Le scanner consulte DataSportsAPI pour les matchs de basketball LIVE toutes les cinq minutes.
- Seuls les statuts textuels explicitement reconnus comme mi-temps sont traités.
- Le script récupère les statistiques du match, exige les statistiques essentielles et vérifie leur cohérence.
- Une simulation Monte Carlo exploratoire de 1 200 itérations est envoyée sur Telegram.
- Les identifiants de matchs déjà notifiés sont conservés dans les propriétés du script pour éviter les doublons pendant 14 jours.
- Un verrou empêche deux exécutions de surveillance simultanées.
- Les matchs sans statistiques suffisantes sont ignorés; aucun chiffre manquant n'est inventé.
- Le moteur est non entraîné et non calibré. Les pourcentages ne sont pas des probabilités fiables ni des conseils de pari.
- La couverture dépend des compétitions et des statuts réellement fournis par DataSportsAPI.
- Les déclencheurs Google dépendent des quotas et des limites du compte Apps Script. Vérifier le tableau **Exécutions** en cas d'échec.

## Fonctions disponibles

- `checkBpiConfiguration` : présence des trois secrets, sans en afficher les valeurs.
- `testBpiTelegram` : envoie un message de test, sans prédiction.
- `testBpiLiveScan` : diagnostic ponctuel des matchs LIVE et statuts mi-temps.
- `installBpiFiveMinuteTrigger` : installe un unique déclencheur toutes les cinq minutes.
- `monitorBpiHalftime` : exécution du scanner.

Le déploiement n'est considéré opérationnel qu'après réception du message Telegram de test, confirmation du déclencheur et observation d'une alerte issue d'une véritable mi-temps.
