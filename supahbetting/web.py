"""Local-only Dutch dashboard for manual football odds research.

No bookmaker scraping, account access, or real-money betting.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path
import html
import json
from .core import match_probabilities, expected_value, no_vig_probabilities

MAX_BODY = 16_384
MARKETS = ("home", "draw", "away")

PAGE = """<!doctype html>
<html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SupahBetting</title>
<style>
:root{font-family:system-ui,Arial;background:#0b1220;color:#e5e7eb}
body{max-width:960px;margin:auto;padding:22px}h1{color:#70e1ac}h2{margin-top:0}
section{background:#172338;padding:20px;border-radius:14px;margin:18px 0}
label{display:block;margin:12px 0}input{padding:10px;background:#0c1525;color:white;border:1px solid #56647a;border-radius:6px;width:95%;max-width:320px}
button{background:#4bd39a;border:0;padding:12px 18px;border-radius:7px;cursor:pointer;font-weight:700}
table{border-collapse:collapse;width:100%;margin-top:14px}th,td{text-align:left;padding:10px;border-bottom:1px solid #39475a}
small,.muted{color:#a9b7cb}.good{color:#69e9a2}.bad{color:#ffb0a5}
</style></head><body>
<h1>⚽ SupahBetting</h1><p class="muted">Onderzoeksdashboard · handmatige odds · geen echte inzetten</p>
<section><h2>Wedstrijd analyseren</h2>
<label>Wedstrijd <input id="event" value="Thuis - Uit"></label>
<label>Verwachte goals thuis (xG) <input id="hxg" type="number" min="0" max="15" step=".1" value="1.6"></label>
<label>Verwachte goals uit (xG) <input id="axg" type="number" min="0" max="15" step=".1" value="1.1"></label>
<p>Decimale bookmakerquoteringen (1X2)</p>
<label>Thuis <input id="oh" type="number" min="1.01" step=".01" value="2.10"></label>
<label>Gelijk <input id="od" type="number" min="1.01" step=".01" value="3.40"></label>
<label>Uit <input id="oa" type="number" min="1.01" step=".01" value="3.60"></label>
<button onclick="analyze()">Bereken kansen en value</button>
<p id="error" class="bad" role="alert"></p><div id="result"></div>
</section>
<section><h2>Paper trading</h2><p>Leg een gesimuleerde selectie vast met een vaste fictieve inzet van €1.</p>
<div id="bets"></div></section>
<section><h2>Belangrijke beperkingen</h2>
<p>De Poisson-berekening is een basismodel. Handmatig ingevoerde xG-cijfers zijn geen getrainde voorspellingen. Odds zijn niet live. Een positieve berekende EV bewijst geen winstgevendheid.</p>
</section>
<script>
const $=id=>document.getElementById(id);
let latest=null;
async function request(path, options={}) {
 const r=await fetch(path,options);const j=await r.json();
 if(!r.ok)throw Error(j.error||'Verzoek mislukt');return j;
}
const pct=x=>(x*100).toFixed(1)+'%';
async function analyze(){
 $('error').textContent='';$('result').replaceChildren();
 try{
  const payload={event:$('event').value,home_xg:Number($('hxg').value),away_xg:Number($('axg').value),
   odds:{home:Number($('oh').value),draw:Number($('od').value),away:Number($('oa').value)}};
  latest=await request('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const table=document.createElement('table');
  table.innerHTML='<thead><tr><th>Uitkomst</th><th>Modelkans</th><th>Fair odds</th><th>EV</th><th>Actie</th></tr></thead>';
  const tbody=document.createElement('tbody');
  for(const key of ['home','draw','away']){
   const row=latest.markets[key];const tr=document.createElement('tr');
   for(const value of [({home:'Thuis',draw:'Gelijk',away:'Uit'})[key],pct(row.probability),row.fair_odds.toFixed(2),pct(row.expected_roi)]){
    const td=document.createElement('td');td.textContent=value;tr.append(td);
   }
   tr.children[3].className=row.expected_roi>0?'good':'bad';
   const td=document.createElement('td'),btn=document.createElement('button');btn.textContent='Simuleer €1';
   btn.onclick=()=>paper(key);td.append(btn);tr.append(td);tbody.append(tr);
  }
  table.append(tbody);$('result').append(table);
  const p=document.createElement('p');p.textContent='Boekmakermarge: '+pct(latest.bookmaker_margin);$('result').append(p);
 }catch(e){$('error').textContent=e.message;}
}
async function paper(market){
 try{await request('/api/paper',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({event:latest.event,market,probability:latest.markets[market].probability,
 decimal_odds:latest.markets[market].decimal_odds,stake:1})});await refresh();}
 catch(e){$('error').textContent=e.message;}
}
async function refresh(){
 try{const data=await request('/api/paper');const box=$('bets');box.replaceChildren();
 const p=document.createElement('p');p.textContent='Gesimuleerde inzetten: '+data.count+
 ' | Totaal ingezet: €'+data.total_staked.toFixed(2)+' | Verwachte nettowaarde (model): €'+data.expected_profit.toFixed(2);
 box.append(p);const list=document.createElement('ul');
 for(const item of data.recent){const li=document.createElement('li');li.textContent=item.event+' · '+item.market+
 ' · odds '+item.decimal_odds+' · inzet €'+item.stake;list.append(li);}box.append(list);
 }catch(e){$('bets').textContent=e.message;}
}
refresh();
</script></body></html>"""


def analyze(payload):
    home_xg, away_xg = float(payload["home_xg"]), float(payload["away_xg"])
    if not 0 <= home_xg <= 15 or not 0 <= away_xg <= 15:
        raise ValueError("xG moet tussen 0 en 15 liggen")
    odds = {key: float(payload["odds"][key]) for key in MARKETS}
    if any(not 1.0 < value <= 1000 for value in odds.values()):
        raise ValueError("Odds moeten tussen 1 en 1000 liggen")
    probs = match_probabilities(home_xg, away_xg)
    fair = no_vig_probabilities(odds)
    return {"event": str(payload.get("event", "Wedstrijd"))[:120],
            "bookmaker_margin": sum(1 / x for x in odds.values()) - 1,
            "markets": {key: {"probability": probs[key], "decimal_odds": odds[key],
                              "fair_odds": 1 / probs[key] if probs[key] else None,
                              "no_vig_market_probability": fair[key],
                              "expected_roi": expected_value(probs[key], odds[key])}
                        for key in MARKETS}}


def paper_summary(path):
    items = []
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return {"count": len(items), "total_staked": sum(x["stake"] for x in items),
            "expected_profit": sum(x["stake"] * x["expected_roi"] for x in items),
            "recent": items[-15:][::-1]}


def make_handler(data_file):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, code, obj):
            data = json.dumps(obj, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            route = urlparse(self.path).path
            if route == "/":
                data = PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif route == "/api/paper":
                self.respond(200, paper_summary(data_file))
            else:
                self.respond(404, {"error": "Niet gevonden"})

        def do_POST(self):
            route = urlparse(self.path).path
            if route not in ("/api/analyze", "/api/paper"):
                return self.respond(404, {"error": "Niet gevonden"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > MAX_BODY:
                    raise ValueError("Ongeldige berichtgrootte")
                payload = json.loads(self.rfile.read(size))
                if route == "/api/analyze":
                    return self.respond(200, analyze(payload))
                event = str(payload["event"]).strip()[:120]
                market = str(payload["market"])
                probability = float(payload["probability"])
                odds = float(payload["decimal_odds"])
                stake = float(payload["stake"])
                if not event or market not in MARKETS or not 0 <= probability <= 1 or not 1 < odds <= 1000 or not 0 < stake <= 1000:
                    raise ValueError("Ongeldige paper-betgegevens")
                record = {"event": event, "market": market, "probability": probability,
                          "decimal_odds": odds, "stake": stake,
                          "expected_roi": expected_value(probability, odds), "status": "unsettled"}
                with data_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, allow_nan=False) + "\n")
                return self.respond(201, record)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError, OverflowError) as exc:
                return self.respond(400, {"error": str(exc)})

    return Handler


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SupahBetting lokaal dashboard")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-file", type=Path, default=Path("paper_bets.jsonl"))
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.data_file))
    print(f"SupahBetting draait op http://127.0.0.1:{args.port} (Ctrl+C om te stoppen)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
