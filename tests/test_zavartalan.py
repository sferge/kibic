"""A zavartalan menet (a szerkesztő, 2026-10-24): ha az ellenfél akciói nem
zavartak meg minket, a licit megtartja a páros menet szerinti jelentését."""
import pytest

from test_konvenciok_2026_10_04 import _pbn


@pytest.fixture(scope="module")
def rendszerek():
    from pathlib import Path
    from kibic.impex.rendszer_yaml import betolt
    from kibic.motor.rendszercheck import feloldas_forrasokbol
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    return {r: feloldas_forrasokbol(g, r)[0] for r in ("KIBIC_STAND", "MOHA_STAND")}


def _h(rendszerek, rsz, kez, menet, oszto):
    from kibic.motor.kriterium import Parametertar
    from kibic.szolgaltatas.licit import licit_elemzes
    f = rendszerek[rsz]
    m = menet.split()
    ules = "NESW"[("NESW".index(oszto) + len(m)) % 4]
    v = licit_elemzes({"hand": _pbn(kez), "seat": ules, "dealer": oszto, "vulnerability": "none",
                       "auction": m, "system": rsz, "test_mode": True},
                      lambda k, p, t=None: (f.sorok, Parametertar()))
    return v["call"] or "P"


def test_zavartalan_menet_alapok():
    from kibic.motor.minta import zavartalan_menet

    def L(s, oszto="N"):
        u = "NESW".index(oszto)
        return [{"ules": "NESW"[(u + i) % 4], "licit": c} for i, c in enumerate(s.split())]
    assert zavartalan_menet(L("1C 1H"), "S", "1S") is not None      # nem zavart
    assert zavartalan_menet(L("1C 2H"), "S", "2S") is None          # elvette a szintet
    assert zavartalan_menet(L("1C 1H"), "S", "2H") is None          # az ő színük
    assert zavartalan_menet(L("1C 1H"), "S", "X") is None           # kontra: nincs páros párja
    assert zavartalan_menet(L("1C P P X"), "N", "1H") is None       # a partner passza lezárta volna
    assert zavartalan_menet(L("1C"), "E", "1S") is None             # az ellenfél nyitott


@pytest.mark.parametrize("rsz, kez, menet, oszto, vart", [
    # 2026-10-24: 1♣ 1♠ (X) 1NT után Nyugat 5-5-tel a másik színét mondja
    ("KIBIC_STAND", "AT543.K5.K9765.3", "P 1C P 1S X 1NT P", "N", "2D"),
    # P/C közbeszólás után is (a közbeszólás nem zavart)
    ("KIBIC_STAND", "K82.QJ4.AJ632.Q5", "1D P 1H 1S 1NT P 3D P", "N", "3H"),
    # #43: 1♦ (1♥) után 4 pikkel, 6 ponttal nem 1♠ (az 5+), nincs negatív kontra sem
    ("MOHA_STAND", "QT42.875.JT.K985", "P P 1D 1H", "W", "P"),
    # #173: 1♦ (1♠) 2♦ (egyszerű emelés, nem fordított) után a minimum passzol
    ("MOHA_STAND", "AQ3.864.AT52.Q73", "P P P 1D 1S 2D P", "E", "P"),
    # a versenyhelyzet saját elve előbb jön: törvény (LOTT) a fedőkereső előtt
    ("MOHA_STAND", "A2.KQJ932.K32.32", "1H 1S 2H 2S", "N", "3H"),
])
def test_zavartalan(rendszerek, rsz, kez, menet, oszto, vart):
    assert _h(rendszerek, rsz, kez, menet, oszto) == vart
