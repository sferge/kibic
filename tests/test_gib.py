"""GIB rendszer (1. szakasz, 2026-11-06): néhány jellemző licit a leírásból."""
from pathlib import Path

import pytest

from kibic.impex.rendszer_yaml import betolt
from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol
from kibic.szolgaltatas.licit import licit_elemzes


@pytest.fixture(scope="module")
def gib():
    g = betolt([Path("rendszerek/yaml")])
    f, _ = feloldas_forrasokbol(g, "GIB")
    pt = Parametertar(rendszer_ertek=dict(g["GIB"].parameterek))
    return lambda k, p, t=None: (f.sorok, pt)


def _licit(forras, kez, menet, ules="N"):
    v = licit_elemzes({"hand": [sz + e for sz, l in zip("SHDC", kez.split(".")) for e in l],
                       "seat": ules, "dealer": "N", "vulnerability": "none",
                       "auction": menet.split(), "system": "GIB", "test_mode": True}, forras)
    return v["call"]


@pytest.mark.parametrize("kez,menet,ules,vart", [
    ("AKJ72.KQ5.Q84.A7", "", "N", "1S"),              # 17 + 5-ös nemes: nem 1NT
    ("KQJ72.K5.Q84.A72", "", "N", "1NT"),             # 16, 5-ös nemes: 1NT
    ("AQ5.K8.KQ42.AQJ7", "", "N", "2NT"),
    ("A72.K5.K84.QJ765", "1C P", "S", "2C"),          # fordított emelés
    ("K872.QJ765.84.A7", "1NT P 2C P 2D P", "S", "3S"),   # Smolen
    ("AKQ72.K5.Q84.A72", "1H P", "S", "2S"),          # Soloway
    ("5.KQ8.QJ54.KJ742", "1NT P", "S", "2S"),         # minor Stayman
    ("T5.K8.Q42.AQJ872", "1NT P", "S", "2NT"),        # minor-transzfer treffre
    ("QJ5.AK875.K4.A72", "1H P 3H P 4NT P", "S", "5C"),   # RKC 0314: 3 kulcslap
    ("QJ5.K8754.K42.72", "1H P 3H P 4NT P", "S", "5D"),   # RKC 0314: 1 kulcslap
    # 2. szakasz: küzdelmi
    ("K43.AQT62.JT52.6", "1C P 1S", "W", "2H"),       # közbeszólás a második helyen
    ("KJT94.A654.J.T54", "1D X P", "W", "2S"),        # ugró válasz a kontrára: 9-12
    ("6.KQJ75.84.AKT87", "1C 2S", "S", "X"),          # 4-es nemes: negatív kontra, nem felüllicit
    ("AKQ43.KQT42.7.K7", "1NT", "E", "2D"),           # Cappelletti: mindkét nemes
])
def test_gib_licitek(gib, kez, menet, ules, vart):
    assert _licit(gib, kez, menet, ules) == vart


def test_gib_alap_utkozesmentes():
    from kibic.motor.rendszercheck import ellenoriz
    g = betolt([Path("rendszerek/yaml")])
    f, _ = feloldas_forrasokbol(g, "GIB")
    ids = {s.licitmenet_id for s in f.sorok if s.rendszer_kod.startswith("GIB")}
    er = ellenoriz(f.sorok, Parametertar(rendszer_ertek=dict(g["GIB"].parameterek)),
                   kez_db=60, csak_sorok=ids, feloldas=f)
    sajat = [u for u in er.utkozesek if set(u.sor_idk) & ids and all(
        i in ids for i in u.sor_idk)]
    assert not sajat, [(u.helyzet, u.licitek) for u in sajat]
