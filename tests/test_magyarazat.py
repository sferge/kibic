"""
Licitmagyarázat: a bridge/explain CSAK a megállapodást adja (kéz nélkül),
a kibic/magyaraz a tanításhoz a kézzel együtt mindent.
"""
import json

import pytest

from kibic.impex.rendszer_yaml import forras_dict
from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol
from kibic.szolgaltatas import atjaro
from kibic.szolgaltatas.magyarazat import (MagyarazatHiba, explain_valasz,
                                           kepessegek, magyaraz_muhely)


@pytest.fixture
def betolto(monkeypatch):
    g = {}
    forras_dict({"rendszer": {"kod": "MINI"}, "szabalyok": [
        {"minta": "1NT", "pont": "15-17", "elosztas": "BAL",
         "magyarazat": "15-17, egyenletes"},
        {"minta": "1NT-2C", "pont": "8+", "prioritas": 58,
         "vagy": [{"hossz": {"S": "4+"}}, {"hossz": {"H": "4+"}}],
         "forsz": "EGY_MENET", "alert": "Stayman: 4-es nemest kérdez"},
        {"minta": "1NT-2C-2D", "hossz": {"S": "0-3", "H": "0-3"},
         "alert": "Nincs 4-es nemes"},
    ]}, "mini", g)
    f, _ = feloldas_forrasokbol(g, "MINI")
    monkeypatch.setattr(atjaro, "ALAP_RENDSZER", "MINI")
    return lambda k, p, teszt=None: (f.sorok, Parametertar())


MENET = [{"seat": "N", "call": "1N"}, {"seat": "E", "call": "P"},
         {"seat": "S", "call": "2C"}, {"seat": "W", "call": "X"},
         {"seat": "N", "call": "2D"}]


def _kerdes(i, ules="S", **kw):
    k = {"request_id": "r1", "actor": {"seat": ules}, "state": {"dealer": "N"},
         "history": {"auction": MENET}, "question": {"call_index": i}}
    k.update(kw)
    return k


def test_explain_a_megallapodast_adja(betolto):
    v = explain_valasz(_kerdes(2), betolto)
    j = v["explanation"]
    assert v["request_id"] == "r1"
    assert j["call"] == "2C" and j["alert"] is True and j["agreed"] is True
    assert j["text"] == "Stayman: 4-es nemest kérdez"
    assert j["forcing"] == "EGY_MENET" and j["conventions"] == ["MINI"]
    assert explain_valasz(_kerdes(0), betolto)["explanation"]["shows"][
        "points"] == [15, 17]
    assert explain_valasz(_kerdes(4), betolto)["explanation"]["call"] == "2D"


def test_explain_nem_hasznal_kezet(betolto):
    """Ha a kérés mégis tartalmaz kezet, a válasz ugyanaz: szerkezetileg
    nem függhet a laptól."""
    sima = explain_valasz(_kerdes(2), betolto)["explanation"]
    kez = {"S": ["SA", "SK", "SQ", "SJ", "HA", "HK", "HQ", "DA", "DK", "DQ",
                 "CA", "CK", "CQ"]}
    keznel = explain_valasz(_kerdes(2, state={"dealer": "N",
                                              "visible_hands": kez}),
                            betolto)["explanation"]
    assert json.dumps(sima, sort_keys=True) == json.dumps(keznel, sort_keys=True)
    assert "hand" not in json.dumps(keznel)


def test_explain_csak_a_sajat_vonal(betolto):
    with pytest.raises(MagyarazatHiba, match="vonalán"):
        explain_valasz(_kerdes(3), betolto)          # W kontrája: nem a miénk


def test_explain_nincs_megallapodas(betolto):
    menet = MENET + [{"seat": "E", "call": "P"}, {"seat": "S", "call": "4S"}]
    j = explain_valasz(dict(_kerdes(6), history={"auction": menet}),
                       betolto)["explanation"]
    assert j["agreed"] is False and "megállapodás" in j["text"]


def test_muhely_a_kezzel_es_a_miert_nemmel(betolto):
    kez = ["SK", "SQ", "S8", "S2", "HJ", "H7", "H3", "DA", "D9", "D2",
           "CQ", "C6", "C4"]
    v = magyaraz_muhely({"system": "MINI", "dealer": "N", "call_index": 2,
                         "auction": [m["call"] for m in MENET],
                         "hand": kez}, betolto)
    assert v["meaning"]["alert"] is True
    assert v["would_bid"]["call"] == "2C" and v["matches"] is True
    assert v["would_bid"]["debug"]["hand"]["hcp"] == 12


def test_kepessegek():
    k = kepessegek()
    assert k["endpoints"]["explain"] and k["bid_alert"]
    assert "mohabridzs-ai/1.0" in k["accepts"]
