"use strict";

const $ = id => document.getElementById(id);
const state = { matches: [], slips: [], stats: null, legs: [], quote: null, filter: "open", version: 0 };
const MARKET = { home: "Thuis wint (1)", draw: "Gelijkspel (X)", away: "Uit wint (2)" };
const money = v => new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" }).format(v);
const num = v => new Intl.NumberFormat("nl-NL", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);
const percent = v => new Intl.NumberFormat("nl-NL", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(v);
const safe = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function notify(message, error = false) {
  const el = $("message");
  el.textContent = message;
  el.classList.toggle("error", error);
  el.classList.remove("hidden");
  el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function api(path, method = "GET", body = null) {
  const options = { method, headers: {} };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch (err) {
    throw Error("Kan de lokale server niet bereiken. Staat start_dashboard.bat aan?");
  }
  const data = await response.json();
  if (!response.ok) throw Error(data.error || "Er is iets misgegaan");
  return data;
}

function renderStats() {
  const stats = state.stats;
  if (!stats) return;
  $("stat-open").textContent = stats.opened;
  $("stat-exposure").textContent = money(stats.open_stake);
  $("stat-profit").textContent = money(stats.realized_profit);
  $("stat-profit").style.color = stats.realized_profit < 0 ? "var(--red)" : "var(--text)";
  $("stat-roi").textContent = stats.realized_roi === null ? "—" : percent(stats.realized_roi);
}

function kickoffText(value) {
  if (!value) return "Aftrap niet ingesteld";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "Aftrap onbekend" :
    d.toLocaleString("nl-NL", { dateStyle: "medium", timeStyle: "short" });
}

function marketButton(match, market) {
  const d = match.analysis.markets[market];
  const selected = state.legs.some(s => s.match_id === match.id && s.market === market);
  const edge = d.expected_roi;
  return `<button class="market-btn ${selected ? "selected" : ""}" type="button"
      data-action="select" data-id="${match.id}" data-market="${market}" ${match.is_settled ? "disabled" : ""}
      aria-pressed="${selected}">
      <span class="m-name">${safe(MARKET[market])}</span>
      <span class="m-odds">${num(d.decimal_odds)}</span>
      <span class="m-edge ${edge >= 0 ? "pos" : "neg"}">Model-EV ${edge > 0 ? "+" : ""}${percent(edge)}</span>
    </button>`;
}

function renderMatches() {
  $("count-open").textContent = "(" + state.matches.filter(m => !m.is_settled).length + ")";
  const query = $("search").value.trim().toLocaleLowerCase("nl");
  const found = state.matches.filter(m =>
    (state.filter === "all" || !m.is_settled) &&
    (m.home_team + " " + m.away_team).toLocaleLowerCase("nl").includes(query));
  $("match-list").innerHTML = found.length ? found.map(m => `
    <article class="match-card">
      <div class="match-heading">
        <div><div class="eyebrow">WEDSTRIJD #${m.id}</div>
        <h3>${safe(m.home_team)} <span class="muted">—</span> ${safe(m.away_team)}</h3></div>
        <span class="label ${m.source.includes("DEMO") ? "demo" : ""}">${safe(m.source)}</span>
      </div>
      <div class="match-sub">${safe(kickoffText(m.kickoff))} · xG ${num(m.home_xg)} – ${num(m.away_xg)}</div>
      <div class="market-grid">${["home", "draw", "away"].map(k => marketButton(m, k)).join("")}</div>
      <div class="market-explain">
        <span>Modelkans: <strong>1 ${percent(m.analysis.probabilities.home)}</strong></span>
        <span><strong>X ${percent(m.analysis.probabilities.draw)}</strong></span>
        <span><strong>2 ${percent(m.analysis.probabilities.away)}</strong></span>
      </div>
      <div class="market-explain"><span>Fair odds: 1 <strong>${num(m.analysis.markets.home.fair_odds)}</strong> ·
        X <strong>${num(m.analysis.markets.draw.fair_odds)}</strong> ·
        2 <strong>${num(m.analysis.markets.away.fair_odds)}</strong></span>
        <span>Bookmakermarge ${percent(m.analysis.market_margin)}</span></div>
      ${m.is_settled ? `<div class="match-result">✓ Afgehandeld: ${m.result_home} – ${m.result_away}</div>` : ""}
    </article>`).join("") :
    '<div class="empty">Geen wedstrijden gevonden. Voeg zelf een wedstrijd toe of laad fictieve voorbeelden.</div>';
}

function renderLegs() {
  const size = state.legs.length;
  $("slip-count").textContent = size + (size === 1 ? " selectie" : " selecties");
  $("slip-type").textContent = size === 0 ? "Nog geen selectie" :
    size === 1 ? "Enkelvoudige bet" : "Combinatie · " + size + " wedstrijden";
  const items = state.legs.map(s => {
    const match = state.matches.find(m => m.id === s.match_id);
    if (!match) return "";
    return `<div class="slip-leg"><div class="slip-leg-head">
      <strong>${safe(match.home_team)} — ${safe(match.away_team)}</strong>
      <button class="remove" type="button" data-action="remove" data-id="${s.match_id}"
      aria-label="Verwijder ${safe(match.home_team)} tegen ${safe(match.away_team)}">×</button>
      </div><p>${safe(MARKET[s.market])} <span class="slip-odds">· ${num(match["odds_" + s.market])}</span></p></div>`;
  }).join("");
  $("slip-legs").innerHTML = size ? items : '<div class="slip-empty">Kies bij een wedstrijd de thuis-, gelijk- of uitquotering.</div>';
}

function renderQuote() {
  const q = state.quote?.quote;
  const summary = $("slip-summary"), edge = $("slip-edge");
  $("save-slip").disabled = !q;
  if (!q) {
    summary.innerHTML = `<div class="summary-row"><span>Gecombineerde odds</span><strong>—</strong></div>
    <div class="summary-row"><span>Modelkans</span><strong>—</strong></div>
    <div class="summary-row"><span>Mogelijke uitbetaling</span><strong>—</strong></div>`;
    edge.classList.add("hidden");
    return;
  }
  summary.innerHTML = `
    <div class="summary-row"><span>Gecombineerde odds</span><strong>${num(q.combined_odds)}</strong></div>
    <div class="summary-row"><span>Modelkans dat alles klopt</span><strong>${percent(q.combined_probability)}</strong></div>
    <div class="summary-row"><span>Fictieve inzet</span><strong>${money(q.stake)}</strong></div>
    <div class="summary-row large"><span>Mogelijke bruto-uitbetaling</span><strong>${money(q.gross_payout)}</strong></div>
    <div class="summary-row"><span>Mogelijke nettowinst</span><strong>${money(q.potential_profit)}</strong></div>`;
  edge.classList.remove("hidden", "positive", "negative");
  edge.classList.add(q.expected_roi >= 0 ? "positive" : "negative");
  edge.textContent = "Theoretische model-EV: " + percent(q.expected_roi) +
    " (" + money(q.expected_profit) + "). Dit is geen voorspelde of gegarandeerde winst.";
}

async function updateQuote() {
  const current = ++state.version;
  state.quote = null;
  renderLegs();
  renderQuote();
  if (!state.legs.length) return;
  try {
    const response = await api("/api/slips/quote", "POST", {
      legs: state.legs,
      stake: Number($("stake").value)
    });
    if (current !== state.version) return;
    state.quote = response;
    renderQuote();
  } catch (err) {
    if (current !== state.version) return;
    notify(err.message, true);
  }
}

function selectLeg(matchId, market) {
  const current = state.legs.find(x => x.match_id === matchId);
  if (current && current.market === market) {
    state.legs = state.legs.filter(x => x.match_id !== matchId);
  } else if (current) {
    state.legs = state.legs.map(x => x.match_id === matchId ? { match_id: matchId, market } : x);
  } else {
    if (state.legs.length >= 8) return notify("Een combinatie mag maximaal 8 wedstrijden bevatten.", true);
    state.legs.push({ match_id: matchId, market });
  }
  renderMatches();
  updateQuote();
}

function renderSettlement() {
  const open = state.matches.filter(m => !m.is_settled);
  $("settle-list").innerHTML = open.length ? open.map(m => `
    <div class="history-item"><div class="item-title">${safe(m.home_team)} – ${safe(m.away_team)}</div>
    <div class="item-sub">#${m.id} · ${safe(m.source)} · uitslag handmatig bevestigen</div>
    <form class="settle-fields" data-settle-id="${m.id}">
      <label>Thuis <input name="home_goals" type="number" min="0" max="100" step="1" required aria-label="Goals thuisteam"></label>
      <label>Uit <input name="away_goals" type="number" min="0" max="100" step="1" required aria-label="Goals uitteam"></label>
      <button class="btn btn-quiet" type="submit">Afrekenen</button></form></div>`).join("") :
    '<p class="muted">Alle wedstrijden zijn afgerekend, of er zijn nog geen wedstrijden.</p>';
}

function renderHistory() {
  $("slip-history").innerHTML = state.slips.length ? state.slips.map(s => `
    <div class="history-item">
      <div class="item-title">Betslip #${s.id} <span class="result-pill ${safe(s.status)}">${s.status === "won" ? "Gewonnen" :
      s.status === "lost" ? "Verloren" : "Openstaand"}</span></div>
      <div class="item-sub">${s.legs.length} selectie(s) · ${money(s.stake)} inzet · odds ${num(s.combined_odds)}</div>
      <div class="item-sub">${s.status === "open" ?
        "Mogelijke bruto-uitbetaling: " + money(s.potential_payout) :
        "Fictief nettoresultaat: " + money(s.profit)}</div>
      <ul class="history-legs">${s.legs.map(l =>
        `<li>${safe(l.home_snapshot)} – ${safe(l.away_snapshot)}: ${safe(MARKET[l.market])} @ ${num(l.odds_snapshot)}</li>`).join("")}</ul>
    </div>`).join("") : '<p class="muted">Nog geen opgeslagen fictieve betslips.</p>';
}

async function refresh() {
  try {
    const [matches, slips, stats] = await Promise.all([
      api("/api/matches"), api("/api/slips"), api("/api/stats")
    ]);
    state.matches = matches.matches;
    state.slips = slips.slips;
    state.stats = stats;
    state.legs = state.legs.filter(l => state.matches.some(m => m.id === l.match_id && !m.is_settled));
    renderStats(); renderMatches(); renderSettlement(); renderHistory();
    await updateQuote();
  } catch (err) {
    notify(err.message, true);
  }
}

async function saveMatch(event) {
  event.preventDefault();
  const f = new FormData(event.currentTarget);
  const kickoff = f.get("kickoff");
  const payload = {
    home_team: f.get("home_team"), away_team: f.get("away_team"), source: f.get("source"),
    kickoff: kickoff ? new Date(kickoff).toISOString() : "",
    home_xg: Number(f.get("home_xg")), away_xg: Number(f.get("away_xg")),
    odds_home: Number(f.get("odds_home")), odds_draw: Number(f.get("odds_draw")),
    odds_away: Number(f.get("odds_away"))
  };
  try {
    await api("/api/matches", "POST", payload);
    $("match-editor").open = false;
    await refresh();
    notify("Wedstrijd opgeslagen. Klik op een quotering om deze te selecteren.");
  } catch (err) {
    notify(err.message, true);
  }
}

async function saveSlip() {
  if (!state.legs.length || !state.quote) return;
  const button = $("save-slip");
  button.disabled = true;
  try {
    const response = await api("/api/slips", "POST", {
      legs: state.legs, stake: Number($("stake").value)
    });
    state.legs = [];
    await refresh();
    notify("Fictieve betslip #" + response.slip.id + " opgeslagen. Dit is geen echte weddenschap.");
  } catch (err) {
    notify(err.message, true);
    button.disabled = false;
  }
}

async function settleMatch(form) {
  const id = Number(form.dataset.settleId);
  const f = new FormData(form);
  const h = Number(f.get("home_goals")), a = Number(f.get("away_goals"));
  if (!Number.isInteger(h) || !Number.isInteger(a) || h < 0 || a < 0 || h > 100 || a > 100) {
    return notify("Vul geldige gehele uitslagen in.", true);
  }
  const m = state.matches.find(item => item.id === id);
  if (!m) return;
  if (!confirm(`Uitslag ${m.home_team} – ${m.away_team}: ${h}–${a} vastleggen? Dit kan niet worden teruggedraaid.`)) return;
  try {
    await api("/api/matches/" + id + "/settle", "POST", { home_goals: h, away_goals: a });
    await refresh();
    notify("Uitslag vastgelegd. Relevante fictieve betslips zijn bijgewerkt.");
  } catch (err) {
    notify(err.message, true);
  }
}

function init() {
  $("demo-button").addEventListener("click", async () => {
    try {
      const data = await api("/api/demo", "POST", {});
      await refresh();
      notify(data.message + " — dit zijn géén echte wedstrijden.");
    } catch (err) { notify(err.message, true); }
  });
  $("refresh-button").addEventListener("click", refresh);
  $("match-form").addEventListener("submit", saveMatch);
  $("save-slip").addEventListener("click", saveSlip);
  $("stake").addEventListener("change", updateQuote);
  $("search").addEventListener("input", renderMatches);
  document.querySelectorAll("[data-filter]").forEach(btn => btn.addEventListener("click", () => {
    state.filter = btn.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach(b => {
      b.classList.toggle("active", b === btn);
      b.setAttribute("aria-pressed", String(b === btn));
    });
    renderMatches();
  }));
  $("match-list").addEventListener("click", event => {
    const button = event.target.closest("[data-action=select]");
    if (button) selectLeg(Number(button.dataset.id), button.dataset.market);
  });
  $("slip-legs").addEventListener("click", event => {
    const button = event.target.closest("[data-action=remove]");
    if (button) {
      state.legs = state.legs.filter(x => x.match_id !== Number(button.dataset.id));
      renderMatches();
      updateQuote();
    }
  });
  $("settle-list").addEventListener("submit", event => {
    const form = event.target.closest("form[data-settle-id]");
    if (form) { event.preventDefault(); settleMatch(form); }
  });
  refresh();
}

document.addEventListener("DOMContentLoaded", init);
