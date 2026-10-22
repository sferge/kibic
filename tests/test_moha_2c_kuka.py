"""MOHA_2C_KUKA (a szerkesztő, 2026-09-30): 2♣-2♥ = kuka (legfeljebb 3
nano-pont), 2♣-2♦ = pozitív, gémforsz; 2♣-3♥ = természetes kőr; nincs
második negatív."""
from pathlib import Path

import pytest

from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol


def _pbn(s):
    return [sz + e for sz, l in zip("SHDC", s.split(".")) for e in l]


@pytest.fixture(scope="module")
def kartya():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "KIBIC_STAND")
    return f


def _elemzes(f, pbn, menet, ules):
    from kibic.szolgaltatas.licit import licit_elemzes
    return licit_elemzes({"hand": _pbn(pbn), "seat": ules, "dealer": "N",
                          "vulnerability": "none", "auction": menet,
                          "system": "KIBIC_STAND", "test_mode": True},
                         lambda k, p, t=None: (f.sorok, Parametertar()))


@pytest.mark.parametrize("pbn, vart", [
    ("J32.Q432.Q432.32", "2H"),      # két dáma = 2 nano-pont: kuka
    ("32.K432.5432.J32", "2H") ,     # egy király = 2 nano-pont: kuka
    ("Q32.K432.5432.32", "2D"),      # K + D = 3 nano-pont: már pozitív
    ("A32.5432.5432.32", "2D"),      # egy ász = 3 nano-pont: pozitív
    ("Q32.KQ5432.432.2", "3H"),      # természetes kőr (a régi 2♥)
    ("2.QJ98765.543.32", "4H"),      # kuka lap 7+ kőrrel: az alaprendszer 4♥-e
])
def test_valasz_a_2treffre(kartya, pbn, vart):
    assert _elemzes(kartya, pbn, ["2C", "P"], "S")["call"] == vart


@pytest.mark.parametrize("pbn, vart", [
    ("AK2.AQ2.AKJ2.KQ2", "3NT"),     # 26 egyenletes
    ("AKQJ32.AK2.AQ2.2", "4S"),      # 3 vesztő, AKQJxx önállóan játszható
    ("AKQ432.AK2.AQ2.2", "3S"),      # 3 vesztő, de AKQxxx nem önálló: erős invit
    ("A.A2.AKQJ432.AK2", "5D"),      # 2 vesztő, önálló adu: 5m
    ("A2.A2.AKQJ432.K2", "4D"),      # 3 vesztő: erős invit az 5m-hez
])
def test_kuka_utan_a_nyito(kartya, pbn, vart):
    v = _elemzes(kartya, pbn, ["2C", "P", "2H", "P"], "N")
    assert v["call"] == vart


@pytest.mark.parametrize("pbn, vart", [
    ("K32.5432.5432.32", "4S"),      # egy fedő (K): elfogadja
    ("32.Q432.5432.J32", "P"),       # nincs fedő: passz
])
def test_erős_invit_utan_a_valaszolo(kartya, pbn, vart):
    v = _elemzes(kartya, pbn, ["2C", "P", "2H", "P", "3S", "P"], "S")
    assert (v["call"] or "P") == vart


def test_2d_gemforsz_es_nincs_masodik_negativ(kartya):
    v = _elemzes(kartya, "32.32.5432.AK432", ["2C", "P", "2D", "P", "2H", "P"], "S")
    assert v["call"] == "3C"                             # természetes, nem kuka
    from kibic.motor.propagal import Propagalo
    from kibic.szolgaltatas.licit import _menet
    er = Propagalo(kartya.sorok, Parametertar()).kenyszertar(
        _menet(["2C", "P", "2D", "P"], "N"), oszto="N")
    assert er.kenyszertar["S"].gemforsz


KUKA = ["2C", "P", "2H", "P"]


def test_kuka_utan_2pikk_lapleiras(kartya):
    # 4-4-4-1 nyitó: 2♠ lapleírást kér
    assert _elemzes(kartya, "AKQ2.AKQ2.AKJ2.2", KUKA, "N")["call"] == "2S"
    # a válaszoló a leghosszabb színét (egyformánál a legolcsóbbat) mondja
    assert _elemzes(kartya, "32.Q32.J5432.432", KUKA + ["2S", "P"], "S")["call"] == "3D"
    assert _elemzes(kartya, "J432.Q432.432.32", KUKA + ["2S", "P"], "S")["call"] == "3H"
    # nemes fittel gém, különben 3NT
    assert _elemzes(kartya, "AKQ2.AKQ2.AKJ2.2", KUKA + ["2S", "P", "3H", "P"], "N")["call"] == "4H"
    assert _elemzes(kartya, "AKQ2.AKQ2.AKJ2.2", KUKA + ["2S", "P", "3D", "P"], "N")["call"] == "3NT"


@pytest.mark.parametrize("pbn, vart", [
    ("J32.QJ432.5432.3", "3D"),      # 5-ös kőr: transzfer, leállás
    ("Q2.32.J32.QJ5432", "3S"),      # 6-os treff: transzfer
    ("32.Q32.J5432.432", "P"),       # 5-ös minor nem elég: passz
])
def test_kuka_2nt_utan_transzferrel_leall(kartya, pbn, vart):
    v = _elemzes(kartya, pbn, KUKA + ["2NT", "P"], "S")
    assert (v["call"] or "P") == vart


def test_alert_a_megallapodas_nem_a_lap(kartya):
    """A Walsh 1♣-1♦ alertje mindkét ágat elmondja, bármelyikbe esik a kéz."""
    v = _elemzes(kartya, "32.32.QJ432.KJ43", ["1C", "P"], "S")
    assert v["call"] == "1D"
    assert "8 pont alatt" in v["alert"]["text"] and "11+" in v["alert"]["text"]


def test_kuka_karo_transzfer_4treff(kartya):
    assert _elemzes(kartya, "2.32.QJ65432.432", KUKA + ["2NT", "P"], "S")["call"] == "4C"
    assert _elemzes(kartya, "AK32.AQ2.AK2.KQ2", KUKA + ["2NT", "P", "4C", "P"], "N")["call"] == "4D"


def test_kuka_2pikk_utan_minor_fit_szimulacio(kartya, monkeypatch):
    """Minor fitnél a 3NT és az 5m közül a várható írás dönt."""
    import kibic.motor.merlegel as mg
    from kibic.szolgaltatas.licit import licit_elemzes

    def tabla(nt, karo):
        t = {u: {sz: 6 for sz in ("C", "D", "H", "S", "NT")} for u in "NESW"}
        for u in "NS":
            t[u]["NT"], t[u]["D"] = nt, karo
        return t
    menet = KUKA + ["2S", "P", "3D", "P"]
    for nt, karo, vart in ((9, 10, "3NT"), (7, 11, "5D")):
        monkeypatch.setattr(mg, "_dd", lambda lo, t=None, a=nt, b=karo: tabla(a, b))
        v = licit_elemzes({"hand": _pbn("AKQ2.AKQ2.AKJ2.2"), "seat": "N", "dealer": "N",
                           "vulnerability": "none", "simulate": True, "samples": 10,
                           "auction": menet, "system": "KIBIC_STAND"},
                          lambda k, p, t=None: (kartya.sorok, Parametertar()))
        assert v["call"] == vart, v.get("deliberation")
