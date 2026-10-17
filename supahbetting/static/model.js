"use strict";
/* Local, research-only use of a real pretrained 1X2 model.
 * No odds, bookmaker accounts, wager sizing, or profit claims.
 */
const baselineText = id => document.getElementById(id);
const asPercent = value => (Number(value)*100).toLocaleString("nl-NL", {
  maximumFractionDigits: 1, minimumFractionDigits: 1
}) + "%";

async function baselineStatus() {
  const node=baselineText("baseline-status");
  if(!node) return;
  try {
    const res=await fetch("/api/model/status");
    const data=await res.json();
    node.replaceChildren();
    const heading=document.createElement("strong");
    heading.textContent=data.available?"Voorgetraind model beschikbaar":"Model nog niet beschikbaar";
    node.append(heading);
    const paragraph=document.createElement("p");
    if(!data.available) {
      paragraph.textContent=data.reason||"Download de nieuwste versie met het getrainde model.";
      node.append(paragraph);
      return;
    }
    const metrics=data.metrics && data.metrics.holdout;
    const period=data.trained_until||"onbekend";
    const count=data.training_matches||0;
    paragraph.textContent="Historische wedstrijden: "+count.toLocaleString("nl-NL")+
      ". Meest recente uitslag in trainingsdata: "+period+
      ". "+(metrics?"Onafhankelijke tijdstest: "+asPercent(metrics.accuracy)+
      " nauwkeurigheid op "+metrics.games+" wedstrijden.":"");
    node.append(paragraph);
    const note=document.createElement("small");
    note.textContent="Let op: de dataset kan jaren oud zijn; dit model is niet bewezen winstgevend. Nieuwe uitslagen zijn nodig om de vorm te actualiseren.";
    node.append(note);
  } catch {
    node.textContent="Modelstatus tijdelijk niet bereikbaar.";
  }
}

window.supahPredictMatch=async function(detail, league) {
  const output=baselineText("live-model-result");
  const button=baselineText("live-model-predict");
  if(!output||!button) return;
  button.disabled=true;
  output.textContent="Modelkansen berekenen…";
  try {
    const response=await fetch("/api/model/predict",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        home_team:detail.home_team,
        away_team:detail.away_team,
        league:String(league||"")
      })
    });
    const result=await response.json();
    if(!response.ok) throw new Error(result.error||"Model is niet beschikbaar");
    // User may have already closed or switched fixtures.
    if(!output.isConnected) return;
    output.replaceChildren();
    const probs=result.probabilities||{};
    const outcomes=[
      ["Thuiswinst",probs.home],["Gelijkspel",probs.draw],["Uitwinst",probs.away]
    ];
    for(const [label,value] of outcomes) {
      const row=document.createElement("div");
      row.className="baseline-probability";
      const name=document.createElement("span");
      name.textContent=label;
      const number=document.createElement("strong");
      number.textContent=asPercent(value);
      row.append(name,number);
      output.append(row);
    }
    const title=document.createElement("small");
    title.textContent="Bron: getraind Elo-/vormmodel tot "+result.model_trained_until+
      ". Historische testresultaten zijn geen toekomstgarantie.";
    output.append(title);
    const warning=document.createElement("p");
    warning.className="model-warning";
    warning.textContent=result.warning||
      "Geen bookmakerodds gekoppeld en geen bewijs van een positief rendement.";
    output.append(warning);
  } catch(error) {
    if(output.isConnected) output.textContent="Modelvoorspelling niet beschikbaar: "+error.message;
  } finally {
    if(button.isConnected) button.disabled=false;
  }
};

document.addEventListener("DOMContentLoaded",baselineStatus);
