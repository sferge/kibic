"""A minor ORKC negatív válasza utáni leállás (a szerkesztő, 2026-10-23).

* A kérdező 4NT-ben áll le 5m helyett, ha a tudott minor fit legfeljebb
  8 lapos, és a vonal már licitált szant.
* A 4NT-re a válaszoló többlethosszal és nem szan jellegű lappal 5m-re
  javít; ha nálam a kétértelmű válasz jobbik esete van: szlem.
"""
import pytest

from test_konvenciok_2026_10_04 import _licit, _pbn, kibic_stand  # noqa: F401

MENET = ["P", "1H", "P", "1S", "P", "2D", "P", "3C", "P", "3NT", "P"]


def test_kerdezo_4nt_leallas(kibic_stand):
    # 2026-10-23, 17. leosztás: Nyugat 3 káró, a partner 4+ (7 lapos fit)
    v = _licit(kibic_stand.sorok, _pbn("AK876.5.K98.A943"), MENET + ["4D", "P", "4S", "P"])
    assert v["call"] == "4NT"


@pytest.mark.parametrize("kez, vart", [
    ("QT.AQJT7.Q532.Q7", "P"),       # nincs többlethossz: passz
    ("Q.AQJT7.Q8532.Q7", "5D"),      # 5 káró (4 ígért) + szingli: javítás
    ("QT.AQJ7.Q8532.Q7", "P"),       # 5 káró, de szan jellegű: passz
])
def test_valaszolo_4nt_utan(kibic_stand, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), MENET + ["4D", "P", "4S", "P", "4NT", "P"])
    assert (v["call"] or "P") == vart


def test_valaszolo_jobbik_eset_szlem(kibic_stand):
    # a 4♠ (0 vagy 3) után nálam a jobbik eset van (♥A ♦A ♣A): szlem
    v = _licit(kibic_stand.sorok, _pbn("Q.AQJT7.A8532.A7"),
               MENET + ["4D", "P", "4S", "P", "4NT", "P"])
    assert v["call"] == "6D"


def test_kerdezo_renonsszal_5m(kibic_stand):
    # renonsz és 7 lapos minor: a szan nem reális, marad az 5m
    v = _licit(kibic_stand.sorok, _pbn("J53..QJT8653.AK9"),
               ["1H", "P", "2D", "P", "2H", "P", "3C", "P", "3NT", "P", "4D", "P", "4S", "P"],
               oszto="N")
    assert v["call"] == "5D"
