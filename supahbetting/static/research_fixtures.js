"use strict";
/* Upcoming schedules & experimental probabilities, from a LOCAL file only. */
(() => {
  const $ = id => document.getElementById(id);
  const make = (tag, content, className) => {
    const node = document.createElement(tag);
    if (content !== undefined) node.textContent = String(content);
    if (className) node.className = className;
    return node;
  };
  let responseCache = null;
  const LEAGUES = {
    "nl.1":"Eredivisie","be.1":"Belgische Pro League",
    "en.1":"Premier League","de.1":"Bundesliga","es.1":"La Liga",
    "it.1":"Serie A","fr.1":"Ligue 1"
  };
  const percent = v => typeof v === "number"
    ? new Intl.NumberFormat("nl-BE",{minimumFractionDigits:1,maximumFractionDigits:1}).format(v*100)+"%"
    : "—";
  const goals = v => typeof v === "number"
    ? new Intl.NumberFormat("nl-BE",{minimumFractionDigits:2,maximumFractionDigits:2}).format(v)
    : "—";
  const shortTime = iso => {
    if (!iso) return "Aftraptijd niet bevestigd";
    const value = new Date(iso);
    return Number.isNaN(value.getTime()) ? "Aftraptijd onbekend" :
      new Intl.DateTimeFormat("nl-BE",{timeZone:"Europe/Brussels",
        day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}).format(value);
  };
  const longTime = iso => {
    if (!iso) return "Nog niet gesynchroniseerd";
    const value = new Date(iso);
    return Number.isNaN(value.getTime()) ? "Onbekende tijd" :
      new Intl.DateTimeFormat("nl-BE",{timeZone:"Europe/Brussels",
        dateStyle:"medium",timeStyle:"short"}).format(value);
  };
  const dateLocal = fixture => {
    if (fixture.kickoff) {
      const value = new Date(fixture.kickoff);
      if (!Number.isNaN(value.getTime())) {
        return new Intl.DateTimeFormat("sv-SE",{timeZone:"Europe/Brussels",
          year:"numeric",month:"2-digit",day:"2-digit"}).format(value);
      }
    }
    return fixture.date;
  };
  const localToday = () => new Intl.DateTimeFormat("sv-SE",{
    timeZone:"Europe/Brussels",year:"numeric",month:"2-digit",day:"2-digit"
  }).format(new Date());
  const offset = (date, base) => Math.round(
    (Date.parse(date+"T12:00:00Z") - Date.parse(base+"T12:00:00Z"))/86400000
  );
  function metric(label, value, cls) {
    const field=make("div",undefined,"fixture-metric "+(cls||""));
    field.append(make("span",label),make("strong",value));
    return field;
  }
  function draw() {
    const holder=$("research-fixture-list");
    if (!holder) return;
    if (!responseCache || !responseCache.available) {
      holder.replaceChildren(make("p",
        responseCache?.message ||
        "Start eerst de onderzoeksmonitor om het actuele speelschema op te halen.",
        "fixture-empty"));
      return;
    }
    const data=responseCache;
    const selectedLeague=$("research-fixture-league").value;
    const range=Number($("research-fixture-range").value);
    const mode=$("research-fixture-filter").value;
    const today=localToday();
    const choices=(data.fixtures||[]).filter(f=>{
      const day=offset(dateLocal(f),today);
      return Number.isFinite(day) && day >= 0 && day <= range
        && (selectedLeague==="all" || f.league===selectedLeague)
        && (mode==="all" || (mode==="predicted" && f.prediction)
          || (mode==="confirmed" && f.source_confirmed));
    });
    const cards=[];
    for(const f of choices.slice(0,100)) {
      const card=make("article",undefined,"panel fixture-card");
      const top=make("div",undefined,"fixture-card-top");
      top.append(make("span",LEAGUES[f.league]||f.league),
                 make("span",shortTime(f.kickoff)||f.date));
      const teams=make("h3",f.home+" – "+f.away);
      const status=make("p",undefined,"fixture-provider");
      const providerName={
        "football-data":"football-data.org","sportsdb":"TheSportsDB",
        "openliga":"OpenLigaDB","openfootball-archive":"OpenFootball (archief)"
      }[f.provider]||"Onbekend";
      status.textContent=providerName+" · "+
        (f.source_confirmed?"Schema onlangs opgehaald":"VOORLOPIG schema · niet recent bevestigd");
      const source=make("a","Bron / informatie");
      source.href=f.source_url;
      source.target="_blank";
      source.rel="noopener noreferrer";
      status.append(" · ",source);
      card.append(top,teams,status);
      if(f.prediction) {
        const model=f.prediction;
        const grid=make("div",undefined,"fixture-chances");
        grid.append(metric("Thuiswinst",percent(model.probabilities.home)),
                    metric("Gelijkspel",percent(model.probabilities.draw)),
                    metric("Uitwinst",percent(model.probabilities.away)));
        const info=make("p",
          "Verwachte goals: thuis "+goals(model.expected_goals_home)+
          " · uit "+goals(model.expected_goals_away)+
          " · model v"+model.model_version+
          " · data t/m "+model.data_through,
          "fixture-details");
        const caution=make("p",model.data_warning,"fixture-warning");
        card.append(grid,info,caution);
      } else {
        const why=make("p",f.prediction_unavailable_reason||
          "Niet genoeg geverifieerde informatie voor een voorspelling",
          "fixture-warning");
        card.append(why);
      }
      cards.push(card);
    }
    if(!choices.length) {
      holder.replaceChildren(make("p",
        "Geen bevestigde wedstrijden gevonden voor deze selectie. "+
        "De gratis bron geeft slechts een beperkt deel van het speelschema; "+
        "probeer alle competities of een langere periode.",
        "fixture-empty"));
    } else {
      holder.replaceChildren(...cards);
      if(choices.length>100) {
        holder.append(make("p",
          "Alleen de eerste 100 wedstrijden getoond; gebruik de filters.","fixture-empty"));
      }
    }
    const stats=$("research-fixture-summary");
    stats.replaceChildren(
      metric("Wedstrijden (0–15 dagen)",data.schedule_count||0),
      metric("Recent bevestigd",data.confirmed_schedule_count||0),
      metric("Modelvoorspellingen",data.predicted_count||0),
      metric("Niet bevestigd",data.provisional_schedule_count||0)
    );
    const msgs=[];
    if(data.model_last_data) msgs.push("Modeluitslagen t/m "+data.model_last_data);
    msgs.push("Laatste schema-ophaling: "+longTime(data.updated_at_utc));
    msgs.push("Prognoses vastgelegd vóór aftrap: "+
      (data.prospective_evaluation?.total_pre_match_snapshots ?? 0));
    msgs.push("Echt beoordeeld: "+(data.prospective_evaluation?.graded_total ?? 0));
    const warnings=(data.provider_warnings||[]);
    const note=$("research-fixture-status");
    note.replaceChildren(make("strong",msgs.join(" · ")));
    if(warnings.length) note.append(make("p",
      "Bronwaarschuwingen: "+warnings.slice(0,4).join(" · ")+
      (warnings.length>4?" · en "+(warnings.length-4)+" meer":""),
      "fixture-warning"));
  }
  async function refresh() {
    const holder=$("research-fixture-list");
    try {
      const response=await fetch("/api/research/upcoming",{cache:"no-store"});
      if(!response.ok) throw new Error("HTTP "+response.status);
      responseCache=await response.json();
      draw();
    } catch(error) {
      if(holder) holder.replaceChildren(
        make("p","Geen verbinding met lokaal speelschema: "+error.message,"fixture-empty"));
    }
  }
  document.addEventListener("DOMContentLoaded",()=>{
    if (!$("research-fixture-list")) return;
    for(const [code,name] of Object.entries(LEAGUES)) {
      const option=make("option",name);
      option.value=code;
      $("research-fixture-league").append(option);
    }
    for(const id of ["research-fixture-league","research-fixture-range","research-fixture-filter"]) {
      $(id).addEventListener("change",draw);
    }
    $("research-fixture-refresh").addEventListener("click",refresh);
    refresh();
    setInterval(refresh,60_000);
  });
})();
