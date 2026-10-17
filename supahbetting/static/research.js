"use strict";
/* An isolated, read-only research view. No real-money actions or automatic scraping. */
const rEl = id => document.getElementById(id);
const researchState = {rows: [], status: null, busy: false};
const rPct = v => (v * 100).toLocaleString("nl-NL", {
  minimumFractionDigits: 1, maximumFractionDigits: 1
}) + "%";
const rNum = v => Number(v).toLocaleString("nl-NL", {
  minimumFractionDigits: 2, maximumFractionDigits: 2
});
const MARKET_NAMES = {home:"Thuis (1)",draw:"Gelijk (X)",away:"Uit (2)"};
const SOURCE_NAMES = {
  prophitbet:"ProphitBet", oddsharvester:"OddsHarvester", prediict:"Prediict"
};
const AGE_TEXT = {
  historisch:"Historisch", tijd_onbekend:"Opnametijd onbekend",
  tijd_ongeldig:"Tijd niet geldig", max_24_uur_oud:"≤ 24 uur geleden",
  verouderd:"Verouderd"
};

async function researchRequest(path, options={}) {
  let response;
  try {response=await fetch(path, options);} catch (_) {
    throw Error("Lokale server niet bereikbaar");
  }
  const payload=await response.json();
  if(!response.ok) throw Error(payload.error || "Verzoek mislukt");
  return payload;
}

function researchMessage(message, error=false) {
  const node=rEl("research-message");
  node.textContent=message;
  node.classList.toggle("research-error",error);
}

function researchStatus() {
  const target=rEl("research-statistics");
  target.replaceChildren();
  if (!researchState.status) return;
  const status=researchState.status;
  for(const source of ["prophitbet","oddsharvester","prediict"]) {
    const data=status.sources.find(x=>x.source===source);
    const chip=document.createElement("span");
    chip.className="research-chip";
    chip.textContent=SOURCE_NAMES[source]+": "+(data?data.files:0)+" bestanden";
    target.append(chip);
  }
  const count=document.createElement("span");
  count.className="research-chip";
  count.textContent=status.predictions+" modelkansen · "+status.odds+" quoteringen";
  target.append(count);
}

function researchRender() {
  const tbody=rEl("research-results");
  tbody.replaceChildren();
  const futureOnly=rEl("research-only-future").checked;
  const recentOnly=rEl("research-only-recent").checked;
  const today=new Date().toISOString().slice(0,10);
  let records=researchState.rows.filter(r=>
    (!futureOnly || (r.kickoff_date && r.kickoff_date >= today)) &&
    (!recentOnly || (r.freshness === "max_24_uur_oud" &&
      r.kickoff_date && r.kickoff_date >= today))
  );
  if (!records.length) {
    const tr=document.createElement("tr"), td=document.createElement("td");
    td.colSpan=7;
    td.textContent=researchState.rows.length
      ? "Geen resultaten voor dit filter. Controleer data, opnametijd en eventuele dubbele teamnamen."
      : "Nog geen gekoppelde voorspellingen en prijzen. Exporteer CSV/JSON vanuit de forks en klik op Bronbestanden inlezen.";
    tr.append(td);
    tbody.append(tr);
    return;
  }
  for(const rec of records) {
    const tr=document.createElement("tr");
    const matchup=document.createElement("td");
    const names=document.createElement("strong");
    names.textContent=rec.home_team+" – "+rec.away_team;
    const day=document.createElement("small");
    day.textContent=rec.kickoff_date||"Wedstrijddatum onbekend";
    matchup.append(names,document.createElement("br"),day);
    tr.append(matchup);
    const fields=[
      MARKET_NAMES[rec.market]||rec.market,
      rPct(rec.probability),
      rNum(rec.decimal_odds),
      (rec.expected_roi>0?"+":"")+rPct(rec.expected_roi),
      AGE_TEXT[rec.freshness]||"Onbekend"
    ];
    fields.forEach((value,i)=>{
      const td=document.createElement("td");
      td.textContent=value;
      if(i===3) td.className=rec.expected_roi>0?"research-positive":"research-negative";
      if(i===4) td.className="research-age";
      tr.append(td);
    });
    const source=document.createElement("td"), major=document.createElement("strong");
    major.textContent=(SOURCE_NAMES[rec.prediction_source]||rec.prediction_source)+
      " / "+rec.bookmaker;
    const small=document.createElement("small");
    small.textContent="Model: "+rec.prediction_file+" · Odds: "+rec.odds_file;
    source.append(major,document.createElement("br"),small);
    tr.append(source);
    tbody.append(tr);
  }
}

async function researchLoad() {
  try {
    const [status,opps]=await Promise.all([
      researchRequest("/api/research/status"),
      researchRequest("/api/research/opportunities")
    ]);
    researchState.status=status;
    researchState.rows=opps.opportunities;
    researchStatus();
    researchRender();
    if(!researchState.rows.length) {
      researchMessage("Nog geen vergelijkbare 1X2-modelkansen en bookmakerprijzen ingelezen. " +
        "Dit is geen fout als je nog geen exports hebt.");
    }else{
      researchMessage("Onderzoeksresultaten: "+opps.total_pairs+
        " combinaties van modelkans en prijs. Geen winstgarantie.");
    }
  } catch(e){researchMessage(e.message,true);}
}

async function researchImport() {
  if(researchState.busy) return;
  researchState.busy=true;
  const button=rEl("research-refresh");
  button.disabled=true;
  button.textContent="Bronbestanden controleren…";
  researchMessage("Lokale exportmappen worden ingelezen…");
  try {
    const result=await researchRequest("/api/research/imports/scan",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:"{}"
    });
    await researchLoad();
    researchMessage(result.files_imported+" nieuwe bestanden ingelezen, "+
      result.observations_imported+" prijs- en kansgegevens verwerkt. "+
      (result.errors.length?result.errors.length+" bestanden konden niet worden ingelezen.":"")+
      " Eerder ingelezen bestanden zijn niet dubbel verwerkt.",
      result.errors.length>0);
  } catch(e){researchMessage(e.message,true);}
  finally {
    researchState.busy=false;
    button.disabled=false;
    button.textContent="↻ Bronbestanden inlezen";
  }
}

function researchInit() {
  rEl("research-refresh").addEventListener("click",researchImport);
  rEl("research-only-future").addEventListener("change",researchRender);
  rEl("research-only-recent").addEventListener("change",researchRender);
  researchLoad();
}

document.addEventListener("DOMContentLoaded",researchInit);
