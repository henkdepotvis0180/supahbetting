"use strict";
/* Local serious research front page. Sources/models only; no fabricated fixtures. */
(() => {
  const $=id=>document.getElementById(id);
  const el=(tag,value,klass)=>{
    const n=document.createElement(tag);
    if(value!==undefined)n.textContent=String(value);
    if(klass)n.className=klass;
    return n;
  };
  const nameOf={"nl.1":"Eredivisie","en.1":"Premier League",
    "de.1":"Bundesliga","es.1":"La Liga","it.1":"Serie A",
    "fr.1":"Ligue 1"};
  const providerLabel={"football-data":"football-data.org",
    "sportsdb":"TheSportsDB","openliga":"OpenLigaDB",
    "knvb":"KNVB – officieel Eredivisie-programma"};
  let dataset=null;
  const pct=v=>typeof v==="number" && Number.isFinite(v)
    ?new Intl.NumberFormat("nl-BE",{style:"percent",minimumFractionDigits:1,
      maximumFractionDigits:1}).format(v):"—";
  const number=v=>typeof v==="number" && Number.isFinite(v)
    ?new Intl.NumberFormat("nl-BE",{maximumFractionDigits:2}).format(v):"—";
  function dateLabel(iso){
    if(!iso)return "Tijdstip onbekend";
    const dt=new Date(iso);
    return Number.isFinite(dt.getTime())
      ?new Intl.DateTimeFormat("nl-BE",{timeZone:"Europe/Brussels",
         day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}).format(dt)
      :"Tijdstip onbekend";
  }
  function dayInBrussels(iso){
    const dt=new Date(iso);
    return Number.isFinite(dt.getTime())?new Intl.DateTimeFormat("sv-SE",{
      timeZone:"Europe/Brussels",year:"numeric",month:"2-digit",day:"2-digit"
    }).format(dt):null;
  }
  const today=()=>dayInBrussels(new Date().toISOString());
  const spanDays=(date,base)=>Math.round(
    (Date.parse(date+"T12:00:00Z")-Date.parse(base+"T12:00:00Z"))/86400000
  );
  function fact(label,value){
    const n=el("div",undefined,"fixture-metric");
    n.append(el("span",label),el("strong",value));
    return n;
  }
  function historyResults(rows){
    const target=$("research-recent-results");
    const count=$("research-recent-count");
    if(!target)return;
    const dedup=Array.isArray(rows)?rows.filter(x=>x.league in nameOf):[];
    if(count) count.textContent="("+dedup.length+")";
    if(!dedup.length){
      target.replaceChildren(el("p",
        "Er zijn geen recente eindstanden door de actieve bronnen bevestigd. "+
        "Dit betekent niet dat er gisteren geen wedstrijden gespeeld zijn.","fixture-empty"));
      return;
    }
    const table=el("div",undefined,"fixture-recent-list");
    for(const row of dedup.slice(0,30)){
      const item=el("div",undefined,"fixture-recent-row");
      item.append(
        el("small",row.date+" · "+(nameOf[row.league]||row.league)),
        el("span",row.home+" – "+row.away),
        el("strong",row.hg+" – "+row.ag)
      );
      table.append(item);
    }
    target.replaceChildren(table);
  }
  function decoratePrediction(card,match){
    const prediction=match.prediction;
    if(!prediction){
      card.append(el("p",match.prediction_unavailable_reason||
         "Deze wedstrijd is niet betrouwbaar genoeg gekoppeld aan het model.",
         "fixture-warning"));
      return;
    }
    const preference=match.model_preference;
    const tag=el("div",undefined,"fixture-model-choice");
    tag.append(el("strong",preference?.label||"Experimentele modelkansen"));
    tag.append(el("span",preference?.category||"Researchmodel; nog niet prospectief gevalideerd"));
    if(preference?.eligible_for_highlight)tag.classList.add("fixture-model-choice-selected");
    card.append(tag);
    const probs=el("div",undefined,"fixture-chances");
    probs.append(
      fact("Thuiswinst",pct(prediction.probabilities.home)),
      fact("Gelijk",pct(prediction.probabilities.draw)),
      fact("Uitwinst",pct(prediction.probabilities.away))
    );
    card.append(probs);
    card.append(el("p",
      "Goalschatting: "+number(prediction.expected_goals_home)+" – "+
      number(prediction.expected_goals_away)+
      " · model "+prediction.model_version+
      " · uitslagen t/m "+prediction.data_through,
      "fixture-details"));
    const details=el("details",undefined,"fixture-why");
    details.append(el("summary","Waarom kiest het model hiervoor?"));
    const list=el("ul");
    for(const reason of preference?.reasons||[])list.append(el("li",reason));
    details.append(list);
    details.append(el("p",preference?.risk_note||prediction.data_warning,"fixture-warning"));
    card.append(details);
    if(prediction.data_warning && !preference?.eligible_for_highlight){
      card.append(el("p",prediction.data_warning,"fixture-warning"));
    }
  }
  function draw(){
    const target=$("research-fixture-list");
    if(!target)return;
    if(!dataset?.available){
      target.replaceChildren(el("p",
        dataset?.message||
        "De monitor heeft nog geen actuele wedstrijden opgehaald. Controleer het bronvenster.",
        "fixture-empty"));
      return;
    }
    const league=$("research-fixture-league").value;
    const days=Number($("research-fixture-range").value);
    const type=$("research-fixture-filter").value;
    const baseline=today();
    const selected=(dataset.fixtures||[])
      .filter(m=>{
        if(!(m.league in nameOf)||!(m.provider in providerLabel)||
           !m.source_confirmed||m.status!=="scheduled")return false;
        const local=m.kickoff?dayInBrussels(m.kickoff):m.date;
        if(!local)return false;
        const d=spanDays(local,baseline);
        return d>=0 && d<=days &&
          (league==="all"||m.league===league) &&
          (type!=="predicted"||Boolean(m.prediction)) &&
          (type!=="confirmed"||m.source_confirmed);
      });
    const cards=[];
    for(const match of selected.slice(0,80)){
      const card=el("article",undefined,"panel fixture-card");
      const header=el("div",undefined,"fixture-card-top");
      header.append(el("span",nameOf[match.league]||match.league),
                    el("span",dateLabel(match.kickoff)));
      card.append(header,el("h3",match.home+" – "+match.away));
      const source=el("p",undefined,"fixture-provider");
      source.append("Bron: "+(providerLabel[match.provider]||match.provider)+" · ");
      const anchor=el("a","Bron bekijken");
      anchor.href=match.source_url;
      anchor.target="_blank";anchor.rel="noopener noreferrer";
      source.append(anchor);
      if(match.provider==="knvb" && match.source_method==="dated_official_snapshot"){
        source.append(" · Officieel programma, laatst gecontroleerd 17 oktober 2026");
      }
      card.append(source);
      decoratePrediction(card,match);
      cards.push(card);
    }
    if(!cards.length)target.replaceChildren(el("p",
      "Geen geverifieerde toekomstige wedstrijden voor dit filter. "+
      "De gratis bronnen tonen mogelijk niet het hele speelschema; "+
      "controleer de bronstatus of gebruik een API-abonnement met ruimere dekking.",
      "fixture-empty"));
    else target.replaceChildren(...cards);
    const stats=$("research-fixture-summary");
    stats.replaceChildren(
      fact("Bevestigde komende duels",selected.length),
      fact("Met experimentele kans",selected.filter(f=>Boolean(f.prediction)).length),
      fact("Modelvoorkeur met voldoende actuele data",
        selected.filter(f=>f.model_preference?.eligible_for_highlight).length)
    );
    const note=$("research-fixture-status");
    const last=dataset.updated_at_utc?dateLabel(dataset.updated_at_utc):"onbekend";
    const registered=dataset.prospective_evaluation?.total_pre_match_snapshots??0;
    const graded=dataset.prospective_evaluation?.graded_total??0;
    note.replaceChildren(
      el("strong","Laatste broncontrole: "+last),
      el("span"," · Vooraf opgeslagen voorspellingen: "+registered),
      el("span"," · Echt beoordeeld: "+graded)
    );
    const eredivisie=dataset.nl_result_source||{};
    if(eredivisie.status && eredivisie.status!=="not_checked"){
      const labels={
        loaded:"Eredivisie API gecontroleerd",
        no_api_key:"Eredivisie: API-sleutel ontbreekt",
        subscription_required:"Eredivisie: jouw API-abonnement geeft geen DED-toegang",
        rate_limited:"Eredivisie: API-verzoeklimiet bereikt",
        stale_api_cache:"Eredivisie: API-bron tijdelijk verouderd",
        no_inventory:"Eredivisie: historische trainingsbasis ontbreekt",
        no_model:"Eredivisie: model ontbreekt",
        error:"Eredivisie: update kon niet worden gevalideerd",
        api_http_error:"Eredivisie: HTTP-bronfout"
      };
      const label=labels[eredivisie.status]||"Eredivisie: "+eredivisie.status;
      note.append(el("p",label+
        (eredivisie.model_last_score_date?
         " · bijgewerkte modeldata t/m "+eredivisie.model_last_score_date:"")+
        (eredivisie.new_confirmed?
         " · nieuwe uitslagen "+eredivisie.new_confirmed:"")+
        (eredivisie.http_status?" · HTTP "+eredivisie.http_status:""),
        eredivisie.status==="loaded"?"fixture-info":"fixture-warning"));
    }
    const csv=dataset.nl_manual_history||{};
    if(csv.matches){
      note.append(el("p","Eredivisie historische CSV: "+csv.matches+
        " wedstrijden uit "+csv.seasons+" seizoenen (uitsluitend lokaal).",
        "fixture-info"));
    }
    const update=dataset.local_data_update;
    if(update?.added)note.append(el("p",
      update.added+" nieuw bevestigde uitslagen zijn lokaal verwerkt."+
      (update.local_retrained?" Het model is opnieuw berekend.":""),
      "fixture-info"));
    if(dataset.provider_warnings?.length)note.append(el("p",
      "Bronbeperkingen: "+dataset.provider_warnings.slice(0,3).join(" · ")+
      (dataset.provider_warnings.length>3?" (meer in monitor)":""),"fixture-warning"));
    historyResults(dataset.recent_results);
  }
  async function readiness(){
    const host=$("research-readiness");
    try{
      const resp=await fetch("/api/research/readiness",{cache:"no-store"});
      if(!resp.ok)throw Error("HTTP "+resp.status);
      const m=await resp.json();
      host.classList.toggle("research-readiness-degraded",m.level!=="ready");
      const missingTen=Object.entries(m.league_history||{})
        .filter(([,info])=>!info.at_least_10_seasons)
        .map(([code,info])=>(nameOf[code]||code)+": "+info.season_count+" seizoenen");
      host.replaceChildren(
        el("strong","Modelstatus: "+m.level.toUpperCase()+" · "+(m.model_version||"ontbreekt")),
        el("span"," · Historische dekking: "+(m.leagues_with_10_seasons??0)+"/"+
          (m.active_league_count??6)+" competities met 10+ seizoenen"),
        el("span"," · Eredivisie-model t/m: "+(m.nl_model_data_through||"onbekend")),
        el("span"," · Overige modeldata t/m: "+(m.model_data_through||"onbekend")),
        el("p",m.warn+" · Geen aangetoonde winst tegen bookmakers."),
        ...(missingTen.length?[el("p","Nog geen 10 seizoenen voor: "+missingTen.join("; "),
          "fixture-warning")]:[])
      );
    }catch(err){
      host.replaceChildren(el("p","Modelcontrole niet bereikbaar: "+err.message,"fixture-warning"));
    }
  }
  async function refresh(){
    try{
      const resp=await fetch("/api/research/upcoming",{cache:"no-store"});
      if(!resp.ok)throw Error("HTTP "+resp.status);
      dataset=await resp.json();
      draw();
    }catch(err){
      $("research-fixture-list").replaceChildren(el("p",
        "Lokale wedstrijdgegevens niet beschikbaar: "+err.message,"fixture-warning"));
    }
    await readiness();
  }
  document.addEventListener("DOMContentLoaded",()=>{
    if(!$("research-fixture-list"))return;
    for(const [key,label] of Object.entries(nameOf)){
      const option=el("option",label); option.value=key;
      $("research-fixture-league").append(option);
    }
    for(const id of ["research-fixture-league","research-fixture-range","research-fixture-filter"]){
      $(id).addEventListener("change",draw);
    }
    $("research-fixture-refresh").addEventListener("click",refresh);
    refresh();
    setInterval(refresh,60_000);
  });
})();
