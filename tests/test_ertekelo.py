"""
Az értékelő-ÉRTELMEZŐ: a definíciók adatként élnek, nem kódként.

A legfontosabb teszt a `test_definiciok_hibatlanok` és a
`test_ismert_kezen_ismert_ertekek`: ezek fogják el, ha valaki egy
definíciót elront az adatbázisban.
"""
import random

import pytest

from kibic.domain import ERTEKELOK, Kez
from kibic.domain.ertekelo import TAR, ErtekeloHiba, Ertekelotar
from kibic.domain.kartya import LAPOK, SZINEK, Lap

PROBA = "AKQ32.AK54.765.32"        # 5-4-3-2, 16 HCP


def test_minden_definicio_kiertekelheto():
    assert TAR.ellenoriz() == []


def test_a_definiciok_regisztralva_vannak():
    assert len(ERTEKELOK) == len(TAR.definiciok)
    assert "HCP" in ERTEKELOK and "ZAR" in ERTEKELOK


@pytest.mark.parametrize("kod,varhato", [
    ("HCP", 16), ("KONTROLL", 6), ("NANO", 11),
    ("GYORSUTES", 4), ("EGYENLETES", 1),
    ("F1", 9), ("F2", 7), ("F4", 0),
    ("HCP_DIST", 17), ("AP_321", 17), ("AP_531", 17),
])
def test_ismert_kezen_ismert_ertekek(kod, varhato):
    """AKQ pikk + AK kőr, 5-4-3-2 elosztás, 16 HCP."""
    assert ERTEKELOK[kod](Kez.pbn_bol(PROBA)) == varhato


def test_zar_a_hivatkozasokbol_all_ossze():
    """ZAR = HCP + KONTROLL + 2*L1 + L2 - L4 — három hivatkozással."""
    k = Kez.pbn_bol(PROBA)
    h = sorted(k.hosszak, reverse=True)
    varhato = (ERTEKELOK["HCP"](k) + ERTEKELOK["KONTROLL"](k)
               + (h[0] + h[1]) + (h[0] - h[3]))
    assert ERTEKELOK["ZAR"](k) == varhato


def test_korkoros_hivatkozas_hibat_dob():
    tar = Ertekelotar({
        "A": {"tagok": [{"tipus": "ERTEKELO", "kod": "B"}]},
        "B": {"tagok": [{"tipus": "ERTEKELO", "kod": "A"}]},
    })
    with pytest.raises(ErtekeloHiba):
        tar.ertek("A", Kez.pbn_bol(PROBA))


def test_ismeretlen_ertekelo_hibat_dob():
    with pytest.raises(ErtekeloHiba):
        TAR.ertek("NINCS_ILYEN", Kez.pbn_bol(PROBA))


def test_uj_metrika_kod_nelkul_felveheto():
    """A lényeg: új értékelő = adat, nem kód."""
    tar = Ertekelotar({
        "SAJAT": {"nev": "Próba", "tagok": [
            {"tipus": "LAP_SULY", "sulyok": {"A": 10}},
            {"tipus": "HOSSZ_TOBBLET", "felett": 4, "egyutthato": 2},
        ]}})
    k = Kez.pbn_bol("AKQ9876.A54.7.32")     # 2 ász, 7-es szín
    assert tar.ertek("SAJAT", k) == 10 * 2 + 2 * 3


def test_ertekek_stabilak_veletlen_kezeken():
    """Egyetlen metrika sem dob hibát, és mind véges értéket ad."""
    random.seed(42)
    pakli = [Lap(s, e) for s in SZINEK for e in LAPOK]
    for _ in range(200):
        random.shuffle(pakli)
        k = Kez(frozenset(pakli[:13]))
        for kod in TAR.definiciok:
            v = ERTEKELOK[kod](k)
            assert isinstance(v, float) and -100 < v < 100
