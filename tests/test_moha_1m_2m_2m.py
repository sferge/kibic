"""A szerkesztő 2026-10-05-i leosztása: 1♠-2♣-2♠-3♦.

A várakozó 2♠ után a válaszoló 3♦-je természetes, FOGÁS a káróban (nem
ígér plusz erőt, négy lapot sem; gémforsz marad, irány a 3NT). A nyitó a
még nem licitált színben (kőr) fogással 3NT-t mond; fogás nélkül 6+ pikkel
3♠. A 3♠ után a 4♣: a treff hosszabb a kárónál. Mindkét nem licitált
színben fogással a válaszoló rögtön 3NT (nincs plusz erő) / 2NT (plusz erő).
"""
from pathlib import Path

import pytest

from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol


@pytest.fixture(scope="module")
def moha():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "MOHA_STAND")
    return f.sorok


def _pbn(s):
    return [sz + e for sz, lapok in zip("SHDC", s.split(".")) for e in lapok]


def _licit(sorok, kez, menet, oszto="N"):
    from kibic.szolgaltatas.licit import licit_elemzes
    sorrend = "NESW"
    ules = sorrend[(sorrend.index(oszto) + len(menet)) % 4]
    return licit_elemzes({"hand": _pbn(kez), "seat": ules, "dealer": oszto,
                          "vulnerability": "none", "auction": menet,
                          "system": "MOHA_STAND", "test_mode": True, "inference": False},
                         lambda k, p, t=None: (sorok, Parametertar()))


ALAP = ["1S", "P", "2C", "P", "2S", "P"]


@pytest.mark.parametrize("kez, vart", [
    ("4.32.AQJ5.AKJ532", "3D"),        # káró fogás
    ("74.32.K82.AQJ532", "3D"),        # három lappal, plusz erő nélkül is
    ("74.K32.982.AKJ32", "3H"),        # kőr fogás
    ("74.Q32.KJ5.AQJ32", "3NT"),       # mindkettő, nincs plusz erő
    ("74.Q32.AQJ5.AKJ3", "2NT"),       # mindkettő, plusz erő
])
def test_valaszolo_fogast_mutat(moha, kez, vart):
    v = _licit(moha, kez, ALAP)
    assert v["call"] == vart
    assert v["source"] == "SZABALY"


@pytest.mark.parametrize("kez, vart", [
    ("KQJ862.AKT.73.84", "3NT"),      # a leosztás: AK10 a kőrben
    ("KQJ862.QT2.73.A4", "3NT"),
    ("KQJ862.432.73.AK", "3S"),       # nincs kőrfogás, 6 pikk
])
def test_nyito_a_3d_utan(moha, kez, vart):
    v = _licit(moha, kez, ALAP + ["3D", "P"])
    assert v["call"] == vart
    assert v["source"] == "SZABALY"


def test_az_ellenfel_erti_a_3d_t(moha):
    """A párbeszédablakot az ELLENFÉL kibicje nyitotta (a saját vonal
    licitjére sosem kérdezünk): most már érti, nem kér magyarázatot."""
    v = _licit(moha, "A32.QJ9.K82.Q976", ALAP + ["3D"])          # Nyugat
    meg = [m for m in v["auction_understanding"] if m["call"] == "3D"]
    assert meg and meg[0]["understood"]
    assert not v["explain_requests"]


def test_valaszolo_4c_a_3s_utan(moha):
    v = _licit(moha, "4.32.AQJ5.AKJ532", ALAP + ["3D", "P", "3S", "P"])
    assert v["call"] == "4C"
