"""MOHA_1NT — a Moha-kör 1NT-válaszai (a szerkesztő, 2026-10-24)."""
import pytest

from test_konvenciok_2026_10_04 import _licit, _pbn, kibic_stand  # noqa: F401


def _h(f, kez, menet):
    v = _licit(f.sorok, _pbn(kez), menet.split(), oszto="N")
    return v["call"] or "P"


@pytest.mark.parametrize("kez, menet, vart", [
    ("86.A3.654.Q97632", "1NT P", "2S"),            # gyenge 6 treff: transzfer
    ("86.53.QJ9832.T63", "1NT P", "2NT"),           # gyenge 6 káró: transzfer
    ("8.63.QJ984.KT632", "1NT P", "3C"),            # 5-5 minor, gyenge: leállás
    ("8.A3.KQ984.AT632", "1NT P", "2S"),            # 5-5 minor, gémerő: előbb 2♠
    ("KJ32.5.KQ32.Q932", "1NT P", "3H"),            # 4441 kőr szingli
    ("KJ32.Q932.KQ32.5", "1NT P", "3D"),            # 4441 minor szingli
    ("K82.Q93.J932.K32", "1NT P", "2C"),            # egyenletes 8-9 invit: Stayman
    ("AQ2.KJ3.K932.KJ2", "1NT P 2S P", "2NT"),      # max, 3 treff
    ("AQ32.KJ3.KQ32.32", "1NT P 2S P", "3C"),       # 16, de 2 kis treff: nem max
    ("AQ2.KJ3.K932.KJ2", "1NT P 3D P", "3H"),       # relé
    ("KJ32.Q932.KQ32.5", "1NT P 3D P 3H P", "3NT"), # treff szingli
    ("86.A3.654.A97632", "1NT P 2S P 2NT P", "3NT"),  # invit a max után, egyenletes
    ("86.A3.654.Q97632", "1NT P 2S P 2NT P", "3C"),   # gyenge a max után: 3♣
    ("86.A3.654.Q97632", "1NT P 2S P 3C P", "P"),     # gyenge a nem max után: passz
    ("A86.3.K54.AQ9763", "1NT P 2S P 3C P", "3H"),    # gémerő, kőr szingli
])
def test_moha_1nt(kibic_stand, kez, menet, vart):
    assert _h(kibic_stand, kez, menet) == vart


def test_5332_5_lapos_minorral_nem_transzfer(kibic_stand):
    # #124: 10 pont, 5332, 5 káró — nem transzfer
    assert _h(kibic_stand, "QT7.AQT.QT843.96", "1NT P") != "2NT"
