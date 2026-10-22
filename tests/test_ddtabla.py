"""
A leosztás-elemző (DD-tábla + par) szolgáltatás.

A DD-táblát nem az endplay számolja, hanem a tesztek adják meg
(`tabla_fv`), így a par és a válaszszerkezet endplay nélkül ellenőrizhető.
A par-eseteket kézzel számoltuk; mindegyik egy ismert helyzettípus.
"""
import json

import pytest

from kibic.szolgaltatas.dd import DdHiba
from kibic.szolgaltatas.ddtabla import ddtabla_elemzes, par, vonal_max

KEZEK = {
    "N": ["SJ", "S3", "H9", "DA", "DQ", "DT", "D8",
          "CA", "CQ", "CJ", "C7", "C6", "C3"],
    "E": ["SA", "ST", "S6", "HA", "H7", "H5", "H4", "D4", "D2",
          "CK", "CT", "C8", "C5"],
    "S": ["SK", "S8", "S7", "S2", "HQ", "HJ", "H8", "H3",
          "DJ", "D7", "D3", "C9", "C2"],
    "W": ["SQ", "S9", "S5", "S4", "HK", "HT", "H6", "H2",
          "DK", "D9", "D6", "D5", "C4"],
}


def tabla(ns=None, ew=None, alap=6, n_eltero=None):
    """Kitalált DD-tábla a solver alakjában ('NT' kulccsal)."""
    ns, ew = ns or {}, ew or {}
    t = {}
    for u in "NS":
        t[u] = {sz: ns.get(sz, alap) for sz in ("C", "D", "H", "S", "NT")}
    for u in "EW":
        t[u] = {sz: ew.get(sz, alap) for sz in ("C", "D", "H", "S", "NT")}
    if n_eltero:
        t["N"].update(n_eltero)
    return t


def keres(**mod):
    k = {"request_id": "t-1", "hands": json.loads(json.dumps(KEZEK)),
         "vulnerability": "none", "dealer": "N"}
    k.update(mod)
    return k


def elemez(k, t):
    return ddtabla_elemzes(k, tabla_fv=lambda _l: t)


def par_ertek(t, beli="NONE", oszto="N"):
    p = par(vonal_max(elemez(keres(), t)["dd_table"]), beli, oszto)
    return p["score_ns"], [(c["contract"], c["side"]) for c in p["contracts"]]


# --- Válaszszerkezet --------------------------------------------------

def test_valasz_szerkezete():
    v = elemez(keres(), tabla({"S": 10}))
    assert v["request_id"] == "t-1"
    assert set(v["dd_table"]) == set("NESW")
    assert set(v["dd_table"]["N"]) == set("CDHSN")      # szan = "N"
    assert v["dd_table"]["N"]["S"] == 10
    assert set(v["side_max"]) == {"NS", "EW"}
    assert v["par"]["score_ns"] == 420
    assert v["contract_analysis"] is None               # nem volt kontraktus
    assert "nyílt lapokkal" in v["warning"]


def test_vonal_max_a_jobbik_felvevot_adja():
    v = elemez(keres(), tabla({"H": 9}, n_eltero={"H": 10}))
    h = v["side_max"]["NS"]["H"]
    assert h == {"tricks": 10, "declarers": ["N"], "max_level": 4}
    assert v["side_max"]["EW"]["H"]["max_level"] is None   # 6 ütés


def test_egyenlo_felvevok_mindketten_szerepelnek():
    v = elemez(keres(), tabla({"S": 10}))
    assert v["side_max"]["NS"]["S"]["declarers"] == ["N", "S"]


def test_legjobb_kontraktus_az_ellenfeltol_fuggetlenul():
    v = elemez(keres(), tabla({"S": 10, "N": 9}, {"H": 9}))
    ns = v["best_contract"]["NS"]
    assert ns["score"] == 420
    assert [c["contract"] for c in ns["contracts"]] == ["4S"]
    ew = v["best_contract"]["EW"]
    # 1H+2 = 2H+1 = 3H = 140: azonos színben a legalacsonyabb szint marad
    assert ew["score"] == 140
    assert [(c["contract"], c["result"]) for c in ew["contracts"]] == [
        ("1H", "+2")]


def test_legjobb_kontraktus_ha_semmi_nem_teljesul():
    v = elemez(keres(), tabla())
    assert v["best_contract"]["NS"] is None


# --- Par ----------------------------------------------------------------

def test_par_sima_gem():
    assert par_ertek(tabla({"S": 10}, {"H": 8})) == (420, [("4S", "NS")])


def test_par_felaldozas():
    # 5HX -2 nem beliben 300, olcsóbb a 420-nál
    assert par_ertek(tabla({"S": 10}, {"H": 9})) == (300, [("5HX", "EW")])


def test_par_felaldozas_folott_tullicitalas():
    # NS beli, 11 ütés pikkben: 5S=650 -> EW 6HX -3 = 500
    assert par_ertek(tabla({"S": 11}, {"H": 9}), "NS") == (500, [("6HX", "EW")])


def test_par_bedobott_lap():
    v = elemez(keres(), tabla())
    assert v["par"]["score_ns"] == 0
    assert v["par"]["contracts"] == [] and v["par"]["passed_out"] is True


def test_par_osztofuggo():
    t = tabla({"NT": 7}, {"NT": 7})
    assert par_ertek(t, oszto="N") == (90, [("1NT", "NS")])
    assert par_ertek(t, oszto="E") == (-90, [("1NT", "EW")])


def test_par_tobb_egyenerteku_kontraktus():
    assert par_ertek(tabla({"S": 10, "H": 10})) == (
        420, [("4H", "NS"), ("4S", "NS")])


def test_par_tobbletutesnel_a_legalacsonyabb_szint():
    v = elemez(keres(), tabla({"S": 11}))
    c = v["par"]["contracts"]
    assert [(x["contract"], x["result"], x["score_ns"]) for x in c] == [
        ("4S", "+1", 450)]


def test_par_ew_szemszog_negativ():
    assert par_ertek(tabla({"C": 8}, {"NT": 9})) == (-300, [("4CX", "NS")])


def test_osztó_hianyaban_jelezzuk_a_feltetelezest():
    k = keres()
    del k["dealer"]
    v = elemez(k, tabla({"NT": 7}, {"NT": 7}))
    assert v["par"]["dealer_assumed"] is True
    assert v["par"]["dealer_sensitive"] is True
    v2 = elemez(k, tabla({"S": 10}))
    assert v2["par"]["dealer_sensitive"] is False


def test_megadott_osztonal_nincs_feltetelezes():
    v = elemez(keres(dealer="e"), tabla({"S": 10}))
    assert v["dealer"] == "E"
    assert v["par"]["dealer_assumed"] is False
    assert v["par"]["dealer_sensitive"] is None


# --- A játszott kontraktus ---------------------------------------------

def test_jatszott_kontraktus_declarer_tricks_alapjan():
    v = elemez(keres(contract="4S", declarer="S", declarer_tricks=9),
               tabla({"S": 10}, {"H": 8}))
    c = v["contract_analysis"]
    assert c["contract"] == "4S" and c["side"] == "NS"
    assert c["dd_tricks"] == 10 and c["dd_result"] == "="
    assert c["actual_tricks"] == 9 and c["actual_result"] == "-1"
    assert c["actual_score_ns"] == -50 and c["actual_source"] == "declarer_tricks"
    assert c["vs_par"]["bidding"] == {"score_diff_ns": 0, "imp_ns": 0}
    assert c["vs_par"]["play_tricks_diff"] == -1
    assert c["vs_par"]["total"] == {"score_diff_ns": -470, "imp_ns": -10}


def test_rossz_licit_a_bidding_elteresben_latszik():
    # NS csak 2S-t mondott, pedig 4S megvan: 170 - 420
    v = elemez(keres(contract={"level": 2, "strain": "S", "multiplier": 1},
                     declarer="N"), tabla({"S": 10}, {"H": 8}))
    c = v["contract_analysis"]
    assert c["dd_score_ns"] == 170
    assert c["vs_par"]["bidding"] == {"score_diff_ns": -250, "imp_ns": -6}
    assert c["actual_tricks"] is None and c["vs_par"]["total"] is None


def test_szan_kontraktus_n_roviditessel():
    v = elemez(keres(contract="3N", declarer="N", declarer_tricks=9),
               tabla({"NT": 9}))
    c = v["contract_analysis"]
    assert c["contract"] == "3NT" and c["dd_tricks"] == 9
    assert c["actual_score_ns"] == 400


def test_ew_felvevo_elojele():
    v = elemez(keres(contract="3NT", declarer="W", declarer_tricks=10),
               tabla({}, {"NT": 10}))
    c = v["contract_analysis"]
    assert c["side"] == "EW" and c["actual_score_ns"] == -430


def test_passzolt_lap():
    v = elemez(keres(contract="P"), tabla({"S": 10}))
    c = v["contract_analysis"]
    assert c["passed_out"] is True
    assert c["vs_par"]["total"] == {"score_diff_ns": -420, "imp_ns": -9}


TRIVIALIS = {"N": ["S" + e for e in "AKQJT98765432"],
             "E": ["H" + e for e in "AKQJT98765432"],
             "S": ["D" + e for e in "AKQJT98765432"],
             "W": ["C" + e for e in "AKQJT98765432"]}


def _teljes_lejatszas():
    """7S észak: kelet kezd kőrrel, mindenki színt ad, észak lop; utána
    észak hívja a pikket, a többiek dobnak — mind a 13 ütés északé."""
    ertekek = "AKQJT98765432"
    lapok = [{"seat": "E", "card": "HA"}, {"seat": "S", "card": "DA"},
             {"seat": "W", "card": "CA"}, {"seat": "N", "card": "S2"}]
    for i in range(1, 13):
        e = ertekek[i]
        lapok += [{"seat": "N", "card": "S" + ertekek[i - 1]},
                  {"seat": "E", "card": "H" + e},
                  {"seat": "S", "card": "D" + e},
                  {"seat": "W", "card": "C" + e}]
    return lapok


def test_teljes_lejatszasbol_szamolt_utesszam():
    k = keres(hands=TRIVIALIS, contract="7S", declarer="N",
              play=_teljes_lejatszas())
    v = elemez(k, tabla({"S": 13}))
    c = v["contract_analysis"]
    assert c["actual_source"] == "play" and c["actual_tricks"] == 13
    assert c["actual_score_ns"] == 1510


def test_hianyos_lejatszasbol_nincs_tenyleges():
    k = keres(hands=TRIVIALIS, contract="7S", declarer="N",
              play=[{"seat": "E", "card": "HA"}])
    v = elemez(k, tabla({"S": 13}))
    assert v["contract_analysis"]["actual_tricks"] is None


# --- Hibás bemenetek ----------------------------------------------------

@pytest.mark.parametrize("mod,reszlet", [
    ({"dealer": "X"}, "dealer"),
    ({"vulnerability": "valami"}, "vulnerability"),
    ({"contract": "4S"}, "declarer"),
    ({"contract": "4S", "declarer": "N", "declarer_tricks": 14}, "declarer_tricks"),
    ({"contract": "4S", "declarer": "N", "declarer_tricks": "9"}, "declarer_tricks"),
    ({"contract": "8S", "declarer": "N"}, "kontraktus"),
])
def test_hibas_bemenetek(mod, reszlet):
    with pytest.raises((DdHiba, ValueError)) as e:
        elemez(keres(**mod), tabla())
    assert reszlet in str(e.value)


def test_hianyzo_kez():
    k = keres()
    del k["hands"]["W"]
    with pytest.raises(DdHiba):
        elemez(k, tabla())


def test_nem_szotar_bemenet():
    with pytest.raises(DdHiba):
        ddtabla_elemzes([1, 2], tabla_fv=lambda _l: tabla())
