/**
 * BPI Cloudflare Worker — surveillance basket à la mi-temps.
 * Déclenchement Cron: toutes les cinq minutes (UTC).
 * Prototype Monte Carlo exploratoire, non entraîné et non calibré.
 */
const API_BASE = "https://api.datasportsapi.com/v2";
const DEDUPE_TTL_SECONDS = 60 * 60 * 24 * 14;
const PENDING_TTL_SECONDS = 20 * 60;

function text(v) {
  if (v == null) return "";
  if (typeof v === "object") return v.name || v.shortName || v.displayName || "";
  return String(v);
}
function fixtureId(m) { return m.id ?? m.fixtureId ?? m.fixture_id ?? null; }
function isHalftime(m) {
  const s = m.status || {};
  const status = [s.description, s.shortName, s.type].filter(Boolean).join(" ").toLowerCase();
  return ["half time", "half-time", "halftime", "half break", "interval"].some(x => status.includes(x));
}
function score(m) {
  const h = Number(m.homeScore?.current);
  const a = Number(m.awayScore?.current);
  if (!Number.isInteger(h) || !Number.isInteger(a) || h < 0 || a < 0) throw new Error("Score courant incomplet.");
  return [h, a];
}
async function api(path, key, params = "") {
  const r = await fetch(API_BASE + path + params, {
    headers: { Authorization: "Bearer " + key },
    signal: AbortSignal.timeout(15000)
  });
  if (!r.ok) throw new Error("DataSportsAPI HTTP " + r.status);
  return await r.json();
}
function periodValues(period) {
  const out = {};
  for (const group of (period.groups || [])) {
    for (const item of (group.items || [])) if (item.key) out[item.key] = item;
  }
  return out;
}
function extractStats(periods) {
  const by = Object.fromEntries((periods || []).map(p => [p.period, p]));
  let selected = [by.period1, by.period2];
  if (!selected.every(Boolean) && by.all) selected = [by.all];
  if (!selected.every(Boolean)) throw new Error("Statistiques Q1+Q2 indisponibles.");
  const aliases = {
    fga: "fieldGoalsAttempted", fgm: "fieldGoalsMade",
    "3pa": "threePointersAttempted", "3pm": "threePointersMade",
    tov: "turnovers", orb: "offensiveRebounds", ftm: "freeThrowsMade", fta: "freeThrowsAttempted"
  };
  const attemptFromMade = { fga: "fieldGoalsMade", "3pa": "threePointersMade", fta: "freeThrowsMade" };
  const result = {};
  for (const side of ["home", "away"]) {
    result[side] = {};
    for (const [target, source] of Object.entries(aliases)) {
      let sum = 0, found = false;
      for (const p of selected) {
        const values = periodValues(p);
        const item = values[source];
        let value = item?.[side]?.value;
        if (value == null && attemptFromMade[target]) value = values[attemptFromMade[target]]?.[side]?.total;
        if (value != null && Number.isFinite(Number(value))) { sum += Math.round(Number(value)); found = true; }
      }
      result[side][target] = found ? sum : null;
    }
    for (const k of ["fga", "fgm", "3pa", "3pm", "ftm", "fta"]) {
      if (result[side][k] == null) throw new Error("Statistique essentielle absente: " + side + "." + k);
    }
    for (const k of ["tov", "orb"]) if (result[side][k] == null) result[side][k] = 0;
    const s = result[side];
    if (Object.values(s).some(v => !Number.isInteger(v) || v < 0)) throw new Error("Statistique invalide: " + side);
    if (s.fgm > s.fga || s["3pm"] > s["3pa"] || s["3pa"] > s.fga || s["3pm"] > s.fgm || s.ftm > s.fta) {
      throw new Error("Incohérence mathématique des statistiques: " + side);
    }
  }
  return result;
}
function normal(rng) {
  const u = Math.max(rng(), 1e-12), v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}
function simulate(hScore, aScore, h, a, n = 1200) {
  const hp = Math.max(1, h.fga - h.orb + h.tov + 0.44 * h.fta);
  const ap = Math.max(1, a.fga - a.orb + a.tov + 0.44 * a.fta);
  const paceMean = Math.min(65, Math.max(25, (hp + ap) / 2));
  const hPpp = Math.min(1.65, Math.max(0.65, 0.55 * (hScore / hp) + 0.45 * 1.05));
  const aPpp = Math.min(1.65, Math.max(0.65, 0.55 * (aScore / ap) + 0.45 * 1.05));
  let hw = 0, aw = 0, total = 0, homeSum = 0, awaySum = 0;
  let totals = [];
  for (let i = 0; i < n; i++) {
    const pace = Math.min(72, Math.max(20, paceMean + 3.5 * normal(Math.random)));
    const hs = Math.max(0, Math.round(pace * hPpp + Math.sqrt(Math.max(1, pace * hPpp)) * normal(Math.random)));
    const as = Math.max(0, Math.round(pace * aPpp + Math.sqrt(Math.max(1, pace * aPpp)) * normal(Math.random)));
    const hf = hScore + hs, af = aScore + as, t = hf + af;
    if (hf > af) hw++; else if (af > hf) aw++;
    homeSum += hf; awaySum += af; total += t; totals.push(t);
  }
  totals.sort((x,y) => x-y);
  return {
    homeWin: 100 * hw / n, awayWin: 100 * aw / n,
    homeMean: homeSum / n, awayMean: awaySum / n, totalMean: total / n,
    p10: totals[Math.floor(0.10 * (n-1))], p90: totals[Math.floor(0.90 * (n-1))]
  };
}
async function telegram(env, message) {
  const r = await fetch("https://api.telegram.org/bot" + env.TELEGRAM_BOT_TOKEN + "/sendMessage", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text: message, disable_web_page_preview: true }),
    signal: AbortSignal.timeout(15000)
  });
  const data = await r.json();
  if (!r.ok || !data.ok) throw new Error("Échec envoi Telegram.");
}
async function redisCommand(env, parts) {
  const base = String(env.UPSTASH_REDIS_REST_URL || "").replace(/\/+$/, "");
  if (!base || !env.UPSTASH_REDIS_REST_TOKEN) throw new Error("Secrets Upstash manquants.");
  const path = parts.map(v => encodeURIComponent(String(v))).join("/");
  const response = await fetch(base + "/" + path, {
    headers: { Authorization: "Bearer " + env.UPSTASH_REDIS_REST_TOKEN },
    signal: AbortSignal.timeout(10000)
  });
  if (!response.ok) throw new Error("Upstash Redis HTTP " + response.status);
  const body = await response.json();
  if (body.error) throw new Error("Upstash Redis: " + body.error);
  return body.result;
}
async function monitor(env) {
  for (const name of ["DATASPORTSAPI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]) {
    if (!env[name]) throw new Error("Secret manquant: " + name);
  }
  if (!env.UPSTASH_REDIS_REST_URL || !env.UPSTASH_REDIS_REST_TOKEN) throw new Error("Secrets Upstash Redis absents.");
  const payload = await api("/livescores", env.DATASPORTSAPI_API_KEY, "?sport=basketball");
  const matches = Array.isArray(payload.data) ? payload.data : [];
  console.log("Matchs LIVE reçus:", matches.length);
  for (const m of matches) {
    if (!isHalftime(m)) continue;
    const id = fixtureId(m);
    if (id == null) continue;
    const dedupeKey = "bpi:halftime:" + String(id);
    try {
      const reservation = await redisCommand(env, ["set", dedupeKey, "pending", "NX", "EX", PENDING_TTL_SECONDS]);
      if (reservation !== "OK") continue;
      const [hs, as] = score(m);
      const statsPayload = await api("/fixtures/" + encodeURIComponent(id) + "/statistics", env.DATASPORTSAPI_API_KEY);
      const stats = extractStats(statsPayload.data?.periods || []);
      const result = simulate(hs, as, stats.home, stats.away);
      const home = text(m.home) || "Domicile", away = text(m.away) || "Extérieur";
      const competition = text(m.competition || m.tournament || m.league) || "Non précisée";
      const favorite = result.homeMean > result.awayMean ? home : result.awayMean > result.homeMean ? away : "Équilibre";
      const message =
        "🏀 BPI — ALERTE MI-TEMPS\n" + home + " " + hs + "–" + as + " " + away +
        "\nCompétition : " + competition +
        "\n\nSIMULATION EXPLORATOIRE — NON CALIBRÉE" +
        "\nÉquipe projetée en tête : " + favorite +
        "\nVictoire domicile simulée : " + result.homeWin.toFixed(1) + "%" +
        "\nVictoire extérieur simulée : " + result.awayWin.toFixed(1) + "%" +
        "\nScore final moyen simulé : " + result.homeMean.toFixed(1) + "–" + result.awayMean.toFixed(1) +
        "\nTotal moyen simulé : " + result.totalMean.toFixed(1) +
        "\nIntervalle central 80% du total : " + result.p10 + "–" + result.p90 +
        "\n\n⚠️ Prototype non entraîné et non calibré : pourcentages non fiables. Aucune recommandation de pari ou de mise.";
      await telegram(env, message);
      await redisCommand(env, ["set", dedupeKey, "sent", "EX", DEDUPE_TTL_SECONDS]);
      console.log("Alerte envoyée pour fixture", id);
    } catch (e) {
      try { await redisCommand(env, ["del", dedupeKey]); } catch (stateError) { console.log("Échec libération déduplication", id, String(stateError)); }
      console.log("Match ignoré", id, String(e));
    }
  }
}
export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(monitor(env).catch(e => console.log("Surveillance BPI échouée:", String(e))));
  },
  async fetch() {
    return new Response("BPI monitor actif. Les résultats sont envoyés par Telegram.", { status: 200 });
  }
};
