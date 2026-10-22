"""
A FÉSŰ próbája — a mintanyelv 0.4 két új eszközének igazolása.

A fésű nem egy licit jelentése, hanem egy LEKÉPEZÉS: az ellenfél ismert
színei és a mi szabad színeink RANGSORRENDBEN párba állnak. Ez a teszt
azt igazolja, hogy ez hat adatsorral leírható — kód nélkül.

Amit ellenőriz:
  1. a kényszertár felépül az ellenfél kétszínű licitjéből;
  2. ebből az I1/I2/V1/V2 kötés automatikusan előáll;
  3. a `+` szint a licitállásból számol konkrét licitet;
  4. a cue-bid a HELYES saját színt mutatja (fésű-párosítás);
  5. a kétértelmű ("gyenge vagy GF") jelentés uniót ad, nem metszetet;
  6. ha az ellenfél NEM kétszínűt mondott, a fésű nem illeszkedik.
"""
import pytest

from kibic.domain import Kez
from kibic.motor.feloldas import Sor
from kibic.motor.helyzet import Allas
from kibic.motor.kifejezes import Kontextus
from kibic.motor.licital import Licitmotor
from kibic.motor.propagal import Propagalo, allas_kenyszertarral

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


def _sor(minta, jelentes=None, feltetel=IGAZ, ha=None, pri=0, magy=None):
    s = Sor(0, 0, "T", 0, minta, minta, None, pri, 0,
            feltetel, magy, magy, "NEM", None)
    s.jelentes = jelentes
    s.ha_feltetel = ha
    return s


GYENGE_VAGY_GF = [{"pont": {"max": 8}}, {"pont": {"min": 13}}]

# Fésűzni csak akkor lehet, ha MINDKÉT színüket ismerjük — két rendezett
# listát fésülünk össze, és egy elemű listát nincs mivel párba állítani.
# A kötés (I1/V1...) egyetlen ismert szín ellen is létrejön (az
# információs kontra elve épp azt használja), ezért a fésűnek EZT a
# feltételt külön ki kell mondania.
KETSZINU = {"t": "ISMERT_SZINEK", "ki": "ok", "db": 2}


@pytest.fixture
def szabalyok():
    """A 015_fesu.sql lényege, Python-alakban."""
    return [
        _sor("1S", {"pont": {"min": 12, "max": 21}, "hossz": {"S": {"min": 5}}},
             _hcp(12, 21)),
        _sor("1H", {"pont": {"min": 12, "max": 21}, "hossz": {"H": {"min": 5}}},
             _hcp(12, 21)),
        # Az ELLENFÉL rendszere: Szokatlan 2NT = mindkét minor
        _sor("(1M) 2NT", {"pont": {"min": 5, "max": 10},
                          "hossz": {"C": {"min": 5}, "D": {"min": 5}}},
             _hcp(5, 10)),
        # Egyszínű közbeszólás — ennek NEM szabad fésűt indítania
        _sor("(1M) 2C", {"pont": {"min": 8}, "hossz": {"C": {"min": 5}}},
             _hcp(8)),
        # A FÉSŰ maga — hat sorból itt a négy lényeges
        _sor(".. (*) +I1",
             {"hossz": {"@V1": {"min": 5}}, "vagy": GYENGE_VAGY_GF},
             IGAZ, {"t": "ES", "gy": [
                 KETSZINU,
                 {"t": "GEM_ALATT", "szin": "@V1"},
                 {"t": "NEM", "gy": [{"t": "MONDVA", "szin": "@V1",
                                      "ki": "mi"}]}]},
             magy="fésű: V1 saját szín"),
        _sor(".. (*) +I2",
             {"hossz": {"@V2": {"min": 3}}, "vagy": GYENGE_VAGY_GF},
             IGAZ, {"t": "ES", "gy": [
                 KETSZINU,
                 {"t": "GEM_ALATT", "szin": "@V2"},
                 {"t": "MONDVA", "szin": "@V2", "ki": "mi"}]},
             magy="fésű: V2 fit"),
        _sor(".. (*) +V1",
             {"pont": {"min": 9, "max": 12}, "hossz": {"@V1": {"min": 5}}},
             _hcp(9, 12), {"t": "ES", "gy": [KETSZINU,
                                            {"t": "GEM_ALATT", "szin": "@V1"}]},
             pri=5, magy="természetes, pontosan invit"),
        _sor(".. (*) +V2",
             {"pont": {"min": 9, "max": 12}, "hossz": {"@V2": {"min": 3}}},
             _hcp(9, 12), {"t": "ES", "gy": [KETSZINU,
                                            {"t": "GEM_ALATT", "szin": "@V2"}]},
             pri=5, magy="invit emelés"),
    ]


# 1S – (2NT = minorok) – ?
MENET = [{"ules": "N", "licit": "1S"}, {"ules": "E", "licit": "2NT"}]


def test_kenyszertar_felepul(szabalyok):
    er = Propagalo(szabalyok).kenyszertar(MENET, oszto="N")
    assert er.nem_ertett == []
    assert er.kenyszertar["N"].hossz("S")[0] == 5
    assert er.kenyszertar["E"].hossz("C")[0] == 5
    assert er.kenyszertar["E"].hossz("D")[0] == 5


def test_fesu_kotesek(szabalyok):
    allas = allas_kenyszertarral(MENET, "S", Propagalo(szabalyok), oszto="N")
    assert allas.ismert_szinek("ok") == ["C", "D"]
    assert allas.szabad_szinek("ok") == ["H", "S"]
    assert allas.fesu_kotesek() == {"I1": "C", "I2": "D",
                                    "V1": "H", "V2": "S"}


def test_plusz_szint_a_licitallasbol(szabalyok):
    """A `+I1` konkrét licitté oldódik: 2NT után a legkisebb treff 3C."""
    allas = allas_kenyszertarral(MENET, "S", Propagalo(szabalyok), oszto="N")
    assert allas.kovetkezo_licit("C") == (3, "C")
    assert allas.kovetkezo_licit("D") == (3, "D")
    # 2NT MAGASABB a 2S-nél, ezért a természetes pikk már 3S —
    # pontosan ezt mondja a forrás is ("3 pikk: természetes GI").
    assert allas.kovetkezo_licit("S") == (3, "S")


def test_cue_bid_a_helyes_szint_mutatja(szabalyok):
    """A fésű lényege: 3C a kőrt (V1), 3D a pikket (V2) ígéri."""
    p = Propagalo(szabalyok)
    er = p.kenyszertar(MENET + [{"ules": "S", "licit": "3C"}], oszto="N")
    assert er.kenyszertar["S"].hossz("H")[0] == 5      # kőr, nem treff!
    assert er.kenyszertar["S"].hossz("C")[0] == 0

    er2 = p.kenyszertar(MENET + [{"ules": "S", "licit": "3D"}], oszto="N")
    assert er2.kenyszertar["S"].hossz("S")[0] == 3     # pikk-fit, nem káró
    assert er2.kenyszertar["S"].hossz("D")[0] == 0


def test_ketertelmu_jelentes_uniot_ad(szabalyok):
    """
    "Gyenge VAGY gémforsz": a kényszertárnak MINDKETTŐT engednie kell.
    Ha metszetet vennénk, a 0-8 és a 13+ sávból üres halmaz lenne, és a
    motor csendben rosszat következtetne.
    """
    er = Propagalo(szabalyok).kenyszertar(
        MENET + [{"ules": "S", "licit": "3C"}], oszto="N")
    ig = er.kenyszertar["S"]
    assert ig.pont_min == 0 and ig.pont_max >= 13
    assert not ig.ellentmondas


def test_egyszinu_kozbeszolas_nem_indit_fesut(szabalyok):
    """
    1S – (2C) után csak EGY színük ismert. A KÖTÉS létrejön (az
    információs kontra elvének épp erre van szüksége), de a fésű nem
    illeszkedik, mert a `ha_feltetel`-e két ismert színt kér.
    """
    menet = [{"ules": "N", "licit": "1S"}, {"ules": "E", "licit": "2C"}]
    allas = allas_kenyszertarral(menet, "S", Propagalo(szabalyok), oszto="N")
    assert allas.ismert_szinek("ok") == ["C"]
    assert allas.fesu_kotesek()["I1"] == "C"        # a kötés megvan

    from kibic.motor.helyzet import kiertekel
    assert kiertekel(KETSZINU, allas) is False      # a fésű mégsem él

    kez = Kez.pbn_bol("K4.KQT62.874.J93")
    d = Licitmotor(szabalyok, Kontextus(), mod="MERLEGELO").licital(
        menet, "S", kez, allas=allas, oszto="N")
    assert not d.jeloltek, "egyszínű közbeszólásra nem szabad fésűznünk"


def test_licitmotor_jelolthalmaza(szabalyok):
    """
    9 HCP-vel, ötös kőrrel mindhárom licit szóba jön: a rendszer
    ÖNMAGÁBAN nem dönt — pontosan ezt kell látnia a C módnak.
    """
    kez = Kez.pbn_bol("K4.KQT62.874.J93")           # 9 HCP, 5 kőr
    p = Propagalo(szabalyok)
    allas = allas_kenyszertarral(MENET, "S", p, oszto="N")
    d = Licitmotor(szabalyok, Kontextus(), mod="MERLEGELO").licital(
        MENET, "S", kez, allas=allas, oszto="N")
    licitek = {j.licit for j in d.jeloltek}
    assert "3H" in licitek                           # természetes invit
    assert d.bizonytalan


def test_gem_alatt():
    """A fésű élettartama: a nemes gém a 4., a minoré az 5. szinten van."""
    a = Allas(ules="S", licitek=[{"ules": "N", "licit": "1S"},
                                 {"ules": "E", "licit": "4NT"}])
    assert a.gem_alatt("C") is False      # 5C MAGA a gém, nem alatta
    assert a.gem_alatt("H") is False      # 5H már gém fölött
    assert a.gem_alatt("NT") is False

    # Ugyanez alacsonyabb állásban: a nemes gém alatt van, a minoré is.
    b = Allas(ules="S", licitek=[{"ules": "N", "licit": "1S"},
                                 {"ules": "E", "licit": "2NT"}])
    assert b.gem_alatt("H") is True       # 3H < 4H
    assert b.gem_alatt("C") is True       # 3C < 5C
    assert b.gem_alatt("NT") is False     # a legkisebb szan már 3NT = gém


def test_a_felullicit_csak_egyszer_026():
    """
    026 (2026-10-04, Moha): a felüllicit (leállás VAGY gémforsz) után a
    partner bemondja a jelzett színt; a felüllicitező ekkor NEM licitálhat
    újra felül. A „vonalunk már mondta” (fit) sor eddig újra illeszkedett.
    1♦ – (2♦ Michaels: kőr + pikk) – 2♥ (treffet mutat) – 3♣ – ? : nincs 3♥.
    """
    nem_mondtuk_I1 = {"t": "NEM", "gy": [{"t": "MONDVA", "szin": "@I1", "ki": "mi"}]}

    def sorok(uj):
        extra = [nem_mondtuk_I1] if uj else []
        return [
            _sor("1D", {"pont": {"min": 12, "max": 21}, "hossz": {"D": {"min": 4}}}, _hcp(12, 21)),
            _sor("(1D) 2D", {"pont": {"min": 6, "max": 11},
                             "hossz": {"H": {"min": 5}, "S": {"min": 5}}}, _hcp(6, 11)),
            _sor(".. (*) +I1", {"hossz": {"@V1": {"min": 5}}, "vagy": GYENGE_VAGY_GF},
                 IGAZ, {"t": "ES", "gy": [KETSZINU, {"t": "GEM_ALATT", "szin": "@V1"},
                                          {"t": "NEM", "gy": [{"t": "MONDVA", "szin": "@V1", "ki": "mi"}]}]
                        + extra}, magy="fésű: V1 saját szín"),
            _sor(".. (*) +I1", {"hossz": {"@V1": {"min": 3}}, "vagy": GYENGE_VAGY_GF},
                 IGAZ, {"t": "ES", "gy": [KETSZINU, {"t": "GEM_ALATT", "szin": "@V1"},
                                          {"t": "MONDVA", "szin": "@V1", "ki": "mi"}] + extra},
                 magy="fésű: V1 fit"),
            _sor("1D (2D) 2H (P) 3C", {"hossz": {"C": {"min": 2}}}, IGAZ, magy="a jelzett szín"),
        ]
    menet0 = [{"ules": "N", "licit": "1D"}, {"ules": "E", "licit": "2D"}]
    menet = menet0 + [{"ules": "S", "licit": "2H"}, {"ules": "W", "licit": "P"},
                      {"ules": "N", "licit": "3C"}, {"ules": "E", "licit": "P"}]
    kez = Kez.pbn_bol("A4.K4.A4.KQJT932")            # gémforsz, 7 treff
    eredmeny = {}
    for uj in (False, True):
        sr = sorok(uj)
        p = Propagalo(sr)
        allas = allas_kenyszertarral(menet0, "S", p, oszto="N")
        d = Licitmotor(sr, Kontextus(), mod="MERLEGELO").licital(menet0, "S", kez, allas=allas, oszto="N")
        assert "2H" in {j.licit for j in d.jeloltek}          # első kör: a felüllicit él
        allas = allas_kenyszertarral(menet, "S", p, oszto="N")
        d = Licitmotor(sr, Kontextus(), mod="MERLEGELO").licital(menet, "S", kez, allas=allas, oszto="N")
        eredmeny[uj] = {j.licit for j in d.jeloltek}
    assert "3H" in eredmeny[False]                   # a régi sor: második felüllicit (a hiba)
    assert "3H" not in eredmeny[True]                # a 026 után: nincs


def test_fesu_csak_ha_a_partner_mar_licitalt_027():
    """
    027 (2026-10-04, Moha): a fésű akkor él, ha a partner már mutatott színt.
    1♠ (P) 2♦ – a két ellenfél egy-egy színt mondott, a partner passzolt:
    nincs fésű (a 2♥ nem a fésű „pontosan invit” sora).
    """
    partner_szine = {"t": "ISMERT_SZINEK", "ki": "p", "db": 1, "op": ">="}
    sorok = [
        _sor("1S", {"pont": {"min": 12, "max": 21}, "hossz": {"S": {"min": 5}}}, _hcp(12, 21)),
        _sor("1H", {"pont": {"min": 12, "max": 21}, "hossz": {"H": {"min": 5}}}, _hcp(12, 21)),
        _sor("1S-2D", {"pont": {"min": 11}, "hossz": {"D": {"min": 5}}}, _hcp(11)),
        _sor("(1M) 2NT", {"pont": {"min": 5, "max": 10},
                          "hossz": {"C": {"min": 5}, "D": {"min": 5}}}, _hcp(5, 10)),
        _sor(".. (*) +V1", {"pont": {"min": 9, "max": 12}, "hossz": {"@V1": {"min": 5}}},
             _hcp(9, 12), {"t": "ES", "gy": [KETSZINU, partner_szine,
                                            {"t": "GEM_ALATT", "szin": "@V1"}]},
             pri=5, magy="természetes, pontosan invit"),
    ]
    kez = Kez.pbn_bol("K4.KQT62.874.J93")
    p = Propagalo(sorok)
    # a partner passzolt, az ellenfelek mondtak egy-egy színt: nincs fésű
    menet = [{"ules": "W", "licit": "1S"}, {"ules": "N", "licit": "P"},
             {"ules": "E", "licit": "2D"}]
    allas = allas_kenyszertarral(menet, "S", p, oszto="W")
    d = Licitmotor(sorok, Kontextus(), mod="MERLEGELO").licital(menet, "S", kez, allas=allas, oszto="W")
    assert not d.jeloltek
    # a partner nyitott (1♥ – (2NT) – ?): van fésű
    menet = [{"ules": "N", "licit": "1H"}, {"ules": "E", "licit": "2NT"}]
    allas = allas_kenyszertarral(menet, "S", p, oszto="N")
    d = Licitmotor(sorok, Kontextus(), mod="MERLEGELO").licital(menet, "S", kez, allas=allas, oszto="N")
    assert d.jeloltek
