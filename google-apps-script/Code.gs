/**
 * BPI — surveillance basketball à la mi-temps via Google Apps Script.
 * Exécution prévue toutes les 5 minutes par déclencheur temporel.
 * Prototype Monte Carlo exploratoire, non entraîné et non calibré.
 *
 * Secrets à définir dans Paramètres du projet > Propriétés du script :
 * DATASPORTSAPI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
 */

const BPI_API_BASE = "https://api.datasportsapi.com/v2";
const BPI_DEDUPE_DAYS = 14;
const BPI_PENDING_MINUTES = 20;
const BPI_LOCK_WAIT_MS = 1000;

function bpiGetSecret_(name) {
  const value = PropertiesService.getScriptProperties().getProperty(name);
  if (!value) throw new Error("Propriété de script manquante : " + name);
  return value.trim();
}

function bpiFetchJson_(url, headers) {
  const response = UrlFetchApp.fetch(url, {
    method: "get",
    headers: headers || {},
    muteHttpExceptions: true
  });
  const status = response.getResponseCode();
  const body = response.getContentText();
  if (status < 200 || status >= 300) {
    throw new Error("HTTP " + status + " pour " + url + " — " + body.slice(0, 300));
  }
  let parsed;
  try { parsed = JSON.parse(body); }
  catch (e) { throw new Error("Réponse JSON invalide pour " + url); }
  return parsed;
}

function bpiApi_(path, apiKey) {
  return bpiFetchJson_(BPI_API_BASE + path, { Authorization: "Bearer " + apiKey });
}

function bpiText_(value) {
  if (value == null) return "";
  if (typeof value === "object") return value.name || value.shortName || value.displayName || "";
  return String(value);
}

function bpiIsHalftime_(match) {
  const status = match.status || {};
  const label = [status.description, status.shortName, status.type]
    .filter(Boolean).join(" ").toLowerCase();
  return ["half time", "half-time", "halftime", "half break", "interval"]
    .some(function(term) { return label.indexOf(term) !== -1; });
}

function bpiFixtureId_(match) {
  return match.id != null ? match.id :
    (match.fixtureId != null ? match.fixtureId : match.fixture_id);
}

function bpiScore_(match) {
  const home = Number(match.homeScore && match.homeScore.current);
  const away = Number(match.awayScore && match.awayScore.current);
  if (!Number.isInteger(home) || !Number.isInteger(away) || home < 0 || away < 0) {
    throw new Error("Score de mi-temps absent ou invalide.");
  }
  return [home, away];
}

function bpiPeriodValues_(period) {
  const output = {};
  (period.groups || []).forEach(function(group) {
    (group.items || []).forEach(function(item) {
      if (item.key) output[item.key] = item;
    });
  });
  return output;
}

function bpiExtractStats_(periods) {
  const byPeriod = {};
  (periods || []).forEach(function(period) { byPeriod[period.period] = period; });
  let selected = [byPeriod.period1, byPeriod.period2];
  if (!selected.every(Boolean) && byPeriod.all) selected = [byPeriod.all];
  if (!selected.every(Boolean)) throw new Error("Statistiques Q1+Q2 indisponibles.");

  const aliases = {
    fga: "fieldGoalsAttempted", fgm: "fieldGoalsMade",
    "3pa": "threePointersAttempted", "3pm": "threePointersMade",
    tov: "turnovers", orb: "offensiveRebounds",
    ftm: "freeThrowsMade", fta: "freeThrowsAttempted"
  };
  const fallback = { fga: "fieldGoalsMade", "3pa": "threePointersMade", fta: "freeThrowsMade" };
  const result = {};

  ["home", "away"].forEach(function(side) {
    result[side] = {};
    Object.keys(aliases).forEach(function(target) {
      let sum = 0, found = false;
      selected.forEach(function(period) {
        const values = bpiPeriodValues_(period);
        const item = values[aliases[target]];
        let value = item && item[side] ? item[side].value : null;
        if (value == null && fallback[target]) {
          const made = values[fallback[target]];
          value = made && made[side] ? made[side].total : null;
        }
        if (value != null && isFinite(Number(value))) {
          sum += Math.round(Number(value));
          found = true;
        }
      });
      result[side][target] = found ? sum : null;
    });

    ["fga", "fgm", "3pa", "3pm", "ftm", "fta"].forEach(function(key) {
      if (result[side][key] == null) throw new Error("Statistique essentielle absente : " + side + "." + key);
    });
    ["tov", "orb"].forEach(function(key) {
      if (result[side][key] == null) result[side][key] = 0;
    });

    const stats = result[side];
    Object.keys(stats).forEach(function(key) {
      if (!Number.isInteger(stats[key]) || stats[key] < 0) {
        throw new Error("Statistique invalide : " + side + "." + key);
      }
    });
    if (stats.fgm > stats.fga || stats["3pm"] > stats["3pa"] ||
        stats["3pa"] > stats.fga || stats["3pm"] > stats.fgm ||
        stats.ftm > stats.fta) {
      throw new Error("Incohérence mathématique des statistiques : " + side);
    }
  });
  return result;
}

function bpiNormal_(randomFn) {
  const u = Math.max(randomFn(), 1e-12);
  const v = randomFn();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function bpiPoisson_(lambda, randomFn) {
  const limit = Math.exp(-lambda);
  let k = 0, product = 1;
  do { k++; product *= randomFn(); } while (product > limit);
  return k - 1;
}

function bpiPercentile_(sorted, p) {
  const position = (sorted.length - 1) * p;
  const lower = Math.floor(position), upper = Math.ceil(position);
  return lower === upper ? sorted[lower] :
    sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
}

function bpiSimulate_(homeScore, awayScore, homeStats, awayStats, iterations) {
  const randomFn = Math.random;
  const hp = Math.max(1, homeStats.fga - homeStats.orb + homeStats.tov + 0.44 * homeStats.fta);
  const ap = Math.max(1, awayStats.fga - awayStats.orb + awayStats.tov + 0.44 * awayStats.fta);
  const paceMean = Math.min(65, Math.max(25, (hp + ap) / 2));
  const homePpp = Math.min(1.65, Math.max(0.65, 0.55 * (homeScore / hp) + 0.45 * 1.05));
  const awayPpp = Math.min(1.65, Math.max(0.65, 0.55 * (awayScore / ap) + 0.45 * 1.05));

  let homeWins = 0, awayWins = 0, ties = 0, homeSum = 0, awaySum = 0;
  const totals = [];
  for (let i = 0; i < iterations; i++) {
    const pace = Math.min(72, Math.max(20, paceMean + 3.5 * bpiNormal_(randomFn)));
    const hEff = Math.min(1.75, Math.max(0.60, homePpp + 0.16 * bpiNormal_(randomFn)));
    const aEff = Math.min(1.75, Math.max(0.60, awayPpp + 0.16 * bpiNormal_(randomFn)));
    const hFinal = homeScore + bpiPoisson_(pace * hEff, randomFn);
    const aFinal = awayScore + bpiPoisson_(pace * aEff, randomFn);
    if (hFinal > aFinal) homeWins++;
    else if (aFinal > hFinal) awayWins++;
    else ties++;
    homeSum += hFinal;
    awaySum += aFinal;
    totals.push(hFinal + aFinal);
  }
  totals.sort(function(a, b) { return a - b; });
  return {
    homeWin: 100 * homeWins / iterations,
    awayWin: 100 * awayWins / iterations,
    tie: 100 * ties / iterations,
    homeMean: homeSum / iterations,
    awayMean: awaySum / iterations,
    totalMean: (homeSum + awaySum) / iterations,
    p10: bpiPercentile_(totals, 0.10),
    p90: bpiPercentile_(totals, 0.90)
  };
}

function bpiSendTelegram_(message) {
  const token = bpiGetSecret_("TELEGRAM_BOT_TOKEN");
  const chatId = bpiGetSecret_("TELEGRAM_CHAT_ID");
  const url = "https://api.telegram.org/bot" + token + "/sendMessage";
  const response = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({
      chat_id: chatId,
      text: message,
      disable_web_page_preview: true
    }),
    muteHttpExceptions: true
  });
  const status = response.getResponseCode();
  let body = {};
  try { body = JSON.parse(response.getContentText()); } catch (e) {}
  if (status < 200 || status >= 300 || !body.ok) {
    throw new Error("Échec de l'envoi Telegram (HTTP " + status + ").");
  }
}

function bpiBuildMessage_(match, homeScore, awayScore, stats, result) {
  const home = bpiText_(match.home) || "Domicile";
  const away = bpiText_(match.away) || "Extérieur";
  const competition = bpiText_(match.competition || match.tournament || match.league) || "Non précisée";
  const leader = result.homeMean > result.awayMean ? home :
    (result.awayMean > result.homeMean ? away : "Équilibre");
  return [
    "🏀 BPI — ALERTE MI-TEMPS",
    home + " " + homeScore + "–" + awayScore + " " + away,
    "Compétition : " + competition,
    "",
    "SIMULATION EXPLORATOIRE — NON CALIBRÉE",
    "Équipe projetée en tête : " + leader,
    "Victoire domicile simulée : " + result.homeWin.toFixed(1) + "%",
    "Victoire extérieur simulée : " + result.awayWin.toFixed(1) + "%",
    "Égalité simulée : " + result.tie.toFixed(1) + "%",
    "Score final moyen simulé : " + result.homeMean.toFixed(1) + "–" + result.awayMean.toFixed(1),
    "Total moyen simulé : " + result.totalMean.toFixed(1),
    "Intervalle central 80% du total : " + result.p10.toFixed(0) + "–" + result.p90.toFixed(0),
    "",
    "⚠️ Prototype non entraîné et non calibré : pourcentages non fiables. Aucune recommandation de pari ou de mise."
  ].join("\n");
}

/**
 * Fonction principale appelée par le déclencheur toutes les 5 minutes.
 * Le verrou empêche deux exécutions simultanées.
 */
function monitorBpiHalftime() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(BPI_LOCK_WAIT_MS)) {
    console.log("BPI : une autre exécution est déjà en cours.");
    return;
  }
  try {
    const apiKey = bpiGetSecret_("DATASPORTSAPI_API_KEY");
    const payload = bpiApi_("/livescores?sport=basketball", apiKey);
    const matches = Array.isArray(payload.data) ? payload.data : [];
    const properties = PropertiesService.getScriptProperties();
    const now = Date.now();
    let halftimeCount = 0, sentCount = 0, skippedCount = 0;

    matches.forEach(function(match) {
      if (!bpiIsHalftime_(match)) return;
      halftimeCount++;
      const id = bpiFixtureId_(match);
      if (id == null) { skippedCount++; return; }

      const key = "BPI_HALFTIME_" + String(id).replace(/[^a-zA-Z0-9_-]/g, "_");
      const existing = properties.getProperty(key);
      if (existing) {
        let state;
        try { state = JSON.parse(existing); } catch (e) { state = {}; }
        const age = state.updatedAt ? now - Number(state.updatedAt) : Infinity;
        if (state.status === "sent" && age < BPI_DEDUPE_DAYS * 86400000) return;
        if (state.status === "pending" && age < BPI_PENDING_MINUTES * 60000) return;
      }

      properties.setProperty(key, JSON.stringify({ status: "pending", updatedAt: now }));
      try {
        const scores = bpiScore_(match);
        const statsPayload = bpiApi_("/fixtures/" + encodeURIComponent(id) + "/statistics", apiKey);
        const stats = bpiExtractStats_(statsPayload.data && statsPayload.data.periods || []);
        const result = bpiSimulate_(scores[0], scores[1], stats.home, stats.away, 1200);
        const message = bpiBuildMessage_(match, scores[0], scores[1], stats, result);
        bpiSendTelegram_(message);
        properties.setProperty(key, JSON.stringify({ status: "sent", updatedAt: Date.now() }));
        sentCount++;
        console.log("BPI : notification Telegram envoyée pour le match " + id);
      } catch (error) {
        properties.deleteProperty(key);
        skippedCount++;
        console.error("BPI : match " + id + " ignoré — " + String(error));
      }
    });

    console.log(JSON.stringify({
      checkedAt: new Date().toISOString(),
      liveMatches: matches.length,
      halftimeMatches: halftimeCount,
      notificationsSent: sentCount,
      skipped: skippedCount
    }));
  } finally {
    lock.releaseLock();
  }
}

/** Crée ou répare le déclencheur de surveillance toutes les 5 minutes. */
function installBpiFiveMinuteTrigger() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(trigger) {
    if (trigger.getHandlerFunction() === "monitorBpiHalftime") {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  ScriptApp.newTrigger("monitorBpiHalftime").timeBased().everyMinutes(5).create();
  console.log("Déclencheur BPI installé : toutes les 5 minutes.");
}

/** Teste Telegram sans lancer de prédiction. */
function testBpiTelegram() {
  bpiSendTelegram_("✅ BPI — test de connexion Telegram réussi. Aucune prédiction n'a été exécutée.");
  console.log("Test Telegram envoyé.");
}

/** Vérifie la présence des trois secrets sans les afficher. */
function checkBpiConfiguration() {
  const names = ["DATASPORTSAPI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"];
  const props = PropertiesService.getScriptProperties();
  const report = names.map(function(name) {
    return name + " : " + (props.getProperty(name) ? "CONFIGURÉ" : "MANQUANT");
  });
  console.log(report.join("\n"));
  return report.join("\n");
}

/** Diagnostic manuel ponctuel : liste uniquement le nombre de matchs et ceux à la mi-temps. */
function testBpiLiveScan() {
  const key = bpiGetSecret_("DATASPORTSAPI_API_KEY");
  const payload = bpiApi_("/livescores?sport=basketball", key);
  const matches = Array.isArray(payload.data) ? payload.data : [];
  const halftime = matches.filter(bpiIsHalftime_);
  const report = "Matchs LIVE reçus : " + matches.length +
    "\nMatchs détectés à la mi-temps : " + halftime.length +
    "\n" + halftime.map(function(m) {
      const s = m.status || {};
      return String(bpiFixtureId_(m)) + " — " + bpiText_(m.home) + " vs " +
        bpiText_(m.away) + " — " + [s.description, s.shortName, s.type].filter(Boolean).join("/");
    }).join("\n");
  console.log(report);
  return report;
}
