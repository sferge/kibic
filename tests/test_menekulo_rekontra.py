"""MENEKULO_REKONTRA — a büntetőre passzolt kontra után (a szerkesztő, 2026-10-24)."""
import pytest

from test_konvenciok_2026_10_04 import kibic_stand, _pbn  # noqa: F401


def _h(f, kez, menet, oszto):
    from kibic.motor.kriterium import Parametertar
    from kibic.szolgaltatas.licit import licit_elemzes
    m = menet.split()
    ules = "NESW"[("NESW".index(oszto) + len(m)) % 4]
    v = licit_elemzes({"hand": _pbn(kez), "seat": ules, "dealer": oszto, "vulnerability": "both",
                       "auction": m, "system": "KIBIC_STAND", "test_mode": True},
                      lambda k, p, t=None: (f.sorok, Parametertar()))
    return v["call"] or "P"


@pytest.mark.parametrize("kez, menet, oszto, vart", [
    ("64.T9874.JT965.8", "1S P P X P P", "W", "XX"),          # 2026-10-24, 20. leosztás: Kelet
    ("AKJ87.K62.874.T4", "1S P P X P P XX P", "W", "2D"),     # Nyugat: a legolcsóbb 3 lapos
    (".AJ54.KQ43.KJ852", "1D X P P", "N", "XX"),              # az induló 5440-ese
    ("8743.Q2.765.T943", "1D X P P XX P", "N", "1S"),         # a legolcsóbb 4 lapos
    ("8.J9742.T8643.32", "1NT P P X P P", "N", "XX"),         # szan elől, 5-5
    ("6.874.52.QT98652", "1S P P X P P", "W", "2C"),          # egyszínű: a színt mondja
    ("643.T98.J965.874", "1S P P X P P", "W", "P"),           # nincs menekülő lap
    ("K2.AJ54.Q43.AJ82", "1C X P P", "N", "P"),               # csak egy másik 4+ lapos szín: nem
    (".AJ543.Q43.AKJ85", "1C X P P", "N", "XX"),              # 5530: a treff 5, a kőr 5
    ("AKQJ87.K62.874.4", "1S P P X P P XX P", "W", "P"),      # a felvevő bent marad: 6+ jó pikk
    ("8743.Q2.765.T943", "1D X P P XX P", "N", "1S"),         # (ismét) a legolcsóbb 4 lapos
    ("8.Q732.Q765.T943", "1D X P P XX P", "N", "P"),          # 4+ káró támogatás: bent marad
])
def test_menekulo_rekontra(kibic_stand, kez, menet, oszto, vart):
    assert _h(kibic_stand, kez, menet, oszto) == vart
