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
function poisson(lambda, rng) {
  const limit = Math.exp(-lambda);
  let k = 0, product = 1;
  do { k++; product *= rng(); } while (product > limit);
  return k - 1;
}
function percentile(sorted, p) {
  const position = (sorted.length - 1) * p;
  const lower = Math.floor(position), upper = Math.ceil(position);
  return lower === upper ? sorted[lower] : sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
}
function simulate(hScore, aScore, h, a, n = 1200, rng = Math.random) {
  const hp = Math.max(1, h.fga - h.orb + h.tov + 0.44 * h.fta);
  const ap = Math.max(1, a.fga - a.orb + a.tov + 0.44 * a.fta);
  const paceMean = Math.min(65, Math.max(25, (hp + ap) / 2));
  const hPpp = Math.min(1.65, Math.max(0.65, 0.55 * (hScore / hp) + 0.45 * 1.05));
  const aPpp = Math.min(1.65, Math.max(0.65, 0.55 * (aScore / ap) + 0.45 * 1.05));
  let hw = 0, aw = 0, tie = 0, homeSum = 0, awaySum = 0;
  const totals = [], margins = [];
  for (let i = 0; i < n; i++) {
    const pace = Math.min(72, Math.max(20, paceMean + 3.5 * normal(rng)));
    const he = Math.min(1.75, Math.max(0.60, hPpp + 0.16 * normal(rng)));
    const ae = Math.min(1.75, Math.max(0.60, aPpp + 0.16 * normal(rng)));
    const hf = hScore + poisson(pace * he, rng), af = aScore + poisson(pace * ae, rng);
    const margin = hf - af;
    if (margin > 0) hw++; else if (margin < 0) aw++; else tie++;
    homeSum += hf; awaySum += af; totals.push(hf + af); margins.push(margin);
  }
  totals.sort((x,y) => x-y); margins.sort((x,y) => x-y);
  return {
    homeWin: 100 * hw / n, awayWin: 100 * aw / n, tie: 100 * tie / n,
    homeMean: homeSum / n, awayMean: awaySum / n, totalMean: (homeSum + awaySum) / n,
    totalMedian: percentile(totals, 0.5), p10: percentile(totals, 0.1), p90: percentile(totals, 0.9),
    marginP10: percentile(margins, 0.1), marginP90: percentile(margins, 0.9),
    homePossessions: hp, awayPossessions: ap, paceMean, homePpp: hPpp, awayPpp: aPpp
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

const HOOPS_BASE = "https://hoopsapi.com/api/v1";
const HOOPS_REFRESH_SECONDS = 3 * 60 * 60; // plafond conservateur: au plus 8 appels/jour
const MARKET_MAX_AGE_SECONDS = 15 * 60;

function normTeam(value) {
  return String(value || "").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9]/g, "");
}
function parseTime(value) {
  const n = Date.parse(value || "");
  return Number.isFinite(n) ? n : null;
}
function marketPairs(game) {
  const out = [];
  const add = (provider, period, marketName, market, a, b, capturedAt) => {
    if (!market || typeof market !== "object") return;
    const x = Number(market[a]), y = Number(market[b]);
    const captured = parseTime(capturedAt);
    const age = captured == null ? null : Math.floor((Date.now() - captured) / 1000);
    if (!(x > 1 && y > 1) || age == null || age < -60 || age > MARKET_MAX_AGE_SECONDS) return;
    const ix = 1 / x, iy = 1 / y, sum = ix + iy;
    out.push({ provider, period, market: marketName, line: market.line ?? null,
      captured_at: capturedAt, age_seconds: age, first_price: x, second_price: y,
      first_fair_probability: ix / sum, second_fair_probability: iy / sum });
  };
  for (const [provider, data] of Object.entries(game.providers || {})) {
    if (!data || typeof data !== "object") continue;
    add(provider, "ft", "moneyline", data.moneyline, "home", "away", data.captured_at);
    add(provider, "ft", "handicap", data.handicap, "home", "away", data.captured_at);
    add(provider, "ft", "total", data.over_under, "over", "under", data.captured_at);
    for (const key of ["team_total_home", "team_total_away"])
      add(provider, "ft", key, data[key], "over", "under", data.captured_at);
  }
  for (const [period, providers] of Object.entries(game.periods || {})) {
    for (const [provider, markets] of Object.entries(providers || {})) {
      if (!markets || typeof markets !== "object") continue;
      for (const key of ["moneyline", "spread", "total", "team_total_home", "team_total_away"]) {
        const m = markets[key];
        add(provider, period, key, m, key === "moneyline" || key === "spread" ? "home" : "over",
          key === "moneyline" || key === "spread" ? "away" : "under", m?.captured_at);
      }
    }
  }
  return out;
}
async function fetchHoopsBatch(env) {
  if (!env.HOOPSAPI_API_KEY) throw new Error("Secret HOOPSAPI_API_KEY manquant.");
  const response = await fetch(HOOPS_BASE + "/games?competition=NBA", {
    headers: { Authorization: "Bearer " + env.HOOPSAPI_API_KEY },
    signal: AbortSignal.timeout(15000)
  });
  if (!response.ok) throw new Error("HoopsAPI HTTP " + response.status);
  const payload = await response.json();
  if (!Array.isArray(payload.games)) throw new Error("Réponse HoopsAPI sans tableau games.");
  return payload.games;
}
async function refreshHoopsSnapshots(env) {
  const lock = await redisCommand(env, ["set", "bpi:hoops:last_fetch", String(Date.now()), "NX", "EX", HOOPS_REFRESH_SECONDS]);
  if (lock !== "OK") return { refreshed: false, games: 0 };
  try {
    const games = await fetchHoopsBatch(env);
    for (const game of games) {
      if (game?.game_id == null) continue;
      const record = { game_id: game.game_id, home: game.home, away: game.away,
        start_time: game.start_time, updated_at: game.updated_at, markets: marketPairs(game) };
      await redisCommand(env, ["set", "bpi:hoops:game:" + game.game_id, JSON.stringify(record), "EX", 86400]);
    }
    await redisCommand(env, ["set", "bpi:hoops:last_success", String(Date.now()), "EX", 86400]);
    return { refreshed: true, games: games.length };
  } catch (e) {
    await redisCommand(env, ["del", "bpi:hoops:last_fetch"]);
    throw e;
  }
}
async function findMarketSnapshot(env, fixture) {
  const keys = await redisCommand(env, ["keys", "bpi:hoops:game:*"]);
  if (!Array.isArray(keys)) return null;
  const home = normTeam(text(fixture.home)), away = normTeam(text(fixture.away));
  const start = parseTime(fixture.startTime || fixture.start_time || fixture.startDate);
  const candidates = [];
  for (const key of keys.slice(0, 100)) {
    const raw = await redisCommand(env, ["get", key]);
    if (!raw) continue;
    let item; try { item = JSON.parse(raw); } catch { continue; }
    const sameTeams = normTeam(item.home) === home && normTeam(item.away) === away;
    const marketStart = parseTime(item.start_time);
    if (!sameTeams || start == null || marketStart == null || Math.abs(start - marketStart) > 180 * 60000) continue;
    candidates.push(item);
  }
  if (candidates.length !== 1) return { status: candidates.length ? "AMBIGUOUS" : "NO_MATCH", markets: [] };
  const item = candidates[0];
  const markets = (item.markets || []).filter(m => m.age_seconds >= 0 && m.age_seconds <= MARKET_MAX_AGE_SECONDS);
  return { status: markets.length ? "MARKET_SNAPSHOT_AVAILABLE" : "NO_FRESH_MARKET",
    game_id: item.game_id, markets };
}
async function recordMarketMovement(env, fixtureIdValue, markets) {
  const changes = [];
  for (const m of markets) {
    const signature = [m.provider, m.period, m.market, m.line ?? "none"].join(":");
    const key = "bpi:market:last:" + fixtureIdValue + ":" + signature;
    const previousRaw = await redisCommand(env, ["get", key]);
    if (previousRaw) {
      try {
        const previous = JSON.parse(previousRaw);
        changes.push({ provider: m.provider, period: m.period, market: m.market, line: m.line,
          previous_home_or_over: previous.first_price, current_home_or_over: m.first_price,
          previous_away_or_under: previous.second_price, current_away_or_under: m.second_price,
          delta_first: m.first_price - previous.first_price, delta_second: m.second_price - previous.second_price });
      } catch {}
    }
    await redisCommand(env, ["set", key, JSON.stringify(m), "EX", 7 * 86400]);
  }
  return changes;
}

async function monitor(env) {
  for (const name of ["DATASPORTSAPI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]) {
    if (!env[name]) throw new Error("Secret manquant: " + name);
  }
  if (!env.UPSTASH_REDIS_REST_URL || !env.UPSTASH_REDIS_REST_TOKEN) throw new Error("Secrets Upstash Redis absents.");
  const payload = await api("/livescores", env.DATASPORTSAPI_API_KEY, "?sport=basketball");
  const matches = Array.isArray(payload.data) ? payload.data : [];\n  try { console.log("HoopsAPI snapshot:", JSON.stringify(await refreshHoopsSnapshots(env))); }\n  catch (e) { console.log("Cotes HoopsAPI indisponibles:", String(e)); }
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
      const result = simulate(hs, as, stats.home, stats.away);\n      let marketInfo = null, movements = [];\n      try { marketInfo = await findMarketSnapshot(env, m); if (marketInfo?.markets?.length) movements = await recordMarketMovement(env, id, marketInfo.markets); }\n      catch (marketError) { console.log("Comparaison marché indisponible", id, String(marketError)); }
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
        "\nÉgalité simulée : " + result.tie.toFixed(1) + "%" +
        "\nScore final moyen simulé : " + result.homeMean.toFixed(1) + "–" + result.awayMean.toFixed(1) +
        "\nTotal moyen simulé : " + result.totalMean.toFixed(1) +
        "\nIntervalle central 80% du total : " + result.p10 + "–" + result.p90 +
        "\n\n⚠️ Prototype non entraîné et non calibré : pourcentages non fiables. Aucune recommandation de pari ou de mise.";
      await telegram(env, message);
      // Après confirmation Telegram, garder la réservation même si Redis échoue.
      try {
        await redisCommand(env, ["set", dedupeKey, "sent", "EX", DEDUPE_TTL_SECONDS]);
      } catch (stateError) {
        console.log("Alerte envoyée mais statut Redis non finalisé; réservation conservée", id, String(stateError));
      }
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
