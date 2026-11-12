"""PODI-PORI a lépcsős válaszoknál és a spirálban (a szerkesztő, 2026-11-11).

1. lépcső passz, 2. lépcső kontra (rekontra), 3. lépcsőtől az első szabad
licit. A kérdező (relé): passz = relé, kontra = büntető. A relé-passz után a
válaszoló kontrával mutatja az 1. lépcsőt.
"""
import pytest

from test_konvenciok_2026_10_04 import KERDEZO, RELE, T7, _licit, _pbn, kibic_stand  # noqa: F401


@pytest.mark.parametrize("kozbe, kez, vart", [
    ("4D", "AQT32.J2.A32.J32", "4S"),     # 4♣ ORKC (4♦): P tetszik, X 0/3, 4♥ 1/4, 4♠ 2 dáma nélkül
    ("4D", "QJT32.J2.Q32.J32", "X"),      # 0 kulcslap: 2. lépcső = kontra
    ("X", "QJT32.J2.A32.J32", "4D"),      # (X): P, XX, 4♦ = 3. lépcső (1/4)
])
def test_orkc_valasz_kozbeszolas_utan(kibic_stand, kozbe, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), T7 + ["4C", kozbe])
    assert v["call"] == vart


def test_spiral_kerdezo_passzal_relez(kibic_stand):
    # a válasz (5♣) után közbeszólás: a relé (a ♠K-t kérdezi) = passz
    v = _licit(kibic_stand.sorok, _pbn(KERDEZO), RELE + ["5C", "5D"])
    assert v["call"] == "P" and v["source"] == "SPIRAL"


@pytest.mark.parametrize("kez, vart", [
    ("AKT32.Q2.A32.J32", "5H"),        # ♠K megvan, ♥K nincs: L2 = az első szabad licit
    ("AQT32.J2.A32.J32", "X"),         # a ♠K nincs: L1 = kontra
])
def test_spiral_valasz_rele_passz_utan(kibic_stand, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), RELE + ["5C", "5D", "P", "P"])
    assert v["call"] == vart and v["source"] == "SPIRAL"


@pytest.mark.parametrize("kez, vart", [
    ("AKT32.Q2.A32.J32", "X"),         # L2 = kontra
    ("AQT32.J2.A32.J32", "P"),         # L1 = passz
])
def test_spiral_valasz_kozbeszolas_utan(kibic_stand, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), RELE + ["5C", "P", "5D", "5H"])
    assert v["call"] == vart and v["source"] == "SPIRAL"


@pytest.mark.parametrize("valasz, vart", [
    ("5H", "7C"),                      # L2: a ♠K megvan
    ("X", "6NT"),                      # L1: a ♠K nincs
])
def test_spiral_kerdezo_erti(kibic_stand, valasz, vart):
    v = _licit(kibic_stand.sorok, _pbn(KERDEZO), RELE + ["5C", "5D", "P", "P", valasz, "P"])
    assert v["call"] == vart and v["source"] == "SPIRAL"


def test_spiral_parameterek():
    # a spirál változata a rendszer paramétereiben rögzíthető (2026-11-11)
    from kibic.motor.kriterium import Parametertar
    from kibic.motor.spiral import spiral_beallitas, tetelek
    alap, r = tetelek("H", False, spiral_beallitas(None))
    assert alap[:4] == [("Q", "H"), ("K", "S"), ("K", "D"), ("K", "C")] and r == [0, 1, 4, 7]
    b = spiral_beallitas(Parametertar(rendszer_ertek={"SPIRAL_SZINSOR": "CDHS",
                                                      "SPIRAL_SIKEN": "KIMARAD"}))
    t, r = tetelek("H", True, b, {"D"})
    assert t[:2] == [("K", "C"), ("K", "S")] and r == [0, 2, 4]


def test_rele_kulcs():
    from pathlib import Path
    from kibic.impex.rendszer_yaml import betolt
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    sor = next(s for s in g["RKC"].sorok if s.kulcs == "ORKC-TREFF-RELE")
    assert sor.jelentes.get("rele") == 1


def test_6nt_az_ures_kiraly_vedelmeben():
    # 2-es asztal #20 (2026-11-11): E A8.AK7.KT54.AK84 a ♦K védelmében 6NT, nem 6♠
    from pathlib import Path
    from kibic.impex.rendszer_yaml import betolt
    from kibic.motor.kriterium import Parametertar
    from kibic.motor.rendszercheck import feloldas_forrasokbol
    from kibic.szolgaltatas.licit import licit_elemzes
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "MOHA_STAND")
    pt = Parametertar(rendszer_ertek=dict(g["MOHA_STAND"].parameterek))
    v = licit_elemzes({"hand": _pbn("A8.AK7.KT54.AK84"), "seat": "E", "dealer": "W",
                       "vulnerability": "both",
                       "auction": ["2S", "P", "2NT", "P", "3H", "P", "4NT", "P", "5D", "P"],
                       "system": "MOHA_STAND", "test_mode": True}, lambda k, p, t=None: (f.sorok, pt))
    assert v["call"] == "6NT"


def test_hezag_dd_mintaval_sem_mesterseges():
    # 2-es asztal #23 (2026-11-11): szimulációval (DD-minta) sem választ a
    # hézag-elv mesterséges licitet (passzolt lappal a 2♣ Drury)
    from pathlib import Path
    from kibic.impex.rendszer_yaml import betolt
    from kibic.motor.kriterium import Parametertar
    from kibic.motor.rendszercheck import feloldas_forrasokbol
    from kibic.szolgaltatas.licit import licit_elemzes
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "MOHA_STAND_ELV")
    pt = Parametertar(rendszer_ertek=dict(g["MOHA_STAND_ELV"].parameterek))
    v = licit_elemzes({"hand": _pbn("K42.97.J9.J98765"), "seat": "S", "dealer": "S",
                       "vulnerability": "both", "auction": ["P", "P", "1H", "P"],
                       "system": "MOHA_STAND_ELV", "test_mode": True, "simulate": True},
                      lambda k, p, t=None: (f.sorok, pt))
    assert v["call"] == "P"


@pytest.mark.parametrize("kez, nyitas, vart", [
    ("K42.97.J9.J98765", "1H", "P"),   # 5 FP: válaszerő alatt passz (2026-11-12, #23)
    ("A3.5.T95.AKT9863", "1S", "3C"),  # passzolt lap: 3♣ = 11-12, 5+ treff (a 2♣ Drury)
])
def test_drury_helyzet_passzolt_lap(kez, nyitas, vart):
    from pathlib import Path
    from kibic.impex.rendszer_yaml import betolt
    from kibic.motor.kriterium import Parametertar
    from kibic.motor.rendszercheck import feloldas_forrasokbol
    from kibic.szolgaltatas.licit import licit_elemzes
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "MOHA_STAND_ELV")
    pt = Parametertar(rendszer_ertek=dict(g["MOHA_STAND_ELV"].parameterek))
    for sim in (False, True):
        v = licit_elemzes({"hand": _pbn(kez), "seat": "S", "dealer": "S",
                           "vulnerability": "none", "auction": ["P", "P", nyitas, "P"],
                           "system": "MOHA_STAND_ELV", "test_mode": True, "simulate": sim},
                          lambda k, p, t=None: (f.sorok, pt))
        assert v["call"] == vart, (sim, v["explanation"])


def test_valaszero_alatt_emeles_fedoutessel():
    # 1♠-re Axx.x.xxxxx.xxxx: 2♠ (4 FP, ász, 2 fedőütés, 3 adu; 2026-11-12)
    from pathlib import Path
    from kibic.impex.rendszer_yaml import betolt
    from kibic.motor.kriterium import Parametertar
    from kibic.motor.rendszercheck import feloldas_forrasokbol
    from kibic.szolgaltatas.licit import licit_elemzes
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "MOHA_STAND_ELV")
    pt = Parametertar(rendszer_ertek=dict(g["MOHA_STAND_ELV"].parameterek))
    v = licit_elemzes({"hand": _pbn("A32.4.76532.5432"), "seat": "S", "dealer": "N",
                       "vulnerability": "none", "auction": ["1S", "P"],
                       "system": "MOHA_STAND_ELV", "test_mode": True},
                      lambda k, p, t=None: (f.sorok, pt))
    assert v["call"] == "2S", v["explanation"]


@pytest.mark.parametrize("kez, vart", [
    ("K32.43.AQ63.K432", "2C"),        # 3 lapos adu, 12 FP: 2♣
    ("K432.43.AQ6.K432", "2D"),        # 4 lapos adu, 12 FP: 2♦
    ("32.4.AKJ632.K432", "3D"),        # 11-12, 5+ káró, nincs fit
])
def test_ketutas_drury_moha(kez, vart):
    from pathlib import Path
    from kibic.impex.rendszer_yaml import betolt
    from kibic.motor.kriterium import Parametertar
    from kibic.motor.rendszercheck import feloldas_forrasokbol
    from kibic.szolgaltatas.licit import licit_elemzes
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "MOHA_STAND")
    pt = Parametertar(rendszer_ertek=dict(g["MOHA_STAND"].parameterek))
    v = licit_elemzes({"hand": _pbn(kez), "seat": "S", "dealer": "S",
                       "vulnerability": "none", "auction": ["P", "P", "1S", "P"],
                       "system": "MOHA_STAND", "test_mode": True},
                      lambda k, p, t=None: (f.sorok, pt))
    assert v["call"] == vart, v["explanation"]


def test_passzolt_feltetel():
    # „passzos” (2026-11-12): az első lehetőségén, minden nyitás előtt passzolt
    from kibic.motor.helyzet import Allas
    lic = [{"ules": u, "licit": l} for u, l in zip("WNES", ["P", "P", "1H", "X"])]
    a = Allas(licitek=lic, ules="W", oszto="W")
    assert a.passzolt("W") and a.passzolt("N") and not a.passzolt("E") and not a.passzolt("S")


@pytest.mark.parametrize("kez, menet, vart", [
    ("8752.Q7.KQJT2.A6", ["P", "P", "1H", "X"], "1S"),     # #7: system on, 4 pikkel 1♠
    ("932.Q72.KQJ3.A62", ["P", "P", "1H", "X"], "2C"),     # passzolt lap: Drury kontra után is
])
def test_moha_kontra_utan(kez, menet, vart):
    from pathlib import Path
    from kibic.impex.rendszer_yaml import betolt
    from kibic.motor.kriterium import Parametertar
    from kibic.motor.rendszercheck import feloldas_forrasokbol
    from kibic.szolgaltatas.licit import licit_elemzes
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "MOHA_STAND")
    pt = Parametertar(rendszer_ertek=dict(g["MOHA_STAND"].parameterek))
    v = licit_elemzes({"hand": _pbn(kez), "seat": "W", "dealer": "W", "vulnerability": "none",
                       "auction": menet, "system": "MOHA_STAND", "test_mode": True},
                      lambda k, p, t=None: (f.sorok, pt))
    assert v["call"] == vart, v["explanation"]
