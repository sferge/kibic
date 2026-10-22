"""
A szerkesztő 2026-09-30-i elvei: gyors-lassú (erővel lassú), P/C a
géminvit alatt, a kulcslapkérdés kontroll-feltétele és a rövidségből
származó fedő (splinter).
"""
from pathlib import Path

import pytest

from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol


def _pbn(s):
    return [sz + e for sz, l in zip("SHDC", s.split(".")) for e in l]


@pytest.fixture(scope="module")
def kartya():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt, forras_dict
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    forras_dict({"rendszer": {"kod": "PROBA_GYL", "fajta": "RENDSZER"},
                 "hivatkozasok": ["MOHA_SZLEM", "GYORS_LASSU", "MOHA_PC", "1TREFF_DUBLO",
                                  "KIBICEGY_STAND", "RKC", "EMELES_ELV", "PASSZ_ELV"]},
                "proba.yaml", g)
    f, _ = feloldas_forrasokbol(g, "PROBA_GYL")
    return f


def _licit(f, pbn, licitmenet, ules):
    from kibic.szolgaltatas.licit import licit_elemzes
    v = licit_elemzes({"hand": _pbn(pbn), "seat": ules, "dealer": "N", "vulnerability": "none",
                       "auction": licitmenet, "system": "PROBA_GYL", "test_mode": True},
                      lambda k, p, t=None: (f.sorok, Parametertar()))
    return v["call"] or "P"


GF = ["1H", "P", "2C", "P", "2H", "P"]


@pytest.mark.parametrize("pbn, vart", [
    ("32.K32.A32.KQ432", "4H"),     # 12 pont, 7 vesztő: gyors = leállás
    ("Q2.K32.Q2.AQJ432", "4H"),     # 14 pont, 7 vesztő: minimális gémerő
    ("A2.K32.432.AKJ32", "3H"),     # 15 pont: plusz erő, lassú
    ("A2.K32.32.KQJ432", "3H"),     # 13 pont, de 6 vesztő: plusz erő
])
def test_gyors_lassu_a_valaszolo(kartya, pbn, vart):
    assert _licit(kartya, pbn, GF, "S") == vart


@pytest.mark.parametrize("pbn, vart", [
    ("A2.AKJ432.K32.32", "3S"),     # szlem nem kizárt: kulcslicit
    ("A.AKQJ32.KQ32.32", "3S"),     # a treffben nincs kontroll: nem ászkérdés, kulcslicit
    ("32.AQJ432.Q32.Q2", "4H"),     # a szlem kizárt: gém
])
def test_lassu_emeles_utan_a_nyito(kartya, pbn, vart):
    assert _licit(kartya, pbn, GF + ["3H", "P"], "N") == vart


PC = ["1D", "P", "1S", "P", "1NT", "P", "3D", "P"]


def test_pc_a_geminvit_alatt(kartya):
    # 12 pont (az ígért 12-14 alsó fele), 3 pikk: 3♠ = passz vagy javíts
    assert _licit(kartya, "K32.Q2.AJ32.Q432", PC, "N") == "3S"
    # 2 pikkel nem
    assert _licit(kartya, "K2.Q32.AJ32.Q432", PC, "N") != "3S"


def test_pc_nem_forszolo(kartya):
    sor = next(s for s in kartya.sorok if s.rendszer_kod == "MOHA_PC")
    assert sor.forsz == "NEM"


def test_rovidseg_fedo_splinter():
    """A partner szinglije mellett az xxx-emből 2 fedő (nem pont)."""
    import kibic.domain  # noqa: F401
    from kibic.domain import Kez
    from kibic.motor.helyzet import Allas, Igeret
    from kibic.motor.kifejezes import Kontextus, partner_fedo
    tar = {u: Igeret() for u in "NESW"}
    tar["N"] = Igeret(nyilatkozott=True, hossz_min={"S": 5})
    tar["S"] = Igeret(nyilatkozott=True, hossz_min={"S": 4}, hossz_max={"C": 1},
                      pont_min=10, pont_max=14)
    ktx = Kontextus(allas=Allas(ules="N", licitek=[], oszto="N", kenyszertar=tar))
    lo, _ = partner_fedo(ktx, Kez.pbn_bol("AKQ32.K32.A32.432"))
    assert lo == 2                          # treff xxx a szingli mellett
    lo, _ = partner_fedo(ktx, Kez.pbn_bol("AKQ32.K32.432.A32"))
    assert lo == 1                          # Axx: csak 2 vesztő, abból 1 marad


def test_splinter_nem_szingli_asszal(kartya):
    # 1♠-re 13 pont, 4 pikk, szingli treff ász: nem splinter
    assert _licit(kartya, "KJ32.Q432.QJ32.A", ["1S", "P"], "S") != "4C"
    # kis szingli treffel igen
    assert _licit(kartya, "KJ32.K432.QJ32.2", ["1S", "P"], "S") == "4C"


def _tabla(pikk, karo):
    t = {u: {sz: 6 for sz in ("C", "D", "H", "S", "NT")} for u in "NESW"}
    for u in "NS":
        t[u]["S"], t[u]["D"] = pikk, karo
    return t


@pytest.mark.parametrize("pikk, karo, vart", [
    (9, 9, "P"),        # a 3♠ teljesül, a 4♦ bukik: passz
    (8, 10, "4D"),      # a 3♠ bukik, a 4♦ teljesül: javít
])
def test_pc_utan_a_szimulacio_dont(kartya, monkeypatch, pikk, karo, vart):
    """P/C után: a passz és a 4♦ MÉRLEGELŐ sor — a várható ütésszám dönt
    (itt kézzel adott DD-táblával, DDS nélkül)."""
    import kibic.motor.merlegel as mg
    from kibic.szolgaltatas.licit import licit_elemzes
    monkeypatch.setattr(mg, "_dd", lambda lo, t=None: _tabla(pikk, karo))
    v = licit_elemzes({"hand": _pbn("AJ32.32.KQ432.K2"), "seat": "S", "dealer": "N",
                       "vulnerability": "none", "simulate": True, "samples": 12,
                       "auction": PC + ["3S", "P"], "system": "PROBA_GYL"},
                      lambda k, p, t=None: (kartya.sorok, Parametertar()))
    delib = v["deliberation"]
    assert delib["kind"] == "final_contract", delib
    assert {o["call"] for o in delib["options"]} == {"P", "4D"}
    assert v["call"] == vart and v["source"] == "MERLEGELES"


def test_lassu_emeles_elso_szin_fedo():
    """1♥-2♣-2♥-3♥ után a treff nagyon jó: a nyitó xxx-e a biztonságos
    5-ös szinthez 1 vesztő (valószínű 2 fedő), a szlemjelleghez 2 (biztos 1)."""
    import kibic.domain  # noqa: F401
    from kibic.domain import Kez
    from kibic.motor.helyzet import Allas, Igeret
    from kibic.motor.kifejezes import Kontextus, partner_fedo
    tar = {u: Igeret() for u in "NESW"}
    tar["N"] = Igeret(nyilatkozott=True, hossz_min={"H": 6})
    tar["S"] = Igeret(nyilatkozott=True, hossz_min={"H": 2, "C": 2}, pont_min=12,
                      szin_fedo={"C": (1.0, 2.0)})
    ktx = Kontextus(allas=Allas(ules="N", licitek=[], oszto="N", kenyszertar=tar))
    kez = Kez.pbn_bol("A2.AKJ432.KQ2.432")
    assert partner_fedo(ktx, kez)[0] == 1
    assert partner_fedo(ktx, kez, becsult=True)[0] == 2
