"use strict";
/* Pretrained real historical match scores, not live bookmaker odds or shot xG. */
const tEl = id => document.getElementById(id);
const tPct = x => new Intl.NumberFormat("nl-NL",{
  style:"percent",minimumFractionDigits:1,maximumFractionDigits:1
}).format(x);
const tNum = x => new Intl.NumberFormat("nl-NL",{
  minimumFractionDigits:2,maximumFractionDigits:2
}).format(x);

let lastPrediction = null;

async function requestTrained(path, payload=null) {
  const opts = {};
  if (payload !== null) {
    opts.method="POST";
    opts.headers={"Content-Type":"application/json"};
    opts.body=JSON.stringify(payload);
  }
  let response;
  try{response=await fetch(path,opts);}
  catch(_error){throw Error("Lokale SupahBetting-server niet bereikbaar");}
  const result=await response.json();
  if(!response.ok)throw Error(result.error||"Model kon niet worden geladen");
  return result;
}

function statTile(label,value,caption) {
  const box=document.createElement("div");
  box.className="panel trained-stat";
  const a=document.createElement("span"),b=document.createElement("strong"),
    c=document.createElement("small");
  a.textContent=label;b.textContent=value;c.textContent=caption;
  box.append(a,b,c);
  return box;
}

async function trainedLoadStatus() {
  const root=tEl("trained-stats");
  try{
    const status=await requestTrained("/api/trained/status");
    root.replaceChildren();
    if(!status.available){
      root.append(statTile("Modelstatus","Niet aanwezig",
        "Start train_model.bat of download de volledige release"));
      return;
    }
    const test=status.evaluation.test, validation=status.evaluation.validation;
    root.append(
      statTile("Echte trainingswedstrijden",status.training_matches.toLocaleString("nl-NL"),
        "OpenFootball · CC0 · 7 competities"),
      statTile("Extra historische training",
        (status.added_older_results||0).toLocaleString("nl-NL")+" wedstrijden",
        "2017–2020 · extra historische context, niet per se betere voorspellingen"),
      statTile("Chronologische test",""+test.matches.toLocaleString("nl-NL"),
        "2025/26 · seizoensbestanden deels onvolledig"),
      statTile("Brier-score model",tNum(test.model_brier),
        "Lager is beter · eenvoudige referentie: "+tNum(test.reference_brier)),
      statTile("Validatie 2024/25",tNum(validation.model_logloss),
        "Log loss model · eenvoudige referentie: "+tNum(validation.reference_logloss)),
      statTile("Extra toets 2026/27",
        status.evaluation.prospective_2026_27
          ? status.evaluation.prospective_2026_27.matches.toLocaleString("nl-NL")+" wedstrijden"
          : "Niet beschikbaar",
        "Afgeronde wedstrijden t/m "+(status.last_observed_result_date||"onbekend")+
        " · kleine steekproef, geen bookmakersvalidatie")
    );
  }catch(e){
    root.replaceChildren(statTile("Model niet beschikbaar","Controleer server",e.message));
  }
}

function renderPrediction(result) {
  const root=tEl("trained-result");
  root.replaceChildren();
  const heading=document.createElement("h3");
  heading.textContent=result.home_team+" – "+result.away_team;
  const info=document.createElement("p");
  info.textContent="Geleerde doelpuntverwachting: thuis "+
    tNum(result.expected_goals_home)+" · uit "+tNum(result.expected_goals_away);
  const grid=document.createElement("div");grid.className="trained-prob-grid";
  for(const [key,title] of [["home","Thuiswinst (1)"],["draw","Gelijk (X)"],["away","Uitwinst (2)"]]){
    const box=document.createElement("div");box.className="trained-prob";
    const label=document.createElement("span");label.textContent=title;
    const value=document.createElement("strong");value.textContent=tPct(result.probabilities[key]);
    box.append(label,value);grid.append(box);
  }
  const conf=document.createElement("p");
  conf.className="trained-extra";
  conf.textContent="Modelzekerheid: "+result.confidence+
    " · historische gegevens t/m "+result.data_through+
    " · modelversie "+result.model_version;
  const warning=document.createElement("p");warning.className="trained-warning";
  warning.textContent=result.disclaimer;
  const btn=document.createElement("button");
  btn.type="button";btn.className="btn btn-quiet";
  btn.textContent="Gebruik modeldoelpunten in handmatige analyse";
  btn.addEventListener("click",()=>{
    fillAnalysis(result.home_team,result.away_team,result,
      "Getraind basismodel v"+result.model_version);
  });
  root.append(heading,info,grid,conf,warning,btn);
}

function fillAnalysis(home,away,result,source) {
  const editor=tEl("match-editor"),form=tEl("match-form");
  editor.open=true;
  form.elements.namedItem("home_team").value=home;
  form.elements.namedItem("away_team").value=away;
  form.elements.namedItem("home_xg").value=String(result.expected_goals_home);
  form.elements.namedItem("away_xg").value=String(result.expected_goals_away);
  form.elements.namedItem("source").value=source;
  // Critically: never synthesize bookmaker odds.
  for(const name of ["odds_home","odds_draw","odds_away"]){
    form.elements.namedItem(name).value="";
  }
  editor.scrollIntoView({behavior:"smooth",block:"start"});
  form.elements.namedItem("odds_home").focus({preventScroll:true});
}

async function trainedPredictFromForm(event) {
  event.preventDefault();
  const root=tEl("trained-result");
  root.textContent="Model berekent kansen…";
  try{
    const result=await requestTrained("/api/trained/predict",{
      league:tEl("trained-league").value,
      home_team:tEl("trained-home").value,
      away_team:tEl("trained-away").value
    });
    lastPrediction=result;
    renderPrediction(result);
  }catch(e){
    root.textContent="Geen getrainde voorspelling beschikbaar: "+e.message;
  }
}

/* Called only on a user click in a scheduled live-match dialog. */
async function applyTrainedFromLive(match,provider,league) {
  const result=await requestTrained("/api/trained/predict",{
    provider,league,home_team:match.home_team,away_team:match.away_team
  });
  fillAnalysis(match.home_team,match.away_team,result,
    "Eigen doelpuntenmodel v"+result.model_version+" (historische scores)");
  return result;
}

window.SupahTrained={applyFromLive:applyTrainedFromLive};

document.addEventListener("DOMContentLoaded",()=>{
  tEl("trained-form").addEventListener("submit",trainedPredictFromForm);
  trainedLoadStatus();
});
