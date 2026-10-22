"""KENYSZER és FORSZPASSZ_KIBIC elv-sablon (2026-10-12, elv-lap 1 és 2).

A szerkesztővel közösen leírt elvek („A licithelyzet szótára”):
  * a gémforsz megszűnik, ha a licitből közösen kiderül, hogy nincs esélyes
    gém (HELP-színben nincs fogás, nincs nemes fit, az 5 minorhoz kevés);
  * kényszerítő passz: ha az ellenfél a gémünk fölé licitál, és mi beliben
    (ők mansban), elfogadott invit vagy gémforsz volt — a passz „döntsd el”,
    a partner nem passzolhat.
"""
from pathlib import Path

import pytest

from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol

YAML = Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"


@pytest.fixture(scope="module")
def forrasok():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    return betolt([YAML])


@pytest.fixture(scope="module")
def elv(forrasok):
    return feloldas_forrasokbol(forrasok, "MOHA_STAND_ELV")[0]


@pytest.fixture(scope="module")
def regi(forrasok):
    return feloldas_forrasokbol(forrasok, "MOHA_STAND")[0]


def _pbn(s):
    return [sz + e for sz, lapok in zip("SHDC", s.split(".")) for e in lapok]


def _licit(sorok, kez, menet, ules, zona="none", rendszer="MOHA_STAND_ELV"):
    from kibic.szolgaltatas.licit import licit_elemzes
    k = {"hand": _pbn(kez), "seat": ules, "dealer": "N", "vulnerability": zona,
         "auction": menet.split(), "system": rendszer, "test_mode": True, "inference": False}
    return licit_elemzes(k, lambda kod, p=None, t=None: (sorok, Parametertar()))


HELP = "1H P 2D P 2H P 3C P 3D P 3H P 3S P 4D P"


@pytest.mark.parametrize("kez, vart", [
    ("762.AQJT8.843.A4", "P"),     # 11 + 11 < 27: a gémforsz megszűnt
    ("762.AQJT8.843.AK", "P"),     # 14 + 11 < 27
])
def test_gemforsz_megszunik_help_utan(elv, kez, vart):
    v = _licit(elv.sorok, kez, HELP, "N")
    assert v["call"] == vart and "megszűnt" in v["explanation"]


def test_gemforsz_nem_szunik_meg_eros_lappal(elv):
    # 17 + 11 >= 27: az 5 minorhoz elég lehet — nem passz
    assert _licit(elv.sorok, "K62.AQJT8.843.AK", HELP, "N")["call"] != "P"


def test_gemforsz_nem_szunik_meg_ha_a_partner_fogast_mutatott(elv):
    menet = "1H P 2D P 2H P 3C P 3D P 3H P 3S P 3NT P"
    v = _licit(elv.sorok, "762.AQJT8.843.A4", menet, "N")
    assert "megszűnt" not in (v["explanation"] or "")


SAKRIFISZ = "1H P 2C P 2H P 4H 5D"      # gémforsz után a gémünk fölé licitáltak


def test_forszpassz_elsokent_kontra_vedoutesekkel(elv):
    v = _licit(elv.sorok, "AK3.AQJT8.84.Q42", SAKRIFISZ, "N")
    assert v["call"] == "X" and "Kényszerítő passz" in v["explanation"]


def test_forszpassz_elsokent_passz_dontsd_el(elv):
    v = _licit(elv.sorok, "873.KQJT8.Q4.KJ4", SAKRIFISZ, "N")
    assert v["call"] == "P" and "döntsd el" in v["explanation"]


@pytest.mark.parametrize("kez, vart", [
    ("A4.9765.K32.AQ53", "X"),     # védőütésekkel: kontra
    ("4.97653.Q32.KQJ5", "5H"),    # 10 közös adu, kevés védőütés: tovább
])
def test_forszpassz_utan_nem_passzolunk(elv, kez, vart):
    v = _licit(elv.sorok, kez, SAKRIFISZ + " P P", "S")
    assert v["call"] == vart


def test_forszpassz_csak_kenyszer_helyzetben(elv):
    # egyszerű emelés után a gém, senki sincs beliben: nem kényszerítő helyzet
    menet = "1H P 2H P 4H 5D"
    assert "Kényszerítő" not in (_licit(elv.sorok, "K73.AQJT8.84.Q42", menet, "N")["explanation"] or "")
    # ugyanez, ha csak mi vagyunk beliben (ők mansban): kényszerítő passz helyzete
    v = _licit(elv.sorok, "K73.AQJT8.84.Q42", menet, "N", zona="ns")
    assert "Kényszerítő" in v["explanation"]


def test_a_regi_rendszert_nem_erinti(regi):
    # a MOHA_STAND nem hivatkozik az új elvekre
    assert not [s for s in regi.sorok if s.rendszer_kod in ("KENYSZER", "FORSZPASSZ_KIBIC")]


def test_help_passz_egy_helyen(elv):
    # a HELP-re adott 4m utáni passz csak a KENYSZER elvben él (egy fogalom — egy hely)
    kulcsok = {s.kulcs for s in elv.sorok}
    assert "FOGASMUTATAS-HELP-PASSZ" not in kulcsok
    assert {"KENYSZER-MEGSZUNES", "FORSZPASSZ-ELSO-P", "FORSZPASSZ-MASODIK-X"} <= kulcsok


def test_leiras_a_parameter_ertekevel(forrasok):
    from kibic.szolgaltatas.leiras import _sablon_adat
    sb = forrasok["KENYSZER"].sablon
    adat = _sablon_adat(sb, [{"beallitas": {}, "ertekek": {"MINOR_GEM_ERO": 27, "NEMES_FIT_MIN": 7}}])
    assert "{MINOR_GEM_ERO}" not in adat["szoveg"] and "27" in adat["szoveg"]


# --- LIMITALT_UJ_SZIN (2026-10-19): a limitált lap új színe lezárás -------------

@pytest.mark.parametrize("kez, vart", [
    ("T3.J4.T.AQJT9872", "3C"),     # 8 treff (az aranykészlet #57)
    ("T3.J4.T86.AKQ987", "3C"),     # jó minőségű 6 (ÁKD)
    ("T3.J4.T86.KJ9874", "P"),      # gyenge 6-os: nem lezárás
])
def test_limitalt_lap_uj_szine(regi, kez, vart):
    assert _licit(regi.sorok, kez, "1H P 1NT P 2H P", "S", rendszer="MOHA_STAND")["call"] == vart


@pytest.mark.parametrize("kez, vart", [
    ("AQ4.AKJ987.Q52.K", "3NT"),    # szingli treff K, fogások, gyorsütések: 9 ütés
    ("A4.AKJ987.KQ5.J3", "P"),      # nincs figura a treffben
])
def test_lezarasra_a_partner(regi, kez, vart):
    assert _licit(regi.sorok, kez, "1H P 1NT P 2H P 3C P", "N", rendszer="MOHA_STAND")["call"] == vart


# --- A szimuláció időkerete (2026-10-20) ------------------------------------

def test_szimulacio_idokeret_lejart_mintan_dont(monkeypatch):
    """Ha az időkeret letelik, az addig feldolgozott mintán dönt."""
    import time
    import kibic.motor.merlegel as mg
    from kibic.motor.helyzet import Allas
    from kibic.motor.mintavetel import mintavetel
    from kibic.motor.propagal import Igeret
    hivas = []

    def lassu_dd(lo, t=None):
        hivas.append(1)
        time.sleep(0.02)
        return {u: {sz: 9 for sz in ("C", "D", "H", "S", "NT")} for u in "NESW"}
    monkeypatch.setattr(mg, "_dd", lassu_dd)
    lic = [{"ules": "N", "licit": "1H"}, {"ules": "E", "licit": "P"},
           {"ules": "S", "licit": "3H"}, {"ules": "W", "licit": "P"}]
    tar = {u: Igeret() for u in "NESW"}
    allas = Allas(ules="N", licitek=lic, oszto="N", kenyszertar=tar)
    from kibic.domain import Kez
    kez = Kez.pbn_bol("AKQ2.AKQ32.32.32")
    m = mintavetel(kez, "N", tar, db=40, mag=1)
    ki = mg.vegkontraktus_valasztas(allas, m.leosztasok, ["P", "4H"],
                                    hatarido=time.monotonic() + 0.1, mag=1)
    assert 1 <= len(ki[0].pontszamok) < 40 and len(hivas) < 40


def test_atjaro_alapbol_szimulal(monkeypatch):
    import importlib
    monkeypatch.delenv("KIBIC_ATJARO_SZIMULACIO", raising=False)
    monkeypatch.delenv("KIBIC_ATJARO_SZIM_MS", raising=False)
    import kibic.szolgaltatas.atjaro as at
    at = importlib.reload(at)
    assert at.SZIMULACIO_ENGEDVE is True and at.SZIMULACIO_MS == 10000
    monkeypatch.setenv("KIBIC_ATJARO_SZIMULACIO", "0")
    at = importlib.reload(at)
    assert at.SZIMULACIO_ENGEDVE is False
    monkeypatch.delenv("KIBIC_ATJARO_SZIMULACIO")
    importlib.reload(at)
