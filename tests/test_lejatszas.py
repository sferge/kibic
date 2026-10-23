"""A lejátszó réteg: játékállás, mintavétel, DD-szűrő, a megállapodás a jó lapok közül."""
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from kibic.domain import Leosztas, Lap
from kibic.motor import lejatszas as lj
from kibic.motor.helyzet import Igeret
from kibic.motor.jelzes import jelzesek, rendszerek_betolt

JELZESEK = Path(__file__).resolve().parents[1] / "rendszerek" / "jelzesek"
VAN_DDS = importlib.util.find_spec("endplay") is not None

# W: KQJ52.873.K6.974 — erős pikk, 3NT ellen indul; S a felvevő, N az asztal
LO = Leosztas.pbn_bol("N:A76.KQ5.AJ43.K82 T8.T962.T98.JT53 943.AJ4.Q752.AQ6 KQJ52.873.K6.974")


@pytest.fixture(scope="module")
def moha():
    return jelzesek("MOHA_STAND", rendszerek_betolt([JELZESEK]), "ELES")


def _kez(u, ki=()):
    return [str(l) for l in LO.kezek[u].lapok if str(l) not in ki]


def _keres(ules, play=(), lathato=None, strain="N", legalis=None):
    lejatszott = [c for _, c in play]
    lathato = lathato or [ules]
    if legalis is None:
        sajat = _kez(ules, lejatszott)
        if len(play) % 4:
            hivott = play[len(play) // 4 * 4][1][0]
            legalis = [c for c in sajat if c[0] == hivott] or sajat
        else:
            legalis = sajat
    return {"request_id": "r", "decision": "play", "deadline_ms": 20000,
            "actor": {"seat": ules, "acting_for_seat": ules},
            "state": {"dealer": "N", "contract": {"level": 3, "strain": strain, "multiplier": 1},
                      "declarer": "S", "dummy": "N",
                      "visible_hands": {u: _kez(u, lejatszott) for u in lathato}},
            "history": {"auction": [], "play": [{"seat": u, "card": c} for u, c in play]},
            "legal_actions": {"cards": legalis}}


@dataclass
class _E:
    lap: str
    utesek: int


def _dd(ertekek):
    """Hamis DD: minden mintán ugyanazok az ütésszámok (alapból 5)."""
    def fv(lo, jatszott, k):
        return [_E(str(l), ertekek.get(str(l), 5)) for l in _legalis_most]
    return fv


_legalis_most: list = []


# --- 0. Játékállás -------------------------------------------------------------

def test_allas_keresbol():
    k = _keres("E", [("W", "SK"), ("N", "S6"), ("E", "ST"), ("S", "S3"), ("W", "H3")],
               lathato=["E", "N"])
    a = lj.allas_keresbol(k)
    assert a.ules == "E" and a.vedo and a.felvetel == "SZAN" and a.asztal == "N"
    assert a.aktualis == [("W", Lap("H", "3"))]
    assert Lap("S", "T") in a.eredeti("E") and len(a.eredeti("E")) == 13
    assert a.renonszok()["W"] == set()
    k2 = _keres("E", [("W", "SK"), ("N", "S6"), ("E", "HT"), ("S", "S3")], lathato=["E", "N"],
                legalis=["H2"])
    assert lj.allas_keresbol(k2).renonszok()["E"] == {"S"}
    assert lj.lap_drotrol("S10") == Lap("S", "T") and lj.lap_drotrol("AS") == Lap("S", "A")
    with pytest.raises(lj.LejatszasHiba):
        lj.allas_keresbol({"actor": {"seat": "E"}, "state": {}})


# --- 1. Mintavétel ---------------------------------------------------------------

def test_mintavetel_tenyek():
    play = [("W", "SK"), ("N", "S6"), ("E", "ST"), ("S", "S3"),
            ("W", "SQ"), ("N", "S7"), ("E", "S8"), ("S", "S4"),
            ("W", "SJ"), ("N", "SA"), ("E", "H2"), ("S", "S9")]      # E a 3. pikkre renonsz
    a = lj.allas_keresbol(_keres("N", play, lathato=["N", "S"], legalis=_kez("N", [c for _, c in play])))
    m = lj.mintavetel(a, db=20, mag=3)
    assert len(m.leosztasok) == 20
    for lo in m.leosztasok:
        assert all(len(lo.kezek[u]) == 13 for u in "NESW")
        assert Lap("S", "K") in lo.kezek["W"].lapok and Lap("H", "2") in lo.kezek["E"].lapok
        assert lo.kezek["E"].hossz("S") == 2                       # a renonsz: több pikkje nincs
        assert lo.kezek["N"] == LO.kezek["N"] and lo.kezek["S"] == LO.kezek["S"]


def test_mintavetel_kenyszertar_es_lazitas():
    a = lj.allas_keresbol(_keres("W"))
    ig = Igeret()
    ig.pont_min = 12
    m = lj.mintavetel(a, {"E": ig}, db=10, mag=1)
    assert all(lj._hcp(lo.kezek["E"].lapok) >= 12 for lo in m.leosztasok) and not m.lazitott
    lehetetlen = Igeret()
    lehetetlen.pont_min = 39                                      # nincs ennyi pont kint
    m = lj.mintavetel(a, {"E": lehetetlen}, db=5, mag=1, max_proba=200)
    assert m.lazitott and len(m.leosztasok) == 5
    # ha a célszámot nem éri el, de van elég illeszkedő minta: NEM engedi el
    # (2026-10-21: régen már ekkor is, és szinte minden döntésnél lazított)
    m = lj.mintavetel(a, {"E": ig}, db=400, mag=1, max_proba=400)
    assert not m.lazitott and lj.LAZIT_MIN <= len(m.leosztasok) < 400
    assert all(lj._hcp(lo.kezek["E"].lapok) >= 12 for lo in m.leosztasok)


# --- 2. DD-szűrő -------------------------------------------------------------------

def test_dd_szuro_osztalyok():
    global _legalis_most
    a = lj.allas_keresbol(_keres("W"))
    _legalis_most = list(a.legalis)
    m = lj.mintavetel(a, db=8, mag=1)
    stat, n = lj.dd_szuro(a, m.leosztasok, _dd({"SK": 6, "SQ": 6, "S2": 5.9, "DK": 4}))
    assert n == 8
    assert stat[Lap("S", "K")].osztaly == "JO" and stat[Lap("S", "2")].osztaly == "JO"
    assert stat[Lap("D", "K")].osztaly == "BIZTOSAN_ROSSZ"
    assert stat[Lap("H", "3")].osztaly == "BIZTOSAN_ROSSZ"         # mindig egy ütés mínusz


# --- 3. A megállapodás a jó lapok közül ------------------------------------------

def _stat(a, ertekek, alap=5):
    """Kész LapStat-ok a döntéshez (DD nélkül)."""
    legjobb = max([ertekek.get(str(l), alap) for l in a.legalis])
    ki = {}
    for l in a.legalis:
        u = ertekek.get(str(l), alap)
        ki[l] = lj.LapStat(l, n=1, utes=u, veszt=legjobb - u, rossz=float(u < legjobb),
                           legjobb=float(u == legjobb),
                           osztaly="JO" if u >= legjobb - lj.JO_TURES else "BIZTOSAN_ROSSZ")
    return ki


def test_inditas_a_jo_lapok_kozul(moha):
    a = lj.allas_keresbol(_keres("W"))
    d = lj.dontes(a, moha, _stat(a, {"SK": 6, "SQ": 6, "SJ": 6, "S5": 6, "S2": 6}))
    assert d.lap == Lap("S", "K") and d.szabaly == "INDITAS/SZAN/SOROZAT" and d.helyzet == "INDITAS"
    # ha a megállapodás lapja nem jó: a legjobb lap
    d = lj.dontes(a, moha, _stat(a, {"S2": 7}))
    assert d.lap == Lap("S", "2") and d.szabaly is None
    # a színt a DD dönti: a kőr a jó szín, ott a megállapodás lapja (873: a legnagyobb kis lap? — Moha szan: 3 lap, nincs 10-es)
    d = lj.dontes(a, moha, _stat(a, {"H8": 7, "H7": 7, "H3": 7}))
    assert d.lap.szin == "H" and d.szabaly


def test_dds_nelkul_a_megallapodas(moha):
    a = lj.allas_keresbol(_keres("W"))

    def nincs(*_):
        raise ImportError("nincs endplay")
    e = lj.jatek_dontes(a, moha, None, nincs, db=3, mag=1)
    assert e.stat is None and e.dd_hiba and e.dontes.lap == Lap("S", "K")   # a leghosszabb szín
    assert "elemzés nélkül" in lj.magyarazat(e)


def test_szinadas_smith_es_lapszam(moha):
    harom = [("W", "SK"), ("N", "S6"), ("E", "ST"), ("S", "S3"),
             ("W", "SQ"), ("N", "S7"), ("E", "S8"), ("S", "S4"),
             ("W", "SJ"), ("N", "SA"), ("E", "H2"), ("S", "S9")]
    # a felvevő ELSŐ hívása (MOHA, szan): Smith — E-nek nincs figurája az
    # indított pikkben, nem tetszik az indulás -> nagy = jó, tehát kis lap
    a = lj.allas_keresbol(_keres("E", harom + [("N", "DA")], lathato=["E", "N"]))
    assert {l.ertek for l in a.legalis} == {"T", "9", "8"}       # E: T98 káró
    d = lj.dontes(a, moha, _stat(a, {}))
    assert d.lap == Lap("D", "8") and d.helyzet == "SZINADAS"
    # a felvevő második hívása: lapszám (fordított) — 3 lap, páratlan: nagy-kicsi -> magas
    tovabb = harom + [("N", "C2"), ("E", "C3"), ("S", "CA"), ("W", "C4"), ("S", "D2")]
    a = lj.allas_keresbol(_keres("E", tovabb, lathato=["E", "N"]))
    d = lj.dontes(a, moha, _stat(a, {}))
    assert d.lap == Lap("D", "T")
    # ha a 10-es nem jó lap, a jók közül a magas
    d = lj.dontes(a, moha, _stat(a, {"DT": 4}))
    assert d.lap == Lap("D", "9")


def test_felvevo_a_legjobb_legkisebbje():
    a = lj.allas_keresbol(_keres("S", [("W", "SK"), ("N", "S6"), ("E", "ST")], lathato=["S", "N"]))
    d = lj.dontes(a, None, _stat(a, {}))
    assert d.lap == Lap("S", "3") and d.helyzet == "FELVEVO"


def test_dobas_egyenes_preferencia(moha):
    # E nem tud pikket adni (csak kőr/káró/treff): nagy lap a nem kért színből
    play = [("W", "SK"), ("N", "S6"), ("E", "ST"), ("S", "S3"),
            ("W", "SQ"), ("N", "S7"), ("E", "S8"), ("S", "S4"),
            ("W", "SJ"), ("N", "SA")]
    a = lj.allas_keresbol(_keres("E", play, lathato=["E", "N"]))
    assert not any(l.szin == "S" for l in a.legalis)
    d = lj.dontes(a, moha, _stat(a, {}))
    assert d.helyzet == "DOBAS" and d.szabaly == "RACS/DOBAS"


def test_kenyszeru_lap():
    a = lj.allas_keresbol(_keres("E", [("W", "SK"), ("N", "S6"), ("E", "ST"), ("S", "S3"),
                                       ("W", "SQ"), ("N", "S7")], lathato=["E", "N"]))
    e = lj.jatek_dontes(a)
    assert e.dontes.lap == Lap("S", "8") and lj.magyarazat(e) == "Kényszerű lap."


# --- Valódi DDS-sel -------------------------------------------------------------------

@pytest.mark.skipif(not VAN_DDS, reason="nincs endplay (DDS)")
def test_valodi_dds_indulas(moha):
    a = lj.allas_keresbol(_keres("W"))
    e = lj.jatek_dontes(a, moha, None, ido_keret_s=10, db=12, mag=1)
    assert e.mintak >= 6 and e.dontes.lap.szin == "S" and e.dontes.lap.ertek in "KQJ"
    m = lj.meta(e)
    assert m["classes"]["JO"] >= 1 and "cards" not in m        # élesben laponként nem
    assert "cards" in lj.meta(e, reszletes=True)


def test_atjaro_play(moha):
    from kibic.szolgaltatas.atjaro import play_dontes
    k = _keres("W")
    v = play_dontes(k, betolto=None, jelzes_fv=lambda kod: moha)
    assert v["action"]["card"] in k["legal_actions"]["cards"]
    assert v["meta"]["source"] == "model" and v["meta"]["pipeline"] == "kibic_play"
    assert v["meta"]["kibic"]["signals"] == "MOHA_STAND"
    assert "debug" not in v["meta"]["kibic"]                     # élesben a lapok nem mennek ki
    # értelmezhetetlen állás: tartalék, és ezt be is vallja
    v = play_dontes({"request_id": "r", "legal_actions": {"cards": ["DT", "D6"]}})
    assert v["meta"]["source"] == "fallback" and v["action"]["card"] == "D6"


# --- A licit kényszertára a mintavételhez ------------------------------------------

@pytest.fixture(scope="module")
def betolto():
    pytest.importorskip("yaml")
    from kibic.cli.aranykeszlet import yaml_betolto
    return yaml_betolto([str(Path(__file__).resolve().parents[1] / "rendszerek" / "yaml")])


def test_kenyszertar_a_menetbol(betolto):
    from kibic.szolgaltatas.licit import kenyszertar_menetbol
    tar = kenyszertar_menetbol({"seat": "W", "dealer": "S", "vulnerability": "none",
                                "auction": ["1N", "P", "3N", "P", "P", "P"],
                                "system": "MOHA_STAND"}, betolto)
    assert tar["S"].pont_min >= 14 and tar["S"].pont_max <= 18      # az 1NT nyitás
    # a mintában a felvevő keze ezt teljesíti
    a = lj.allas_keresbol(_keres("W"))
    m = lj.mintavetel(a, tar, db=10, mag=2)
    assert not m.lazitott and all(tar["S"].pont_min <= lj._hcp(lo.kezek["S"].lapok)
                                  for lo in m.leosztasok)


def test_atjaro_play_kenyszertarral(betolto, moha):
    from kibic.szolgaltatas.atjaro import play_dontes
    k = _keres("W")
    k["history"]["auction"] = [{"seat": "S", "call": "1N"}, {"seat": "W", "call": "P"},
                               {"seat": "N", "call": "3N"}, {"seat": "E", "call": "P"},
                               {"seat": "S", "call": "P"}, {"seat": "W", "call": "P"}]
    k["state"]["dealer"] = "S"
    k["game"] = {"systems": {"NS": "MOHA_STAND", "EW": "MOHA_STAND"}}
    v = play_dontes(k, betolto=betolto, jelzes_fv=lambda kod: moha)
    assert v["meta"]["kibic"]["constraints_used"] is True
    assert v["action"]["card"] in k["legal_actions"]["cards"]


# --- A 2026-10-21-i tesztparti: 6♦ ellen, adu hívásra T73-ból a 10-es ment ---------

LO6 = Leosztas.pbn_bol("N:AK76.KQ5.AJ4.K82 T8.T962.T73.JT53 943.AJ4.KQ9852.A QJ52.873.6.Q9764")


def _keres6(szint):
    play = [("W", "SQ"), ("N", "SA"), ("E", "S8"), ("S", "S3"), ("N", "D4")]
    ki = {c for _, c in play}
    kez = {u: [str(l) for l in LO6.kezek[u].lapok if str(l) not in ki] for u in "EN"}
    return {"request_id": "r", "actor": {"seat": "E", "acting_for_seat": "E"},
            "state": {"dealer": "S", "contract": {"level": szint, "strain": "D", "multiplier": 1},
                      "declarer": "S", "dummy": "N", "visible_hands": kez},
            "history": {"play": [{"seat": u, "card": c} for u, c in play]},
            "legal_actions": {"cards": [c for c in kez["E"] if c[0] == "D"]}}


def test_magas_jel_nem_a_jatszo_tizes(moha):
    """5♦ ellen jelzünk (fordított lapszám, 3 lap: magas), de nem a magában
    álló 10-essel — a legnagyobb nélkülözhető a 7-es."""
    a = lj.allas_keresbol(_keres6(5))
    d = lj.dontes(a, moha, _stat(a, {}))
    assert d.lap == Lap("D", "7") and d.helyzet == "SZINADAS"


def test_szlem_ellen_nincs_jelzes(moha):
    a = lj.allas_keresbol(_keres6(6))
    d = lj.dontes(a, moha, _stat(a, {}))
    assert d.lap == Lap("D", "3") and d.szabaly == "JELZES/NINCS/SZLEM"
    assert "nem jelzünk" in d.indok
    assert moha.nincs_jelzes(7, "SZAN") and not moha.nincs_jelzes(5, "SZAN")
    # a kártyán az elvek között
    assert any("Szlem ellen nem jelzünk" in e["szoveg"] for e in moha.elvek)


# --- A 2026-10-21-i második tesztparti: 3NT ellen Á765-ből a kőr ász ment ---------

LO3 = Leosztas.pbn_bol("N:864.QJT43.AKJT5. T532.98.642.AKQ6 KQ9.K2.Q93.JT872 AJ7.A765.87.9543")


def test_inditas_lapja_mindig_a_megallapodase(moha):
    """Indításnál a DD csak a színt választja; az üres figura alól a 4. lap
    megy akkor is, ha a mintán az ász egy hajszállal jobbnak látszik."""
    w = [str(l) for l in LO3.kezek["W"].lapok]
    k = {"request_id": "r", "actor": {"seat": "W", "acting_for_seat": "W"},
         "state": {"dealer": "E", "contract": {"level": 3, "strain": "N"}, "declarer": "S",
                   "dummy": "N", "visible_hands": {"W": w}},
         "history": {"play": []}, "legal_actions": {"cards": w}}
    a = lj.allas_keresbol(k)
    # az ász 0,25-tel jobb (a JÓ tűrésen kívül) — a megállapodás lapja akkor is
    st = _stat(a, {"HA": 6.0, "H5": 5.75, "H6": 5.75, "H7": 5.75,
                   "S7": 5.5, "D8": 5.5, "C9": 5.5})
    for x in st.values():                    # a mintán: talán (nem biztosan rossz)
        if x.osztaly != "JO":
            x.osztaly = "TALAN"
    d = lj.dontes(a, moha, st)
    assert d.lap == Lap("H", "5") and d.szabaly == "INDITAS/SZAN/*/h4+/T+"
    # a színt viszont a DD választja: ha a treff a jobb, a treff megállapodás-lapja
    d = lj.dontes(a, moha, _stat(a, {"C9": 6.5, "C3": 6.5}))
    assert d.lap == Lap("C", "9")
    # ha minden megállapodás-lap biztosan rossz, a jó lap megy (vétó)
    d = lj.dontes(a, moha, _stat(a, {"HA": 7}))
    assert d.lap == Lap("H", "A") and d.szabaly is None


def test_jelzesrendszer_yamlbol():
    from kibic.motor.kartya import jelzesek_rendszerhez_yaml
    j = jelzesek_rendszerhez_yaml("KIBIC_STAND")
    assert j is not None and j.rendszer.kod == "MOHA_STAND"


# --- Az indulás színe: a partner licitált színe elsőbbséget élvez -------------------

def _w_keres(pbn, partner_licit, strain="N", szint=3):
    from kibic.domain import Kez
    w = [str(l) for l in Kez.pbn_bol(pbn).lapok]
    return {"request_id": "r", "actor": {"seat": "W", "acting_for_seat": "W"},
            "state": {"dealer": "E", "contract": {"level": szint, "strain": strain},
                      "declarer": "S", "dummy": "N", "visible_hands": {"W": w}},
            "history": {"play": [], "auction": [{"seat": "E", "call": partner_licit},
                                                {"seat": "S", "call": f"{szint}{strain}"}]},
            "legal_actions": {"cards": w}}


@pytest.mark.parametrize("pbn,licit,strain,vart,miert", [
    ("AJ7.A765.87.9543", "1C", "N", "C9", "a partner színe"),
    ("AJ7.A765.87.9543", "2D", "N", "D8", "a partner színe"),
    ("AJ75.A765.8.9543", "2D", "N", None, "kis szingli: nem a partner színe"),
    ("AJ75.A765.T.9543", "2D", "N", "DT", "a 10-es már nagy"),
    ("KQJ52.873.K6.974", "1H", "N", "SK", "saját erős szín, szan ellen"),
    ("AJ75.765.8.Q9543", "1S", "H", "D8", "lopás rövid aduval"),
    ("AJ7.7652.8.Q9543", "1S", "H", "S7", "hosszú aduval nem lopunk: a partner színe"),
])
def test_partner_szine_elsobbseg(moha, pbn, licit, strain, vart, miert):
    a = lj.allas_keresbol(_w_keres(pbn, licit, strain, 3 if strain == "N" else 4))
    a.partner_szinek = lj.partner_szinei(a)
    # a DD a kőrt (illetve a pikket) szeretné — az elsőbbség mégis dönt
    st = _stat(a, {}, alap=5)
    for l, x in st.items():
        if l.szin == ("H" if strain == "N" else "C"):
            x.utes = 5.1
    d = lj.dontes(a, moha, st)
    if vart is None:
        assert d.szabaly != "INDITAS/SZINVALASZTAS/PARTNER_SZINE", miert
    else:
        assert str(d.lap) == vart, (miert, d)
        assert d.szabaly == "INDITAS/SZINVALASZTAS/PARTNER_SZINE"


def test_partner_szinei_a_kenyszertarbol():
    a = lj.allas_keresbol(_w_keres("AJ7.A765.87.9543", "2C", "N"))
    ig = Igeret()
    ig.hossz_min["D"] = 5                     # pl. egy mesterséges 2♣, ami kárót ígér
    assert lj.partner_szinei(a, {"E": ig}) == ["D"]
    assert lj.partner_szinei(a) == ["C"]      # kényszertár nélkül: szó szerint


# --- Végjáték: kimerítő elemzés, a tűrés a bizonytalansággal arányos ----------------

def _lejatszas(lo, felvevo, adu, utesek):
    """Egyszerű lejátszás: mindenki a legkisebb szabályos lapját teszi."""
    from kibic.domain import kovetkezo_ules
    kez = {u: set(lo.kezek[u].lapok) for u in "NESW"}
    hivo, play = kovetkezo_ules(felvevo), []
    for _ in range(utesek):
        utes, u = [], hivo
        for _ in range(4):
            hivott = utes[0][1].szin if utes else None
            szinben = [l for l in kez[u] if l.szin == hivott]
            l = min(szinben or kez[u], key=lambda x: x.rang)
            kez[u].discard(l)
            utes.append((u, l))
            u = kovetkezo_ules(u)
        nyero, legjobb = utes[0]
        for u_, l in utes[1:]:
            if (l.szin == legjobb.szin and l.rang > legjobb.rang) or \
               (adu and l.szin == adu and legjobb.szin != adu):
                nyero, legjobb = u_, l
        play += [(u_, str(l)) for u_, l in utes]
        hivo = nyero
    return play, kez, hivo


def test_vegjatek_kimerito_es_nulla_tures():
    play, kez, hivo = _lejatszas(LO, "S", None, 10)
    ules = hivo                                  # aki hív a 11. ütésben
    lathato = [ules, "N"] if ules != "N" else ["N", "S"]
    k = {"request_id": "r", "actor": {"seat": ules, "acting_for_seat": ules},
         "state": {"dealer": "N", "contract": {"level": 3, "strain": "N"}, "declarer": "S",
                   "dummy": "N", "visible_hands": {u: [str(l) for l in kez[u]] for u in lathato}},
         "history": {"play": [{"seat": u, "card": c} for u, c in play]},
         "legal_actions": {"cards": [str(l) for l in kez[ules]]}}
    a = lj.allas_keresbol(k)
    m = lj.mintavetel(a, db=5, mag=1)
    assert m.kimerito and m.ismeretlen == 6 and len(m.leosztasok) == 20   # C(6,3), nem 5
    # egy lap az elosztások egy részében (1 a 20-ból) egy ütést veszít:
    # kimerítő elemzésnél ez már NEM jó lap (a tűrés 0)
    lapok = sorted(a.legalis, key=lambda l: (l.szin, l.rang))
    rossz, jo = lapok[0], lapok[1:]
    elso = m.leosztasok[0]

    def dd(lo, jatszott, kk):
        return [_E(str(l), 2 if (l == rossz and lo.kezek == elso.kezek) else 3) for l in a.legalis]
    e = lj.jatek_dontes(a, None, None, dd, db=5, mag=1)
    assert e.kimerito and e.tures == 0.0 and e.mintak == 20
    assert e.stat[rossz].osztaly != "JO" and all(e.stat[l].osztaly == "JO" for l in jo)
    assert "mind a(z) 20 lehetséges elosztás" in lj.magyarazat(e)
    assert lj.meta(e)["exhaustive"] is True


def test_tures_a_bizonytalansaggal():
    a = lj.allas_keresbol(_keres("W"))           # indítás: 39 ismeretlen lap
    m = lj.mintavetel(a, db=3, mag=1)
    assert not m.kimerito and m.ismeretlen == 39


def test_jatekelemzes_cli(tmp_path, capsys):
    from kibic.cli.jatekelemzes import main
    k = _keres("W")
    sor = {"decision": "play", "request_id": "r", "action": {"card": "SK"}, "request": k}
    ut = tmp_path / "naplo.jsonl"
    ut.write_text(json.dumps(sor) + "\n", encoding="utf-8")
    assert main(["--naplo", str(ut)]) == 0
    assert "kérés: van" in capsys.readouterr().out
    if VAN_DDS:
        assert main(["--naplo", str(ut), "--sor", "1", "--ido", "3"]) == 0
        ki = capsys.readouterr().out
        assert "DÖNTÉS:" in ki and "osztály" in ki


# --- Következtetés a lejátszásból: negyedik kézben a legolcsóbb nyerő lap -----------

def test_kovetkeztetes_csak_az_ellenjatekostol():
    from kibic.domain import Lap as L
    # 1. ütés: N hív ♣2, E ♣3, S (felvevő) ♣K, W (negyedik) ♣A-val üt
    k = {"request_id": "r", "actor": {"seat": "E", "acting_for_seat": "E"},
         "state": {"dealer": "N", "contract": {"level": 4, "strain": "S"}, "declarer": "S",
                   "dummy": "N", "visible_hands": {"E": [], "N": []}},
         "history": {"play": [{"seat": "N", "card": "C2"}, {"seat": "E", "card": "C3"},
                              {"seat": "S", "card": "CK"}, {"seat": "W", "card": "CA"}]},
         "legal_actions": {"cards": ["SA"]}}
    a = lj.allas_keresbol(k)
    moha_ = jelzesek("MOHA_STAND", rendszerek_betolt([JELZESEK]), "ELES")
    szab = lj.kovetkeztetes_szabalyai(a, moha_, ["S", "W"])
    assert {"LEGKISEBB_EGYENERTEKU", "LEGOLCSOBB_NYERO"} <= szab["W"]
    assert not szab.get("S", set()) & set(lj.LAP_KODOK)          # a felvevő lapjából soha
    assert szab["S"] == {"LICIT_PONTHATAR", "LICIT_KIZARAS"}      # a licitjéből igen
    assert lj.kovetkeztetes_szabalyai(a, None, ["S", "W"]) == {}   # sor nélkül semmi
    base = {"N": {L("C", "2")}, "E": {L("C", "3")}, "S": {L("C", "K"), L("C", "J")}}
    # W az Á-val ütött; ha nála lett volna az egyenértékű... nincs: az Á és a K között semmi
    assert lj.kovetkezetlen_vedo(a, {**base, "W": {L("C", "A")}}, ["W"]) is None
    # 2. eset: W harmadikként a K-t tette, nála a D is (egyenértékű) -> ellentmondás
    k2 = dict(k, history={"play": [{"seat": "S", "card": "C2"}, {"seat": "W", "card": "C3"},
                                   {"seat": "N", "card": "C4"}, {"seat": "E", "card": "CK"}]})
    a2 = lj.allas_keresbol({**k2, "actor": {"seat": "W", "acting_for_seat": "W"},
                            "state": {**k["state"], "visible_hands": {"W": [], "N": []}}})
    eredeti = {"S": {L("C", "2")}, "W": {L("C", "3")}, "N": {L("C", "4")},
               "E": {L("C", "K"), L("C", "Q")}}
    assert lj.kovetkezetlen_vedo(a2, eredeti, ["E"])                 # KD-ből a D-t tette volna
    eredeti["E"] = {L("C", "K"), L("C", "J")}
    assert lj.kovetkezetlen_vedo(a2, eredeti, ["E"])                 # negyedikként: a B is vitte volna
    # harmadik kézben a KB-ből a K nem árul el semmit (a B elveszhetne a D ellen)
    k3 = {**k2, "history": {"play": [{"seat": "W", "card": "C3"}, {"seat": "N", "card": "C4"},
                                     {"seat": "E", "card": "CK"}, {"seat": "S", "card": "C2"}]}}
    a3 = lj.allas_keresbol({**k3, "actor": {"seat": "W", "acting_for_seat": "W"},
                            "state": {**k["state"], "visible_hands": {"W": [], "N": []}}})
    assert lj.kovetkezetlen_vedo(a3, eredeti, ["E"]) is None
    # a felvevő ugyanígy tett lapjából nem következtetünk (nincs a listában)
    assert lj.kovetkezetlen_vedo(a2, {**eredeti, "S": {L("C", "2"), L("C", "8")}}, []) is None


def test_sajat_jatek_legkisebb_egyenerteku(moha):
    # E harmadik kézben, KDx-ből üt: a D-t teszi (nem a K-t)
    k = {"request_id": "r", "actor": {"seat": "E", "acting_for_seat": "E"},
         "state": {"dealer": "N", "contract": {"level": 3, "strain": "N"}, "declarer": "S",
                   "dummy": "N", "visible_hands": {"E": ["CK", "CQ", "C5", "SA"], "N": ["D2"]}},
         "history": {"play": [{"seat": "W", "card": "C2"}, {"seat": "N", "card": "C3"}]},
         "legal_actions": {"cards": ["CK", "CQ", "C5"]}}
    a = lj.allas_keresbol(k)
    st = _stat(a, {"C5": 3})                                         # a K és a D a jó lap
    d = lj.dontes(a, moha, st)
    assert d.lap == Lap("C", "Q") and "legolcsóbb" in d.indok




def test_masodik_kez_dublo_figurabol_a_figura(moha):
    """Az asztal kis treffet hív, Nyugatnál D10 dubló: a D (a DD-nek mindegy)."""
    k = {"request_id": "r", "actor": {"seat": "W", "acting_for_seat": "W"},
         "state": {"dealer": "N", "contract": {"level": 3, "strain": "S"}, "declarer": "N",
                   "dummy": "S", "visible_hands": {"W": ["CQ", "CT", "S5", "HQ", "HJ"],
                                                   "S": ["C7", "C6", "S8", "HT"]}},
         "history": {"play": [{"seat": "S", "card": "C2"}]},
         "legal_actions": {"cards": ["CQ", "CT"]}}
    a = lj.allas_keresbol(k)
    d = lj.dontes(a, moha, _stat(a, {}))               # a DD szerint egyformák
    assert d.lap == Lap("C", "Q") and d.szabaly == "MASODIK_KEZ/DUBLO_FIGURA"
    # ha a figura biztosan rossz, nem
    d = lj.dontes(a, moha, _stat(a, {"CQ": 3, "CT": 5}))
    assert d.lap == Lap("C", "T")
    # három lapnál nem él (D73: második kézben kicsi)
    assert moha.indito_lap("Q73", "SZIN", "MASODIK_KEZ") == (None, None)


@pytest.mark.parametrize("asztal_lapok,hivott,vart,kulcs", [
    (["C7", "C6", "C5"], "C2", "Q", "MASODIK_KEZ/DUBLO_FIGURA"),          # xxxx: a figura
    (["CJ", "CT", "C6"], "C2", "T", "MASODIK_KEZ/DUBLO_FIGURA/VARUNK"),   # B10xx: várunk
    (["CJ", "C6", "C5"], "C2", "T", "MASODIK_KEZ/DUBLO_FIGURA/KICSIRE"),  # Bxxx, kicsi: nem fedünk
    (["C6", "C5", "C4"], "CJ", "Q", "MASODIK_KEZ/DUBLO_FIGURA/FEDES"),    # Bxxx, a B-t hívták: fedünk
])
def test_masodik_kez_az_asztal_elottunk(moha, asztal_lapok, hivott, vart, kulcs):
    """Az asztal (Észak) hív, Kelet második kézben D10 dublóval."""
    k = {"request_id": "r", "actor": {"seat": "E", "acting_for_seat": "E"},
         "state": {"dealer": "N", "contract": {"level": 4, "strain": "S"}, "declarer": "S",
                   "dummy": "N", "visible_hands": {"E": ["CQ", "CT", "S5", "HQ"],
                                                   "N": asztal_lapok + ["S8"]}},
         "history": {"play": [{"seat": "N", "card": hivott}]},
         "legal_actions": {"cards": ["CQ", "CT"]}}
    a = lj.allas_keresbol(k)
    d = lj.dontes(a, moha, _stat(a, {}))
    assert d.lap.ertek == vart and d.szabaly == kulcs, d


def test_kovetkeztetes_sor_nelkul_nincs(moha):
    """A következtetés a jelzésrendszer sora — nélküle a kibic nem következtet."""
    from kibic.motor.jelzes import rendszerek_betolt as rb, jelzesek as jz
    szm = jz("SZEGEDI_MRAZ", rb([JELZESEK]), "ELES")
    # az alaprendszerben csak a licit kizárásos következtetése (2026-10-23)
    assert [k["kovetkeztetes"] for k in szm.kovetkeztetes_sorok] == ["LICIT_KIZARAS"]
    assert not szm.merlegeles_sorok
    assert {k["kovetkeztetes"] for k in moha.kovetkeztetes_sorok} == {
        "LEGKISEBB_EGYENERTEKU", "LEGOLCSOBB_NYERO", "PARTNER_INDITASA", "PARTNER_DOBASA",
        "LICIT_PONTHATAR", "LICIT_KIZARAS"}
    assert {m["merlegeles"] for m in moha.merlegeles_sorok} == {"ATVETEL", "PARTNER_KERESE"}


# --- 2026-10-21 (2.): súlyozott következtetések, mérlegelés --------------------------
# A tesztparti (1♦ kontra, Ny felvevő): É ♠K952 ♥Á874 ♦— ♣KB753 (11 pont!),
# K ♠1043 ♥952 ♦Á98 ♣10642, D (kibic) ♠D7 ♥DB63 ♦KB1042 ♣98.

def _kezbol(s):
    return {Lap(x[0], x[1]) for x in s.split()}


def test_tobbertelmu_licit_es_puha_pont():
    tar = Igeret(pont_min=12)
    tar.alternativak = [[Igeret(pont_min=12, hossz_min={"D": 0, "C": 3, "H": 3, "S": 3},
                                hossz_max={"D": 2}), Igeret(pont_min=20)]]
    eszak = _kezbol("SK S9 S5 S2 HA H8 H7 H4 CK CJ C7 C5 C3")           # 11 pont, 4-4-0-5
    assert lj._igeret_suly(eszak, tar) == 0.0                            # éles határ: kiesik
    assert lj._igeret_suly(eszak, tar, tures=2, suly=0.5) == 0.5         # egyszer, nem kétszer
    assert lj._igeret_suly(eszak, tar, tures=0) == 0.0
    otkaro = _kezbol("SA SK S2 HA H8 H7 DK DJ D9 D5 D3 C5 C3")           # 18 pont, 5 káró
    assert lj._igeret_suly(otkaro, tar, tures=2) == 0.0                 # se kontra-alak, se 20+
    huszon = _kezbol("SA SK S2 HA HK H7 DK DJ D9 D5 D3 CA C3")           # 22 pont, 5 káró
    assert lj._igeret_suly(huszon, tar, tures=2) == 1.0                 # az erős változat


def test_kenyszertar_megorzi_a_valtozatokat(betolto):
    from kibic.szolgaltatas.licit import kenyszertar_menetbol
    tar = kenyszertar_menetbol({"seat": "S", "dealer": "S", "vulnerability": "both",
                                "auction": [{"seat": "S", "call": "P"}, {"seat": "W", "call": "1D"},
                                            {"seat": "N", "call": "X"}],
                                "system": "MOHA_STAND"}, betolto)
    alt = tar["N"].alternativak
    # 4 változat: 11-12, 13-17, 18+ és a felmentés-kontra (9-11, a licit-szálból)
    assert alt and len(alt[0]) == 4 and tar["N"].hossz("H") == (0, 13)   # az unió nem tud alakot


def _parti(play, ules="S", lathato=None):
    lathato = lathato or {"S": "SQ S7 HQ HJ H6 H3 DK DJ DT D4 D2 C9 C8",
                          "E": "ST S4 S3 H9 H5 H2 DA D9 D8 CT C6 C4 C2"}
    lement = {c for _, c in play}
    k = {"request_id": "r", "actor": {"seat": ules, "acting_for_seat": ules},
         "state": {"dealer": "S", "contract": {"level": 1, "strain": "D", "multiplier": 2},
                   "declarer": "W", "dummy": "E",
                   "visible_hands": {u: [c for c in v.split() if c not in lement]
                                     for u, v in lathato.items()}},
         "history": {"auction": [{"seat": "S", "call": "P"}, {"seat": "W", "call": "1D"},
                                 {"seat": "N", "call": "X"}, {"seat": "E", "call": "P"},
                                 {"seat": "S", "call": "P"}, {"seat": "W", "call": "P"}],
                     "play": [{"seat": u, "card": c} for u, c in play]},
         "legal_actions": {"cards": _szabalyos([c for c in lathato[ules].split() if c not in lement],
                                               play)}}
    return lj.allas_keresbol(k)


def _szabalyos(kez, play):
    n = len(play) % 4
    if not n:
        return kez
    hivott = play[len(play) - n][1][0]
    return [c for c in kez if c[0] == hivott] or kez


def test_partner_inditasa_es_dobasa_sulyoz(moha):
    a = _parti([("N", "S5"), ("E", "ST"), ("S", "SQ"), ("W", "SA"),
                ("W", "D3"), ("N", "C3"), ("E", "DA"), ("S", "D4")])
    kov = lj.kovetkeztetes_beallitas(a, moha, ["N", "W"])
    assert kov.van("N", "PARTNER_INDITASA") and kov.van("N", "PARTNER_DOBASA")
    assert kov.suly["PARTNER_INDITASA"] == 0.2 and kov.tures == 2
    eszak = _kezbol("SK S9 S5 S2 HA H8 H7 H4 CK CJ C7 C5 C3")
    assert lj._jelzes_suly(a, {"N": eszak}, kov, {}) == (1.0, set())
    # KB952-ből a Moha a 2-est indulná (páratlan lapszám) — az S5 ezzel ellentmond
    otpikk = _kezbol("SK SJ S9 S5 S2 HA H8 H7 H4 CK C7 C5 C3")
    w, okok = lj._jelzes_suly(a, {"N": otpikk}, kov, {})
    assert w == pytest.approx(0.2) and okok == {"PARTNER_INDITASA"}
    # a ♣3 kis lappal kérte a treffet: figura nélkül ellentmondás
    figuratlan = _kezbol("SK S9 S5 S2 HA HK H8 H7 H4 C8 C7 C5 C3")
    w, okok = lj._jelzes_suly(a, {"N": figuratlan}, kov, {})
    assert w == pytest.approx(0.25) and okok == {"PARTNER_DOBASA"}
    assert lj.partner_kert_szine(a, moha) == "C"          # a ♣2 az asztalon: a 3-as a legkisebb


def test_jatek_kozben_a_tures_csak_zaj():
    """Játék közben az a lap, amely a minták 10%-ában egy ütést veszít, már nem JÓ."""
    a = _parti([("N", "S5"), ("E", "ST")])
    lapok = sorted(a.legalis, key=lambda l: l.rang)
    jo, rossz = lapok[1], lapok[0]
    leo = [None] * 200

    def dd(lo, jatszott, k, _i=[0]):
        _i[0] += 1
        return [_E(str(jo), 6), _E(str(rossz), 5 if _i[0] % 10 == 0 else 6)]
    st, _ = lj.dd_szuro(a, leo, dd, tures=0.2)
    assert st[rossz].osztaly == "JO"                       # a régi tűrés: 0.1 < 0.2
    st, _ = lj.dd_szuro(a, leo, dd, tures=0.2, paros=True)
    assert st[rossz].osztaly != "JO" and st[jo].osztaly == "JO"


def test_atvetel_ha_mindegy(moha):
    """A 9. ütés: É ♥8-at hív (ez viszi), D-nél ♥D6 — a D-vel átvesszük, és mi hívunk."""
    play = [("N", "S5"), ("E", "ST"), ("S", "SQ"), ("W", "SA"),
            ("W", "D3"), ("N", "C3"), ("E", "DA"), ("S", "D4"),
            ("E", "D8"), ("S", "DK"), ("W", "D5"), ("N", "C5"),
            ("S", "DT"), ("W", "DQ"), ("N", "H4"), ("E", "D9"),
            ("W", "D6"), ("N", "S2"), ("E", "H2"), ("S", "DJ"),
            ("S", "H3"), ("W", "HT"), ("N", "HA"), ("E", "H5"),
            ("N", "H7"), ("E", "H9"), ("S", "HJ"), ("W", "HK"),
            ("W", "S6"), ("N", "S9"), ("E", "S3"), ("S", "S7"),
            ("N", "H8"), ("E", "S4")]
    a = _parti(play)
    st = _stat(a, {})                                      # a DD szerint egyformák
    from dataclasses import replace
    csak_atv = replace(moha, merlegeles_sorok=[m for m in moha.merlegeles_sorok
                                               if m["merlegeles"] == "ATVETEL"])
    d = lj.dontes(a, csak_atv, st)
    assert d.lap == Lap("H", "Q") and d.szabaly == "MERLEGELES/ATVETEL"
    # a teljes Mohában a partner kérése (a ♣3) is ide visz
    assert lj.dontes(a, moha, st).lap == Lap("H", "Q")
    szm = jelzesek("SZEGEDI_MRAZ", rendszerek_betolt([JELZESEK]), "ELES")
    assert lj.dontes(a, szm, st).szabaly != "MERLEGELES/ATVETEL"   # sor nélkül nem él
    # ha az átvétel ütésbe kerül, nem
    d = lj.dontes(a, moha, _stat(a, {"HQ": 4}))
    assert d.lap == Lap("H", "6")


def test_partner_kerese_ha_mindegy(moha):
    """Ütésben vagyunk; a kőr és a treff egyformán jó: a partner (♣3) kért treffjét hívjuk."""
    play = [("N", "S5"), ("E", "ST"), ("S", "SQ"), ("W", "SA"),
            ("W", "D3"), ("N", "C3"), ("E", "DA"), ("S", "D4"),
            ("E", "D8"), ("S", "DK"), ("W", "D5"), ("N", "C5")]
    a = _parti(play)
    d = lj.dontes(a, moha, _stat(a, {"D2": 4}))
    assert d.lap.szin == "C" and d.szabaly == "MERLEGELES/PARTNER_KERESE"
    # ha a treff rosszabb, a jobb szín
    d = lj.dontes(a, moha, _stat(a, {"C9": 3, "C8": 3}))
    assert d.lap.szin != "C"


def test_kovetkeztetes_sor_parameterei():
    from kibic.motor.jelzes import jsorok_dictbol as _jd, JelzesHiba, sor_szoveg

    def jsorok_dictbol(d):
        return _jd(d, None, 1, "teszt", "ELFOGADOTT")
    s = jsorok_dictbol({"kovetkeztetes": "LICIT_PONTHATAR", "kitol": ["FELVEVO"],
                        "tures": 1, "suly": 0.3})
    assert s[0].adat["tures"] == 1 and s[0].adat["suly"] == 0.3 and not s[0].adat["sajat"]
    assert "1 pontig" in sor_szoveg(s[0]) and "0.3" in sor_szoveg(s[0])
    for rossz in ({"kovetkeztetes": "PARTNER_DOBASA", "tures": 1},
                  {"kovetkeztetes": "PARTNER_DOBASA", "suly": 2},
                  {"merlegeles": "VALAMI"}):
        with pytest.raises(JelzesHiba):
            jsorok_dictbol(rossz)
    m = jsorok_dictbol({"merlegeles": "ATVETEL"})
    assert m[0].kulcs == "MERLEGELES/ATVETEL" and m[0].alak == "MERLEGELES"
    assert sor_szoveg(m[0]).startswith("Mérlegelés:")


_PARTI10 = [("N", "S5"), ("E", "ST"), ("S", "SQ"), ("W", "SA"),
            ("W", "D3"), ("N", "C3"), ("E", "DA"), ("S", "D4"),
            ("E", "D8"), ("S", "DK"), ("W", "D5"), ("N", "C5"),
            ("S", "DT"), ("W", "DQ"), ("N", "H4"), ("E", "D9"),
            ("W", "D6"), ("N", "S2"), ("E", "H2"), ("S", "DJ"),
            ("S", "H3"), ("W", "HT"), ("N", "HA"), ("E", "H5"),
            ("N", "H7"), ("E", "H9"), ("S", "HJ"), ("W", "HK"),
            ("W", "S6"), ("N", "S9"), ("E", "S3"), ("S", "S7"),
            ("N", "H8"), ("E", "S4"), ("S", "H6"), ("W", "S8"),
            ("N", "SK"), ("E", "C2")]


def test_partner_kerese_lopunk_erte(moha):
    """10. ütés: É a ♠K-t hívja, D-nél nincs pikk; a ♣-ot kérte: lopunk, hogy hívhassuk."""
    a = _parti(_PARTI10)
    # az elemzés szerint a lopás 0,1 ütéssel rosszabb: a partnerség kedvéért mégis
    d = lj.dontes(a, moha, _stat(a, {"D2": 4.9, "HQ": 4}))
    assert d.lap == Lap("D", "2") and d.szabaly == "MERLEGELES/PARTNER_KERESE"
    # fél ütés már sok (a tűrés 0,25)
    d = lj.dontes(a, moha, _stat(a, {"D2": 4.5, "HQ": 4}))
    assert d.lap != Lap("D", "2")
    # sor nélkül (Szegedi–Mráz) a jobb dobás
    szm = jelzesek("SZEGEDI_MRAZ", rendszerek_betolt([JELZESEK]), "ELES")
    assert lj.dontes(a, szm, _stat(a, {"D2": 4.9, "HQ": 4})).lap != Lap("D", "2")


def test_moha_informativ_kontra_indulo_ero(betolto):
    """A Moha kontrája: induló erő (11-12 is, ha induló erős), legfeljebb 17; vagy 18+."""
    from kibic.szolgaltatas.licit import kenyszertar_menetbol
    menet = [{"seat": "S", "call": "P"}, {"seat": "W", "call": "1D"}, {"seat": "N", "call": "X"}]
    tar = kenyszertar_menetbol({"seat": "S", "dealer": "S", "vulnerability": "both",
                                "auction": menet, "system": "MOHA_STAND"}, betolto)
    alt = tar["N"].alternativak[0]
    assert sorted((v.pont_min, v.pont_max) for v in alt) == [(9, 11), (11, 12), (13, 17), (18, 40)]
    eszak = _kezbol("SK S9 S5 S2 HA H8 H7 H4 CK CJ C7 C5 C3")      # 11 pont, 6 vesztő
    assert lj._igeret_suly(eszak, tar["N"]) == 1.0
    kibic = kenyszertar_menetbol({"seat": "S", "dealer": "S", "vulnerability": "both",
                                  "auction": menet, "system": "KIBIC_STAND"}, betolto)
    assert sorted(v.pont_min for v in kibic["N"].alternativak[0]) == [9, 12, 17]   # a KIBIC-ben 17+ (és a 9-11-es felmentés)


# --- 2026-10-23: pontozás (IMP / MP) és a döntés biztossága szerinti mintaszám ------

def test_pontozas_neve():
    assert lj.pontozas_neve("IMP") == "IMP" and lj.pontozas_neve("MP") == "MP"
    assert lj.pontozas_neve("matchpoints") == "MP" and lj.pontozas_neve(None) == "IMP"
    k = _keres("W")
    k["game"] = {"scoring": "MP"}
    assert lj.allas_keresbol(k).pontozas == "MP"


def test_imp_biztonsagi_jatek():
    """3NT, felvevő: A lap átlagban több ütés (11 / 8), B biztos 9 — IMP-ben B, MP-ben A."""
    from kibic.solver.dds import LapErtekeles
    k = _keres("S", lathato=["S", "N"])
    k["state"]["contract"] = {"level": 3, "strain": "N", "multiplier": 1}
    k["legal_actions"] = {"cards": ["SA", "S3"]}
    a = lj.allas_keresbol(k)
    A, B = Lap("S", "A"), Lap("S", "3")

    def minta(a_ut):
        return [LapErtekeles("SA", a_ut, a_ut, True, 0), LapErtekeles("S3", 9, 9, True, 0)]
    for pontozas, vart in (("IMP", B), ("MP", A)):
        gy = lj.DDGyujto(a, pontozas)
        for a_ut in (11, 8, 11, 8):
            gy.hozzaad(minta(a_ut))
        st = gy.stat(tures=0.0)
        legjobb = max(st, key=lambda l: st[l].ertek)
        assert legjobb == vart, (pontozas, {str(l): s.ertek for l, s in st.items()})
    # IMP-ben a veszteség IMP-ben: bukás (-50) vs teljesítés (400 / 460) = 10 / 11 IMP
    gy = lj.DDGyujto(a, "IMP")
    gy.hozzaad(minta(8))
    assert gy.stat()[A].veszt == 10


def _hamis_dd_fv(ertek_fv):
    from kibic.solver.dds import LapErtekeles
    szamlalo = [0]

    def fv(lo, jatszott, k):
        szamlalo[0] += 1
        return [LapErtekeles(str(l), u, 13 - u, True, 0)        # u: a védő (W) ütései
                for l, u in ertek_fv(szamlalo[0]).items()]
    return fv, szamlalo


def test_a_minta_nagysaga_a_dontes_biztossagatol_fugg():
    a = lj.allas_keresbol(_keres("W"))                  # indítás: sok ismeretlen lap
    lapok = sorted(a.legalis, key=lambda l: (l.szin, l.rang))
    jo, tobbi = lapok[0], lapok[1:]
    # egyértelmű: az egyik lap mindig egy ütéssel jobb -> a minimumnál megáll
    fv, n = _hamis_dd_fv(lambda i: {jo: 6, **{l: 5 for l in tobbi}})
    e = lj.jatek_dontes(a, None, None, fv, ido_keret_s=30, db=3000, mag=1)
    assert e.megallt == "BIZTOS" and e.mintak <= lj.MIN_MINTA + lj.KOTEG
    # szoros: a két legjobb felváltva nyer -> tovább gondolkodik (itt a db-ig)
    fv, n = _hamis_dd_fv(lambda i: {lapok[0]: 6 + i % 2, lapok[1]: 7 - i % 2,
                                    **{l: 4 for l in lapok[2:]}})
    e = lj.jatek_dontes(a, None, None, fv, ido_keret_s=30, db=400, mag=1)
    assert e.megallt == "MAX" and e.mintak == 400
    assert lj.meta(e)["stopped"] == "MAX" and lj.meta(e)["scoring"] == "IMP"


# --- 2026-10-23: építő sorsolás (a színhosszak a licit szerint, pontos arányban) ----

def _hs(szabad, kell, tar=None, renonsz=None, fix=None):
    rejtett = list(kell)
    fix = fix or {u: set() for u in rejtett}
    # a `kell` a fix lapokkal együtt 13: itt a próbában a fix lapok "kitöltők"
    for u in rejtett:
        fix[u] = fix.get(u) or {Lap("C", e) for e in "AKQJT98765432"[:13 - kell[u]]}
    return lj.HosszSorsolo(rejtett, fix, szabad, renonsz or {}, tar or {})


def test_epito_sorsolas_pontos_aranyban():
    import random
    from collections import Counter
    szabad = [Lap("S", e) for e in "AKQJ"] + [Lap("H", e) for e in "AK"]
    h = _hs(szabad, {"N": 3, "S": 3})
    assert h.ok
    r = random.Random(7)
    db = Counter(sum(1 for l in h.sorsol(r)["N"] if l.szin == "S") for _ in range(6000))
    # C(4,k)·C(2,3-k)/C(6,3): k=1: 0.2, k=2: 0.6, k=3: 0.2
    for k, p in ((1, 0.2), (2, 0.6), (3, 0.2)):
        assert abs(db[k] / 6000 - p) < 0.03, db


def test_epito_sorsolas_licit_es_renonsz():
    import random
    szabad = [Lap("S", e) for e in "AKQJT9"] + [Lap("H", e) for e in "AKQJT9"]
    ig = Igeret()
    ig.hossz_min = {"S": 5}
    h = _hs(szabad, {"N": 6, "S": 6}, tar={"N": ig})
    r = random.Random(1)
    assert all(sum(1 for l in h.sorsol(r)["N"] if l.szin == "S") >= 5 for _ in range(200))
    # renonsz: S nem tud kőrt adni -> minden kőr É-é (6 kőr, É-nek épp 6 hely)
    h = _hs(szabad, {"N": 6, "S": 6}, renonsz={"S": {"H"}})
    assert all(all(l.szin == "H" for l in h.sorsol(r)["N"]) for _ in range(50))
    # teljesíthetetlen: 7 pikk kellene É-nek, de csak 6 van kint
    ig7 = Igeret()
    ig7.hossz_min = {"S": 7}
    assert not _hs(szabad, {"N": 6, "S": 6}, tar={"N": ig7}).ok


# --- 2026-10-23: kis lapok összevonása (mintázatok) a kimerítő elemzésben ---------

def test_kis_lap_osztalyok():
    szabad = [Lap("S", e) for e in "KQ75432"] + [Lap("H", e) for e in "987"]
    # a látható pikk 6-os szétvágja: {2,3,4,5} és {7} (egyedül nem osztály); a K, D,
    # a kőr 9-es számít (a határ fölött), a kőr 8-7 egy osztály
    o = lj.kis_lap_osztalyok(szabad, [Lap("S", "6")], "8")
    assert [sorted(l.ertek for l in x) for x in o] == [sorted("2345"), sorted("78")]
    assert lj.kis_lap_osztalyok(szabad, [], "0") == []


def test_mintazat_a_valodi_elosztasokat_kepviseli():
    import random
    szabad = [Lap("S", e) for e in "AK5432"] + [Lap("H", e) for e in "Q7632"]
    kell = {"N": 6, "S": 5}
    renonsz = {"N": set(), "S": set()}
    pontos = lj._felsorol(["N", "S"], szabad, kell, renonsz, 10 ** 6)
    o = lj.kis_lap_osztalyok(szabad, [], "8")
    m = lj._mintazat_felsorol(["N", "S"], szabad, kell, renonsz, o, 10 ** 6, random.Random(3))
    assert sum(w for _, w in m) == len(pontos) and len(m) < len(pontos) / 3
    for h, _ in m:                                       # a képviselő érvényes elosztás
        assert len(h["N"]) == 6 and len(h["S"]) == 5 and set(h["N"]) | set(h["S"]) == set(szabad)


def test_szabalyon_beluli_vagy_megmarad(betolto):
    """Michaels (1♥)–2♥: pikk ÉS (treff VAGY káró) — az unió csak „5 pikk” volt."""
    from kibic.szolgaltatas.licit import kenyszertar_menetbol
    tar = kenyszertar_menetbol({"seat": "S", "dealer": "N", "vulnerability": "none",
                                "auction": [{"seat": "N", "call": "1H"}, {"seat": "E", "call": "2H"}],
                                "system": "KIBIC_STAND"}, betolto)
    e = tar["E"]
    assert e.hossz("S")[0] >= 5 and e.hossz("C") == (0, 13) and e.hossz("D") == (0, 13)
    agak = [{sz: v.hossz(sz)[0] for sz in "CD"} for g in e.alternativak for v in g]
    assert {"C": 5, "D": 0} in agak and {"C": 0, "D": 5} in agak
    # pikk-káró kéz illik, pikk-kőr nem
    pk = _kezbol("SA SK SQ S5 S4 H3 H2 DA DK DQ D5 D4 C2")
    ph = _kezbol("SA SK SQ S5 S4 HA HK HQ H5 H4 D2 C3 C2")
    assert lj._igeret_suly(pk, e) == 1.0 and lj._igeret_suly(ph, e) == 0.0


# --- 2026-10-23: a licit kizárásos következtetése a lejátszásban (LICIT_KIZARAS) ----

def test_licit_tudas_a_passz_kizar(betolto):
    """1♥ – passz – passz: Észak passza a licitmotor szimulációja szerint 0-5 pont."""
    from kibic.szolgaltatas.atjaro import licit_tudas
    auc = [{"seat": "S", "call": "1H"}, {"seat": "W", "call": "P"}, {"seat": "N", "call": "P"}]
    tar, v = licit_tudas({"seat": "E", "dealer": "S", "vulnerability": "none",
                          "auction": auc, "system": "KIBIC_STAND"}, betolto, 20000)
    assert tar["S"].pont_min >= 11 and v["N"].pont_max <= 6
    tar0, v0 = licit_tudas({"seat": "E", "dealer": "S", "vulnerability": "none",
                            "auction": auc, "system": "KIBIC_STAND"}, betolto, 0)
    assert v0 == {} and tar0["S"].pont_min == tar["S"].pont_min


def test_licit_kizaras_sulya(moha):
    a = _parti([("N", "S5"), ("E", "ST")])
    kesz = Igeret(pont_min=0, pont_max=5)
    kov = lj.kovetkeztetes_beallitas(a, moha, ["N", "W"], {"N": kesz})
    assert kov.van("N", "LICIT_KIZARAS") and kov.suly["LICIT_KIZARAS"] == 0.2
    gyenge = _kezbol("S9 S5 S2 S3 H8 H7 H4 H2 C8 C7 C5 C3 C2")        # 0 pont
    hat = _kezbol("SK S5 S2 S3 H8 H7 H4 H2 CJ C7 C5 C3 C2")           # 4 pont (K+B)
    eros = _kezbol("SK S5 S2 S3 HA H7 H4 H2 C8 C7 C5 C3 C2")          # 7 pont
    kov.kodok = {"N": {"LICIT_KIZARAS"}}                             # csak ez a sor
    assert lj._jatek_suly(a, {"N": gyenge}, kov, {})[0] == 1.0
    assert lj._jatek_suly(a, {"N": hat}, kov, {})[0] == 1.0
    w, okok = lj._jatek_suly(a, {"N": eros}, kov, {})
    assert w == pytest.approx(0.2) and okok == {"LICIT_KIZARAS"}
    egy = _kezbol("SK S5 S2 S3 HQ H7 H4 H2 CJ C7 C5 C3 C2")           # 6 pont: 1 ponttal kívül
    assert lj._jatek_suly(a, {"N": egy}, kov, {})[0] == pytest.approx(0.6)


def test_aki_mar_megszegte_a_lapmegallapodast():
    """A védő QJT-ből a D-vel ütött, a B-t később letette: rá a lapból nem következtetünk."""
    from kibic.domain import Lap as L
    k = {"request_id": "r", "actor": {"seat": "E", "acting_for_seat": "E"},
         "state": {"dealer": "N", "contract": {"level": 4, "strain": "S"}, "declarer": "E",
                   "dummy": "W", "visible_hands": {"E": ["SA", "S2"], "W": ["S3", "S4"]}},
         "history": {"play": [{"seat": "S", "card": "HK"}, {"seat": "W", "card": "H2"},
                              {"seat": "N", "card": "HA"}, {"seat": "E", "card": "H3"},
                              {"seat": "N", "card": "H5"}, {"seat": "E", "card": "H6"},
                              {"seat": "S", "card": "HQ"}, {"seat": "W", "card": "H7"},
                              {"seat": "S", "card": "HJ"}, {"seat": "W", "card": "H9"},
                              {"seat": "N", "card": "C2"}, {"seat": "E", "card": "H8"}]},
         "legal_actions": {"cards": ["SA", "S2"]}}
    a = lj.allas_keresbol(k)
    szab = jelzesek("MOHA_STAND", rendszerek_betolt([JELZESEK]), "ELES")
    kov = lj.kovetkeztetes_beallitas(a, szab, ["N", "S"])
    assert "S" in kov.nem_kovetett and not (kov.kodok["S"] & set(lj.LAP_KODOK))
    assert kov.kodok["N"] & set(lj.LAP_KODOK)                         # Észak nem szegte meg


# --- 2026-10-23: a fred-mérés tanulságai -----------------------------------------

def test_tar_igazitas_csak_az_ellentmondo_reszt():
    """A licit ígérete ellentmond a letett lapoknak: csak azt a részt igazítjuk,
    a pontsáv és a többértelmű licit lehetséges változatai maradnak."""
    sz = lambda s: [Lap.parse(x) for x in s.split()]
    fix = {"N": set(), "W": set(sz("H6 HA H5"))}
    szabad = sz("HT SK SQ S2 DA D6 C7 C8")              # egyetlen kőr van még kint
    ig = Igeret()
    ig.pont_min, ig.pont_max = 8, 15
    ig.hossz_min, ig.hossz_max = {"H": 5}, {"H": 5}
    v1, v2 = Igeret(), Igeret()
    v1.hossz_min = {"S": 6}                               # lehetetlen: csak 3 pikk van kint
    v2.hossz_min = {"S": 2}
    ig.alternativak = [[v1, v2]]
    tar, igaz = lj.tar_igazitas({"W": ig, "N": None}, ["N", "W"], fix, szabad, {"N": {"H"}})
    assert igaz == ["W"] and tar["W"] is not ig
    assert tar["W"].hossz("H") == (4, 5) and (tar["W"].pont_min, tar["W"].pont_max) == (8, 15)
    assert tar["W"].alternativak == [[v2]]
    assert ig.hossz("H") == (5, 5)                        # az eredeti nem változik
    # ami összefér, ahhoz nem nyúl
    tar2, igaz2 = lj.tar_igazitas({"W": v2}, ["N", "W"], fix, szabad, {})
    assert igaz2 == [] and tar2["W"] is v2


def test_ellentmondo_hossz_mellett_a_pontsav_megmarad():
    a = lj.allas_keresbol(_keres("W"))
    ig = Igeret()
    ig.pont_min = 12
    ig.hossz_min = {"H": 13}                              # lehetetlen ígéret
    m = lj.mintavetel(a, {"E": ig}, db=10, mag=1)
    assert not m.lazitott and m.igazitott == ["E"] and len(m.leosztasok) == 10
    assert all(lj._hcp(lo.kezek["E"].lapok) >= 12 for lo in m.leosztasok)


def test_partner_kerese_turese_a_pontozas_egysegeben():
    """0,16 ütéssel „alig rosszabb”, de IMP-ben 0,8-del: nem vállaljuk."""
    A, C5 = Lap.parse("CA"), Lap.parse("C5")
    stat = {A: lj.LapStat(A, n=66, utes=1.64, ertek=-0.054, osztaly="JO"),
            C5: lj.LapStat(C5, n=66, utes=1.48, ertek=-0.844, osztaly="TALAN")}
    sor = {"merlegeles": "PARTNER_KERESE", "tures": 0.25}
    assert lj._partnersegben(stat, [A, C5], [A], sor) == [A]
    stat[C5].ertek = -0.2                                 # 0,15 IMP: belefér
    assert lj._partnersegben(stat, [A, C5], [A], sor) == [A, C5]
