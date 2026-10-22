"""WALSH, 1TREFF_DUBLO és a zárójeles pontsáv (2026-09-29)."""
from pathlib import Path

import pytest

from kibic.impex.rendszer_yaml import ForrasHiba, forras_dict
from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol


def test_zarojeles_pont_felul_es_alul():
    g = {}
    forras_dict({"rendszer": {"kod": "TPZ", "fajta": "KONVENCIO"}, "szabalyok": [
        {"minta": "1C-1NT", "pont": "8-10(11)", "prioritas": 49,
         "lehetoseg": {"merlegelo": True, "magyarazat": "rossz 11"}},   # mérlegelő
        {"minta": "1S", "pont": "(11)12-21", "hossz": {"S": "5+"}}]}, "t.yaml", g)
    s = {x.kulcs: x for x in g["TPZ"].sorok}
    assert set(s) == {"1C-1NT", "1C-1NT~P11", "1S", "1S~P11"}
    assert s["1C-1NT"].jelentes["pont"] == {"min": 8, "max": 10}
    assert "figurapont = 11" in s["1C-1NT~P11"].feltetel_szoveg
    assert s["1C-1NT~P11"].dontesi_mod == "MERLEGELO"     # merlegelo: true
    assert s["1C-1NT~P11"].prioritas == 48
    with pytest.raises(ForrasHiba, match="fölött"):
        forras_dict({"rendszer": {"kod": "TPY"}, "szabalyok": [
            {"minta": "1C", "pont": "8-10(9)"}]}, "t.yaml", {})


@pytest.fixture(scope="module")
def kibic_stand():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "KIBIC_STAND")
    return f


def _kez(s, h, d, c):
    return ([f"S{x}" for x in s] + [f"H{x}" for x in h]
            + [f"D{x}" for x in d] + [f"C{x}" for x in c])


def _pbn(s):
    return [sz + e for sz, lapok in zip("SHDC", s.split(".")) for e in lapok]


@pytest.mark.parametrize("kez, licitmenet, vart", [
    (_kez("AK32", "QJ32", "K32", "32"), [], "1C"),                  # 4-4-3-2: dubló treff
    (_kez("AK32", "Q32", "KJ32", "32"), [], "1D"),                  # 4 káró: 1♦
    (_kez("Q32", "K32", "J432", "432"), ["1C", "P"], "1D"),         # Walsh, gyenge
    (_kez("Q32", "K32", "Q432", "Q32"), ["1C", "P"], "1NT"),        # 9 pont
    (_kez("32", "AQ32", "KQ432", "32"), ["1C", "P"], "1D"),         # 5 káró + 4 kőr, 12
    (_kez("AQ32", "32", "KQ432", "32"), ["1C", "P", "1D", "P", "1NT", "P"], "2S"),
    (_kez("AK32", "Q32", "K32", "J32"), ["1C", "P", "1D", "P"], "1NT"),
    (_kez("32", "K32", "AQ432", "K32"), ["1C", "P", "1D", "P", "1NT", "P"], "2NT"),
    (_kez("32", "K3", "AQ432", "K432"), ["1C", "P", "1D", "P", "1NT", "P"], "3C"),
    # a lap minősége (LAPMINOSEG) dönt 10, 11 és 12 pontnál
    (_pbn("Q32.K32.Q32.KJ32"), ["1C", "P"], "1NT"),     # rossz 11 (-5)
    (_pbn("A92.KQ2.T92.Q432"), ["1C", "P"], "2NT"),     # 11, nem rossz (+1)
    (_pbn("32.K3.T92.AKT432"), ["1C", "P"], "2NT"),     # jó 10 (+6)
    (_pbn("Q32.KJ2.Q32.KJ32"), ["1C", "P"], "2NT"),     # nem jó 12 (-6)
    (_pbn("Q32.K3.T9.AKT432"), ["1C", "P"], "3NT"),     # jó 12 (+5)
])
def test_walsh_es_dublo_treff(kibic_stand, kez, licitmenet, vart):
    from kibic.szolgaltatas.licit import licit_elemzes
    ules = "N" if len(licitmenet) % 4 == 0 else "S"
    v = licit_elemzes({"hand": kez, "seat": ules, "dealer": "N", "vulnerability": "none",
                       "auction": licitmenet, "system": "KIBIC_STAND", "test_mode": True},
                      lambda k, p, t=None: (kibic_stand.sorok, Parametertar()))
    assert (v["call"] or "P") == vart


def test_lapminoseg_a_moha_peldai():
    import kibic.domain  # noqa: F401 — az értékelők regisztrálása
    from kibic.domain import Kez
    from kibic.domain.kartya import ERTEKELOK
    from kibic.domain.ertekelo import TAR
    assert TAR.ellenoriz() == []
    q = lambda pbn: ERTEKELOK["LAPMINOSEG"](Kez.pbn_bol(pbn))  # noqa: E731
    assert q("Q32.KJ2.Q32.KJ32") <= -2          # elszórt dáma-bubi, 4-3-3-3
    assert q("Q32.K3.T9.AKT432") >= 2           # AK együtt a hosszú színben
    # Kxx és Dx elszórva rosszabb, mint KDx és xx
    assert q("K32.Q2.AT92.J432") < q("KQ2.32.AT92.J432")


@pytest.mark.parametrize("pbn, beli, vart", [
    ("32.KJ98432.432.3", "ew", "2H"),     # 4 pont, mind a kőrben, ők beliben
    ("Q32.J98432.K32.3", "none", "P"),    # 6 pont, csak 1 a kőrben: nem fele
    ("32.QJ9843.K32.32", "none", "2H"),   # 6 pont, fele (3) a kőrben
    ("32.QJ9843.K32.32", "ns", "P"),      # mi beliben: 10 pont kellene
    ("Q3.KQJ432.J32.Q3", "both", "2H"),   # 11, nem jó lap (-1), mindkét vonal beliben
    ("Q3.KQJ432.J32.QJ", "ns", "2H"),     # 12, nem jó lap (-2), csak mi beliben
    ("3.AKQJ94.Q92.932", "ns", "P"),      # 12, jó lap: 1♥-et nyitna, nem 2♥
])
def test_moha_2major(pbn, beli, vart):
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    from kibic.szolgaltatas.licit import licit_elemzes
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml" / "konvenciok"
                / "moha_2major.yaml"])
    f, _ = feloldas_forrasokbol(g, "MOHA_2MAJOR")
    v = licit_elemzes({"hand": _pbn(pbn), "seat": "N", "dealer": "N", "vulnerability": beli,
                       "auction": [], "system": "MOHA_2MAJOR", "test_mode": True},
                      lambda k, p, t=None: (f.sorok, Parametertar()))
    assert (v["call"] or "P") == vart


def test_fedoutes():
    import kibic.domain  # noqa: F401
    from kibic.domain import Kez
    from kibic.motor.kifejezes import fedoutes
    # biztos: ász, király, adu dáma, szingli 1, sikén 2;
    # bizonytalan: dubló 0.5, DBx 0.5, Dxx 0.25 (külső színben)
    assert fedoutes(Kez.pbn_bol("KQ32.432.J32.432"), "S") == 2
    assert fedoutes(Kez.pbn_bol("Q32.A32.K432.J32"), "S") == 3
    assert fedoutes(Kez.pbn_bol("K32.Q32.QJ32.J32"), "S") == 1.75    # K + Dxx + DBxx
    assert fedoutes(Kez.pbn_bol("Q432.A.K5432.432"), "S") == 4        # D, A, szingli, K
    assert fedoutes(Kez.pbn_bol("Q432..K5432.5432"), "S") == 4        # D, sikén 2, K
    assert fedoutes(Kez.pbn_bol("Q432.A2.K543.432"), "S") == 3.5      # D, A, dubló, K


@pytest.fixture(scope="module")
def moha_1nt():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt, forras_dict
    yaml_ut = Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"
    g = betolt([yaml_ut])
    forras_dict({"rendszer": {"kod": "PROBA_1NT", "fajta": "RENDSZER"},
                 "hivatkozasok": ["MOHA_NONFORCE_1NT", "KIBICEGY_STAND", "BERGEN"]},
                "proba.yaml", g)
    f, _ = feloldas_forrasokbol(g, "PROBA_1NT")
    return f


@pytest.mark.parametrize("pbn, vart", [
    ("K32.Q32.QJ32.J32", "1NT"),    # 3-as pikk, 9 pont, csak 1 fedőütés: 1NT
    ("Q32.A32.K432.J32", "2S"),     # 3-as pikk, 10 AP, 2.5 fedőütés: 2♠
    ("KQ32.432.J32.432", "2S"),     # 4-es pikk, 6 AP, 2 fedőütés: 2♠, nem Bergen
    ("32.Q432.KJ32.Q32", "1NT"),    # nincs támogatás, 8 pont
])
def test_moha_nem_kenyszerito_1nt(moha_1nt, pbn, vart):
    from kibic.szolgaltatas.licit import licit_elemzes
    v = licit_elemzes({"hand": _pbn(pbn), "seat": "S", "dealer": "N", "vulnerability": "none",
                       "auction": ["1S", "P"], "system": "PROBA_1NT", "test_mode": True},
                      lambda k, p, t=None: (moha_1nt.sorok, Parametertar()))
    assert (v["call"] or "P") == vart


def test_vesztok():
    import kibic.domain  # noqa: F401
    from kibic.domain import Kez
    from kibic.motor.kifejezes import vesztok
    k = Kez.pbn_bol("AKJ32.Q32.K32.32")
    assert vesztok(k) == 7.5                       # 1 + 2.5 (Dxx) + 2 + 2
    assert vesztok(k, "H") == 2.5 and vesztok(k, "S") == 1
    assert vesztok(Kez.pbn_bol("AQJ32.QJ2.K32.2")) == 6    # DBx: 2 vesztő (nem 2.5)


@pytest.fixture(scope="module")
def fedokereso():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt, forras_dict
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    forras_dict({"rendszer": {"kod": "PROBA_FK", "fajta": "RENDSZER"},
                 "hivatkozasok": ["MOHA_NONFORCE_1NT", "MOHA_FEDOKERESO",
                                  "KIBICEGY_STAND", "BERGEN"]}, "proba.yaml", g)
    f, _ = feloldas_forrasokbol(g, "PROBA_FK")
    return f


@pytest.mark.parametrize("pbn, licitmenet, ules, vart", [
    ("AKQ32.AK2.K32.32", ["1S", "P", "2S", "P"], "N", "4S"),         # 5 vesztő: gém
    ("AKJ32.AK32.2.J32", ["1S", "P", "2S", "P"], "N", "3C"),         # 6 vesztő, J32: invit
    ("AQJ32.K32.Q32.32", ["1S", "P", "2S", "P"], "N", "P"),          # 7.5 vesztő: passz
    ("K32.Q32.Q432.J32", ["1S", "P", "2S", "P", "3C", "P"], "S", "3S"),   # 8 AP: elutasít
    ("Q32.A32.K432.432", ["1S", "P", "2S", "P", "3C", "P"], "S", "4S"),   # 9 AP, 3 fedő
    ("Q32.A32.K432.J32", ["1S", "P", "2S", "P", "3C", "P"], "S", "3H"),   # 10 AP: kulcslicit
    # 1m-1M-2M: a válaszoló fedőt számol, az induló az ígért 12-14 felét nézi
    ("K32.AQ32.432.K32", ["1C", "P", "1H", "P", "2H", "P"], "S", "3D"),   # 4 fedő, 432
    ("A32.KJ32.K2.Q432", ["1C", "P", "1H", "P", "2H", "P", "3D", "P"], "N", "3H"),  # 13: alsó fele
    ("A2.KQ32.K32.Q432", ["1C", "P", "1H", "P", "2H", "P", "3D", "P"], "N", "3S"),  # 14, 6.5 vesztő: kulcslicit
])
def test_fedokereso_invit(fedokereso, pbn, licitmenet, ules, vart):
    from kibic.szolgaltatas.licit import licit_elemzes
    v = licit_elemzes({"hand": _pbn(pbn), "seat": ules, "dealer": "N", "vulnerability": "none",
                       "auction": licitmenet, "system": "PROBA_FK", "test_mode": True},
                      lambda k, p, t=None: (fedokereso.sorok, Parametertar()))
    assert (v["call"] or "P") == vart


@pytest.fixture(scope="module")
def kibic_stand_rkc():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "KIBIC_STAND")
    return f


@pytest.mark.parametrize("pbn, licitmenet, vart", [
    # kőr adu: a 4♠ a kulcslapkérdés, a válasz lépcsőkben (4NT, 5♣, 5♦, 5♥)
    ("Q32.A32.K432.J32", ["1H", "P", "2H", "P", "4S", "P"], "5C"),     # 1 kulcslap
    ("Q32.AK2.K432.J32", ["1H", "P", "2H", "P", "4S", "P"], "5D"),     # 2, adu D nélkül
    ("K32.Q32.Q432.J32", ["1H", "P", "2H", "P", "4S", "P"], "4NT"),    # 0 kulcslap
    # pikk adu: a 4NT a kérdés
    ("A32.Q32.K432.J32", ["1S", "P", "2S", "P", "4NT", "P"], "5D"),    # 1 kulcslap (pikk ász)
    ("AK2.Q32.K432.J32", ["1S", "P", "2S", "P", "4NT", "P"], "5H"),    # 2, adu D nélkül
    ("Q32.Q32.K432.J32", ["1S", "P", "2S", "P", "4NT", "P"], "5C"),    # 0 kulcslap
    # az ellenfél passza átlátszó: küzdelmi menetben is ugyanez
    ("AK2.Q32.K432.J32", ["1S", "2C", "2S", "P", "4NT", "P"], "5H"),
])
def test_rkc_osszeemelt_nemes_utan(kibic_stand_rkc, pbn, licitmenet, vart):
    from kibic.szolgaltatas.licit import licit_elemzes
    v = licit_elemzes({"hand": _pbn(pbn), "seat": "S", "dealer": "N", "vulnerability": "none",
                       "auction": licitmenet, "system": "KIBIC_STAND", "test_mode": True},
                      lambda k, p, t=None: (kibic_stand_rkc.sorok, Parametertar()))
    assert (v["call"] or "P") == vart


def test_orkc_minor_adu_gemforszban(kibic_stand_rkc):
    """1♦-2♣ (2/1 gémforsz), 3♣ treff-emelés: gémforszban a 4♣ az ORKC."""
    from kibic.szolgaltatas.licit import licit_elemzes
    v = licit_elemzes({"hand": _pbn("Q32.K32.AQ43.Q32"), "seat": "N", "dealer": "N",
                       "vulnerability": "none",
                       "auction": ["1D", "P", "2C", "P", "3C", "P", "4C", "P"],
                       "system": "KIBIC_STAND", "test_mode": True},
                      lambda k, p, t=None: (kibic_stand_rkc.sorok, Parametertar()))
    assert v["call"] == "4H"          # 1 kulcslap: a második lépcső


def test_negyes_minor_emeles_orkc(kibic_stand_rkc):
    """1♦-1♠-2♦-4♦: adu + gémforsz + ORKC (a 3♦ szabad volt).
    Az azonnali 1♦-4♦ kizárás, nem kérdés."""
    from kibic.szolgaltatas.licit import licit_elemzes
    kez = _pbn("Q32.K3.AQ5432.Q2")                        # 1 kulcslap
    v = licit_elemzes({"hand": kez, "seat": "N", "dealer": "N", "vulnerability": "none",
                       "auction": ["1D", "P", "1S", "P", "2D", "P", "4D", "P"],
                       "system": "KIBIC_STAND", "test_mode": True},
                      lambda k, p, t=None: (kibic_stand_rkc.sorok, Parametertar()))
    assert v["call"] == "4S"          # a második lépcső a 4♦ fölött
    v = licit_elemzes({"hand": kez, "seat": "N", "dealer": "N", "vulnerability": "none",
                       "auction": ["1D", "P", "4D", "P"],
                       "system": "KIBIC_STAND", "test_mode": True},
                      lambda k, p, t=None: (kibic_stand_rkc.sorok, Parametertar()))
    assert v["call"] != "4S"


def test_elfogadott_invit_gemforsz():
    """GI után: gém = elfogad; az összeemelt szín a GI szintjén = elutasít;
    alatta további invit (F1); fölötte, gém alatt = GF."""
    from kibic.motor.helyzet import Igeret
    from kibic.motor.propagal import _elfogadja
    ig = Igeret()
    assert _elfogadja("4H", ig, "H") and _elfogadja("3NT", ig, "H")
    assert not _elfogadja("3H", ig, "H")          # lezárás
    assert not _elfogadja("3D", ig, "H")          # alatta: további invit
    assert _elfogadja("3S", ig, "H")              # fölötte, gém alatt: GF
    assert not _elfogadja("4D", ig, "D")          # minor: a 4m a lezárás
    assert _elfogadja("4H", ig, "D") and not _elfogadja("3S", ig, "D")


@pytest.fixture(scope="module")
def szlem_kartya():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt, forras_dict
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    forras_dict({"rendszer": {"kod": "PROBA_SZ", "fajta": "RENDSZER"},
                 "hivatkozasok": ["MOHA_SZLEM", "KIBICEGY_STAND", "RKC", "EMELES_ELV",
                                  "PASSZ_ELV"]}, "proba.yaml", g)
    f, _ = feloldas_forrasokbol(g, "PROBA_SZ")
    return f


@pytest.mark.parametrize("pbn, licitmenet, ules, vart", [
    # 1♥-2♣ (gémforsz) -2♥-3♥: kőr adu, gémforszban
    ("A2.AKJ432.K32.32", ["1H", "P", "2C", "P", "2H", "P", "3H", "P"], "N", "3S"),  # kulcslicit
    ("32.AQJ432.Q32.Q2", ["1H", "P", "2C", "P", "2H", "P", "3H", "P"], "N", "4H"),  # nincs kontroll: gém
    ("A32.K5.K654.K432", ["1H", "P", "2C", "P", "2H", "P", "3H", "P", "3S", "P"], "S", "4C"),
])
def test_szlem_elv_kulcslicit(szlem_kartya, pbn, licitmenet, ules, vart):
    from kibic.szolgaltatas.licit import licit_elemzes
    v = licit_elemzes({"hand": _pbn(pbn), "seat": ules, "dealer": "N", "vulnerability": "none",
                       "auction": licitmenet, "system": "PROBA_SZ", "test_mode": True},
                      lambda k, p, t=None: (szlem_kartya.sorok, Parametertar()))
    assert (v["call"] or "P") == vart


def test_szlemjelleg_szamitasa():
    import kibic.domain  # noqa: F401
    from kibic.domain import Kez
    from kibic.motor.helyzet import Allas, Igeret
    from kibic.motor.kifejezes import Kontextus, szlemjelleg
    tar = {u: Igeret() for u in "NESW"}
    tar["N"] = Igeret(nyilatkozott=True, hossz_min={"S": 5})
    tar["S"] = Igeret(nyilatkozott=True, hossz_min={"S": 3}, fedo_min=2, fedo_max=3.75,
                      pont_min=6, pont_max=10)
    allas = Allas(ules="N", licitek=[], oszto="N", kenyszertar=tar)
    ktx = Kontextus(allas=allas)
    # a partner egyszerű emelése: 2-3,75 fedő
    assert szlemjelleg(Kez.pbn_bol("AKQJ2.AKQ.AK2.2"), ktx) == "igen"     # 2 vesztő: 2-2 < 1
    assert szlemjelleg(Kez.pbn_bol("AKQ32.AK2.AK2.2"), ktx) == "talan"    # 3 vesztő
    assert szlemjelleg(Kez.pbn_bol("AKQ32.AK2.A32.32"), ktx) == "nem"     # 5 - 3,75 >= 1
