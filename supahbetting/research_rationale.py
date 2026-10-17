"""Explain model choices from ACTUAL Poisson model inputs, not player rumors.

A 'model favorite' is not a positive-value bet.  Until independently
verified closing odds and prospective results exist, no ROI/edge is asserted.
"""
from __future__ import annotations

from datetime import date, datetime, timezone


LABELS={"home":"Thuisploeg","draw":"Gelijkspel","away":"Uitploeg"}


def reasoning(model, predicted, *, now=None):
    now=now or datetime.now(timezone.utc)
    probs=predicted["probabilities"]
    ranked=sorted(probs.items(),key=lambda pair:pair[1],reverse=True)
    outcome,p=ranked[0]
    margin=p-ranked[1][1]
    is_clear=p>=0.43 and margin>=0.07
    league=predicted["league"]
    stats=model["leagues"][league]
    home=predicted["home_team"]
    away=predicted["away_team"]
    host=stats["teams"][home]
    guest=stats["teams"][away]
    evidence=[
        (
            "Doelpuntenraming uit eerdere competitiewedstrijden: "
            +str(predicted["expected_goals_home"])+" voor "+home+" tegenover "
            +str(predicted["expected_goals_away"])+" voor "+away+"."
        )
    ]
    league_home=stats.get("home_goal_mean",1.33)
    league_away=stats.get("away_goal_mean",1.18)
    if league_home>league_away*1.08:
        evidence.append(
            "Competitiegemiddelde: thuisclubs scoren historisch "+
            str(round(league_home,2))+" tegenover "+str(round(league_away,2))+
            " doelpunten bij uitclubs."
        )
    if host["appearances"]>=10 and guest["appearances"]>=10:
        if host["attack"]>guest["attack"]*1.1:
            evidence.append(
                "Aanvalsindicator uit gespeelde wedstrijden ligt hoger voor "+
                home+"; dit is op basis van goals, niet van schoten of xG."
            )
        if host["defence"]<guest["defence"]*.9:
            evidence.append(
                "De defensieve indicator van "+home+" is gunstiger: gemiddeld "
                "minder doelpunten tegen in het historische ratingsysteem."
            )
        if guest["attack"]>host["attack"]*1.1:
            evidence.append(
                "Aanvalsindicator uit gespeelde wedstrijden ligt hoger voor "+
                away+"; dit is geen informatie over de verwachte opstelling."
            )
        if guest["defence"]<host["defence"]*.9:
            evidence.append(
                "De defensieve indicator van "+away+" is gunstiger in het "
                "historische ratingsysteem."
            )
    age=predicted.get("model_age_days")
    is_recent=isinstance(age,int) and age<14
    enough_matches=min(host["appearances"],guest["appearances"])>=12
    sufficiently_separated=margin>=0.12 and p>=0.5
    # Do not treat any favorite as a betting-value recommendation.
    verdict=(
        "Geen duidelijke modelvoorkeur" if not is_clear else
        home+" heeft volgens het model de hoogste kans" if outcome=="home" else
        away+" heeft volgens het model de hoogste kans" if outcome=="away" else
        "Gelijkspel heeft volgens het model de hoogste kans"
    )
    category=(
        "onvoldoende recente gegevens" if not is_recent else
        "geringe historische onderbouwing" if not enough_matches else
        "krap verschil" if not is_clear else
        "redelijke modelvoorkeur, nog niet prospectief bewezen"
        if sufficiently_separated else
        "voorzichtige modelvoorkeur"
    )
    return {
        "outcome":outcome if is_clear else None,
        "label":verdict,
        "probability":round(p,6),
        "runner_up_probability":round(ranked[1][1],6),
        "margin":round(margin,6),
        "category":category,
        "reasons":evidence[:4],
        "eligible_for_highlight":is_clear and is_recent and enough_matches,
        "model_reasons_only":True,
        "risk_note":(
            "Niet gebruiken als bewezen bettip: geen actuele bookmakerprijzen, "
            "opstellingen, blessure-info of onafhankelijke positieve ROI. "
            "Historische modelgegevens t/m "+str(predicted.get("data_through"))+"."
        ),
    }
