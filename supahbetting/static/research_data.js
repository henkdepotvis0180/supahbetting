"use strict";
/* Local read-only research dashboard; never fabricates player or pitch facts. */
(() => {
  const elem = id => document.getElementById(id);
  const text = (tag, value, className) => {
    const el = document.createElement(tag);
    el.textContent = String(value ?? "Niet beschikbaar");
    if (className) el.className = className;
    return el;
  };
  const numeric = n => typeof n === "number"
    ? new Intl.NumberFormat("nl-NL").format(n) : "—";
  const decimal = n => typeof n === "number"
    ? new Intl.NumberFormat("nl-NL",{minimumFractionDigits:4,maximumFractionDigits:5}).format(n)
    : "Nog niet gemeten";
  const date = value => value && /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? value.split("-").reverse().join("-") : "Geen datum";
  function tile(label, value, description="") {
    const outer=text("div","","panel research-insight");
    outer.replaceChildren(
      text("span",label,"research-insight-label"),
      text("strong",value,"research-insight-number"),
      text("small",description,"research-insight-info"));
    return outer;
  }
  function titleBlock(title, content) {
    const node=document.createElement("div");
    node.className="research-data-note";
    node.append(text("strong",title),text("p",content));
    return node;
  }
  function tableOfRows(headers, rows) {
    const table=document.createElement("table");
    table.className="research-data-table";
    const head=document.createElement("thead");
    const hr=document.createElement("tr");
    for (const h of headers) hr.append(text("th",h));
    head.append(hr);
    const body=document.createElement("tbody");
    for (const row of rows) {
      const tr=document.createElement("tr");
      for (const cell of row) tr.append(text("td",cell));
      body.append(tr);
    }
    table.append(head,body);
    return table;
  }
  function render(payload) {
    const summary=elem("research-data-summary");
    const coverage=elem("research-data-leagues");
    const facts=elem("research-data-factors");
    const games=elem("research-data-matches");
    const status=elem("research-data-status");
    if (!payload.available) {
      summary.replaceChildren(titleBlock("Nog geen onderzoeksdata",payload.message));
      coverage.replaceChildren();
      facts.replaceChildren();
      games.replaceChildren();
      status.textContent="Nog niet geladen";
      return;
    }
    const report=payload.report, monitor=payload.monitor || {};
    const prospective=report.shadow_forecast_evaluation || {};
    const context=payload.context || {};
    const model=report.model_candidate || {};
    const periods=report.historical_metrics || {};
    const quality=report.source_quality || {};
    const freshness=quality.leagues || {};
    const globalAge=quality.days_since_latest_result;
    const recentText=globalAge === null || globalAge === undefined
      ? "Leeftijd uitslag onbekend"
      : globalAge === 0 ? "Laatste eindstand van vandaag"
      : globalAge+" dagen sinds laatste eindstand";
    const newCount=report.new_finished_results_since_last_check
      ?? monitor.new_final_matches ?? 0;
    summary.replaceChildren(
      tile("Gecontroleerde uitslagen",numeric(report.training_matches),
        "Vanaf 1 januari 2016, waar de bron beschikbaar is"),
      tile("Nieuwste eindstand",date(report.last_verified_result_date),
        recentText+(quality.is_stale?" · BRON ACHTERLOPEND":"")),
      tile("Echte toekomstige tests",numeric(prospective.graded_predictions),
        "Alleen voorspellingen vastgelegd vóór de speeldag"),
      tile("Prospectieve log loss",decimal(prospective.prospective_logloss),
        "Lager is beter; geen winstgarantie"),
      tile("Historische test log loss",decimal(periods.test?.model_logloss),
        "Retrospectief seizoen 2025/26"),
      tile("Nieuw sinds vorige controle",numeric(newCount),
        "Eerste import: "+numeric(quality.initial_backfill_matches ??
          report.initial_backfill_matches)+" historische uitslagen")
    );
    status.replaceChildren(
      text("strong","Broncontrole: "+(report.last_checked_at_utc || "onbekend")),
      text("span"," · GitHub: "+(monitor.sync_state || "geen status")),
      text("span"," · "+(report.missing_sources?.length || 0)+" ontbrekende bronbestanden"),
      text("span",quality.is_stale?" · Waarschuwing: scores zijn verouderd":
        " · Bronactualiteit blijft te controleren")
    );
    const competitions=Object.values(report.competitions || {});
    coverage.replaceChildren(tableOfRows(
      ["Competitie","Eindstanden","Laatste resultaat","Leeftijd bron","Gepland"],
      Object.entries(report.competitions || {}).map(([code,c]) => {
        const entry=freshness[code] || {};
        const age=entry.days_since_last_result;
        const severity=entry.freshness || "unknown";
        const label=typeof age==="number" ? age+" dagen"+(
          severity==="severely_stale"?" · ERNSTIG VERTRAAGD":
          severity==="stale"?" · VERTRAAGD":"") : "Onbekend";
        return [c.name,numeric(c.finished),date(c.last_result_date),
          label,numeric(c.scheduled)];
      })
    ));
    const factors = [
      ["Uitslagen", "Gecontroleerd waar beschikbaar", "Ja — bestaande scoremodel"],
      ["Opstellingen en wissels","Externe bron nog niet aangesloten","Nee"],
      ["Aanvallers: schoten, xG, passing","Eventdataprovider vereist","Nee"],
      ["Verdedigers: tackles, intercepties","Eventdataprovider vereist","Nee"],
      ["Officiële spelersbeschikbaarheid","Alleen publiek geverifieerde status","Nee"],
      ["Transfers en trainerswissels","Alleen officiële bekendmaking","Nee"],
      ["Weer en gras / veldkwaliteit","Alleen broninformatie van vóór aftrap","Nee"],
      ["Rustdagen / wedstrijdendruk","Afgeleid uit gecontroleerde vorige eindstanden","Alleen inzicht, nog niet in model"],
      ["Reisafstand","Stadioncoördinaten en reisroute nog niet gekoppeld","Nee"],
      ["Omkoping, voeding of privégeruchten","Bewust uitgesloten","Nee"]
    ];
    facts.replaceChildren(tableOfRows(
      ["Factor","Huidige gegevensstatus","In voorspelling gebruikt"], factors
    ));
    if (context.records) {
      facts.append(titleBlock("Controleerbare extra bronnen",
        numeric(context.records)+" bronrecords opgeslagen. Extra kenmerken staan nog uit " +
        "tot ze onafhankelijke chronologische evaluatie hebben doorstaan."));
    }
    const recent = (report.latest_finished_matches || []).slice(-12).reverse();
    games.replaceChildren(tableOfRows(
      ["Datum","Competitie","Wedstrijd","Uitslag"],
      recent.map(m => [
        date(m.date), m.league, m.home+" – "+m.away, m.hg+" – "+m.ag
      ])
    ));
    const form = (report.derived_team_form_preview || []).slice(0,8);
    if(form.length) {
      games.append(titleBlock("Vorm en rust voor komende wedstrijden",
        "Resultaten uit de laatste vijf gespeelde duels; nooit gegevens van dezelfde of toekomstige speeldag. Dit beïnvloedt het model nog niet."));
      games.append(tableOfRows(
        ["Wedstrijd","Laatste 5: goals voor/tegen","Rustdagen thuis / uit"],
        form.map(m=>[
          m.home+" – "+m.away,
          ((m.home_form?.goals_for_last_5_mean ?? "—")+"/"+(m.home_form?.goals_against_last_5_mean ?? "—"))+
          " · "+((m.away_form?.goals_for_last_5_mean ?? "—")+"/"+(m.away_form?.goals_against_last_5_mean ?? "—")),
          (m.home_form?.rest_days ?? "—")+" / "+(m.away_form?.rest_days ?? "—")
        ])
      ));
    }
    if(quality.is_stale) {
      games.append(titleBlock("Bronactualiteit: waarschuwing",
        "De laatste eindstand is "+date(report.last_verified_result_date)+
        ". De monitor haalt bronbestanden op, maar een succesvolle download "
        +"betekent niet dat de onderliggende competities actueel zijn. "
        +"Gebruik deze dataset niet als complete actuele wedstrijddatabase."));
    }
    const missing = report.missing_sources || [];
    if (missing.length) {
      games.append(titleBlock("Ontbrekende bestanden",
        missing.slice(0,24).join(", ")+(missing.length > 24 ? " …" : "")+
        ". Dit zijn hiaten in de bron, geen bewijs dat wedstrijden niet gespeeld zijn."));
    }
    games.append(titleBlock("Modelgrenzen",
      "Het onderzoek gebruikt momenteel doelpunten en historische teamratings. " +
      "De hogere dimensies worden pas gebruikt na broncontrole en terugkijkvrije evaluatie. " +
      "Nieuwe uitslagen maken data actueler; niet automatisch de voorspellingen beter."));
    if (model.version) {
      games.append(titleBlock("Lokaal experimenteel model",
        model.version+" · dataset "+(model.dataset_sha256 || "").slice(0,12)+
        "… · niet automatisch actief in het productiemodel."));
    }
  }
  async function refresh() {
    try {
      const response=await fetch("/api/research/data/status",{cache:"no-store"});
      if (!response.ok) throw Error("HTTP "+response.status);
      render(await response.json());
    } catch (error) {
      elem("research-data-status").textContent="Onderzoeksgegevens niet bereikbaar: "+error.message;
    }
  }
  document.addEventListener("DOMContentLoaded",() => {
    if (!elem("research-data-summary")) return;
    elem("research-data-refresh").addEventListener("click",refresh);
    refresh();
    setInterval(refresh,60_000);
  });
})();
