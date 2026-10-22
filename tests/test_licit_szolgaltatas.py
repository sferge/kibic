"""
A LICIT-SZOLGÁLTATÁS próbája — adatbázis nélkül.

A `licit_elemzes()` kívülről kapja a betöltőt, ezért a teljes válasz
összerakható egy maroknyi kézzel írt szabállyal. Amit igazol:

  * a válasz akkor is HASZNOS, ha a kibic nem tud licitálni: megmondja,
    melyik licitet nem értette és mennyi a lefedettség;
  * minden eddigi licithez tartozik magyarázat (`auction_understanding`);
  * a javaslat FORRÁSA látszik: szabály, elv vagy mérlegelés;
  * a bemenet elnéző (rövid `auction`, kisbetűs hívások), a hibás
    bemenet viszont beszédes hibát ad.
"""
import pytest

from kibic.motor.feloldas import Sor
from kibic.szolgaltatas.licit import LicitHiba, licit_elemzes

IGAZ = {"t": "IGAZ"}


def _hcp(lo=None, hi=None):
    gy = []
    if lo is not None:
        gy.append({"t": "OSSZE", "op": ">=",
                   "bal": {"t": "ERT", "kod": "HCP"},
                   "jobb": {"t": "SZAM", "v": lo}})
    if hi is not None:
        gy.append({"t": "OSSZE", "op": "<=",
                   "bal": {"t": "ERT", "kod": "HCP"},
                   "jobb": {"t": "SZAM", "v": hi}})
    return {"t": "ES", "gy": gy}


def _sor(minta, feltetel=None, jelentes=None, magy=None, fajta="SZABALY",
         mod="SORREND"):
    s = Sor(0, 0, "TESZT", 0, minta, minta, None, 0, 0,
            feltetel, magy, magy, "NEM", None)
    s.jelentes = jelentes
    s.szabaly_fajta = fajta
    s.dontesi_mod = mod
    return s


SZABALYOK = [
    _sor("1S", _hcp(12, 21),
         {"pont": {"min": 12, "max": 21}, "hossz": {"S": {"min": 5}}},
         "nyitás: 12-21 pont, ötös pikk"),
    _sor("1H", _hcp(12, 21),
         {"pont": {"min": 12, "max": 21}, "hossz": {"H": {"min": 5}}},
         "nyitás: 12-21 pont, ötös kőr"),
    _sor("1S-2S", _hcp(6, 9),
         {"pont": {"min": 6, "max": 9}, "hossz": {"S": {"min": 3}}},
         "egyszerű emelés: 6-9 pont, hármas pikk"),
]


def _betolto(rendszer_kod, par_nev=None):
    return SZABALYOK, None


KEZ = ["SK", "S7", "S4", "HA", "HQ", "H6", "H3", "D9", "D5", "D2",
       "C8", "C6", "C3"]


def _keres(**kw):
    alap = {"hand": KEZ, "seat": "S", "dealer": "N", "vulnerability": "none",
            "system": "TESZT"}
    alap.update(kw)
    return alap


# --- A válasz akkor is hasznos, ha nincs licit ----------------------

def test_a_nem_ertett_licitet_kimondja():
    """
    A 2NT-re nincs szabályunk. A kibic ezt NEM hallgatja el: megnevezi,
    és a lefedettség is mutatja. Ez a legfontosabb visszajelzés.
    """
    v = licit_elemzes(_keres(auction=[
        {"seat": "N", "call": "1S"}, {"seat": "E", "call": "2N"}]), _betolto)

    assert v["coverage"]["understood"] == 1
    assert v["coverage"]["unknown"] == 1
    assert v["coverage"]["unknown_calls"] == ["E:2NT"]

    ertes = {x["call"]: x for x in v["auction_understanding"]}
    assert ertes["1S"]["understood"] is True
    assert "pikk" in ertes["1S"]["meaning"] or "S:" in ertes["1S"]["meaning"]
    assert ertes["2NT"]["understood"] is False
    assert "nincs rá szabály" in ertes["2NT"]["note"]


def test_a_kenyszertar_a_valaszban_van():
    v = licit_elemzes(_keres(auction=[{"seat": "N", "call": "1S"}]), _betolto)
    eszak = v["constraints"]["N"]
    assert eszak["points"] == [12, 21]
    assert eszak["suits"]["S"] == [5, 13]
    assert v["constraints"]["W"] is None       # nem nyilatkozott


def test_ha_nincs_szabaly_nem_talal_ki_licitet():
    # a szabályréteg néma (a hézag-elv nélkül nézzük; az külön teszt: test_hezag.py)
    v = licit_elemzes(_keres(auction=[
        {"seat": "N", "call": "1S"}, {"seat": "E", "call": "2N"}], gap_principle=False), _betolto)
    assert v["call"] is None
    assert v["source"] == "NINCS"
    assert "nincs rá szabály" in v["source_text"]
    assert v["warning"]


# --- Amikor tud licitálni ------------------------------------------

def test_szabaly_alapjan_licital_es_megindokolja():
    """1S után hármas pikkel és 8 ponttal: egyszerű emelés."""
    v = licit_elemzes(_keres(auction=[
        {"seat": "N", "call": "1S"}, {"seat": "E", "call": "P"}]), _betolto)
    assert v["call"] == "2S"
    assert v["source"] == "SZABALY"
    assert v["candidates"][0]["rule"] == "1S-2S"
    assert "emelés" in v["candidates"][0]["why"]
    assert v["branch"] == "PAROS"


def test_a_legal_actions_szur():
    v = licit_elemzes(_keres(
        auction=[{"seat": "N", "call": "1S"}, {"seat": "E", "call": "P"}],
        legal_actions=["P", "X"], gap_principle=False), _betolto)
    assert v["call"] is None, "a 2S nem volt a megengedettek között"


# --- Elnéző bemenet, beszédes hibák --------------------------------

def test_rovid_auction_es_kisbetus_hivasok():
    """`["1s","p"]` ugyanaz, mint a hosszú alak — az üléseket osztjuk."""
    v = licit_elemzes(_keres(auction=["1s", "p"]), _betolto)
    assert v["call"] == "2S"
    ules = [x["seat"] for x in v["auction_understanding"]]
    assert ules == ["N", "E"]


@pytest.mark.parametrize("keres,resz", [
    ({"hand": KEZ[:12]}, "13 lap"),
    ({"hand": KEZ, "seat": "Q"}, "seat"),
    ({"hand": KEZ, "seat": "S", "system": None}, "system"),
    ({"hand": KEZ, "seat": "S", "system": "T", "vulnerability": "izé"},
     "beliállás"),
    ({"hand": KEZ, "seat": "S", "system": "T", "auction": ["8H"]},
     "Érvénytelen hívás"),
])
def test_hibas_bemenet_beszedes(keres, resz):
    alap = {"dealer": "N", "vulnerability": "none", "system": "TESZT"}
    alap.update(keres)
    with pytest.raises(LicitHiba) as e:
        licit_elemzes(alap, _betolto)
    assert resz.lower() in str(e.value).lower()


# --- Hallgatólagos passz nyitóerő nélkül ------------------------------

def test_nyito_helyzetben_nyitoero_nelkul_passz():
    """
    9 pont, negyedik kéz: egyik nyitás sem illik -> a LICREN szabálya
    szerint passz. Ez rendszer-döntés, nem tartalék.
    """
    v = licit_elemzes(_keres(seat="W", auction=["P", "P", "P"]), _betolto)
    assert v["call"] == "P"
    assert v["source"] == "SZABALY"
    assert v["implicit_pass"] is True
    assert "nyitóerő" in v["explanation"]


def test_elso_kezben_is_passz():
    v = licit_elemzes(_keres(seat="N", auction=[]), _betolto)
    assert v["call"] == "P" and v["implicit_pass"] is True


def test_valaszolo_helyzetben_nincs_hallgatolagos_passz():
    """Partner nyitott: a csendes passz itt hiányt takarna el."""
    v = licit_elemzes(_keres(auction=[
        {"seat": "N", "call": "1H"}, {"seat": "E", "call": "P"}], gap_principle=False), _betolto)
    assert v["call"] is None
    assert v["source"] == "NINCS"
    assert v["implicit_pass"] is False


def test_ha_a_passz_nem_legalis_nincs_hallgatolagos_passz():
    v = licit_elemzes(_keres(seat="W", auction=["P", "P", "P"],
                             legal_actions=["1C"]), _betolto)
    assert v["call"] is None and v["implicit_pass"] is False
