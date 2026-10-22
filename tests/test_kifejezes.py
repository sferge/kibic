"""Kifejezésfa: háromértékű logika, LEGALABB, LICREN-fordítás."""
import pytest

from kibic.domain import Kez
from kibic.impex.licren import feltetel_elemez, fordit
from kibic.motor.kifejezes import (Kontextus, ismeretlen_jelzok, kiertekel,
                                   leiras)

KIEGYENSULYOZOTT_12 = "AQ32.K54.Q76.J32"      # 4-3-3-3, 12 HCP
OTOS_PIKK_12 = "AQ932.K54.Q76.J3"             # 5-3-3-2, 12 HCP
ERŐS_21 = "AKQ2.KQ4.A76.KJ3"                  # 4-3-3-3, 21 HCP


def fa(licren: str) -> dict:
    return fordit(feltetel_elemez(licren))


# --- Alapműködés ------------------------------------------------------

def test_egyszeru_osszehasonlitas():
    assert kiertekel(fa("(S>4)"), Kez.pbn_bol(OTOS_PIKK_12)) is True
    assert kiertekel(fa("(S>4)"), Kez.pbn_bol(KIEGYENSULYOZOTT_12)) is False


def test_intervallum():
    assert kiertekel(fa("F[12,14]"), Kez.pbn_bol(KIEGYENSULYOZOTT_12)) is True
    assert kiertekel(fa("F[12,14]"), Kez.pbn_bol(ERŐS_21)) is False


def test_elosztas_pontos_es_rendezett():
    k = Kez.pbn_bol(OTOS_PIKK_12)     # pikk-kőr-káró-treff = 5-3-3-2
    assert kiertekel(fa("e5332"), k) is True
    assert kiertekel(fa("e3532"), k) is False
    assert kiertekel(fa("a5332"), k) is True


def test_negacio():
    assert kiertekel(fa("n(S>4)"), Kez.pbn_bol(KIEGYENSULYOZOTT_12)) is True


def test_szinhossz_rangsor():
    k = Kez.pbn_bol(OTOS_PIKK_12)
    assert kiertekel(fa("(L1=5)"), k) is True
    assert kiertekel(fa("(L4=2)"), k) is True


# --- Háromértékű logika ----------------------------------------------

def test_ismeretlen_jelzo_ismeretlent_ad():
    """A LICREN `P` képlete még tisztázatlan."""
    f = fa("(P>11)")
    assert kiertekel(f, Kez.pbn_bol(OTOS_PIKK_12)) is None
    assert ismeretlen_jelzok(f) == {"@PONT"}   # logikai hivatkozás, feloldásra vár


def test_hamis_ag_elnyeli_az_ismeretlent():
    """Ha egy ÉS másik ága megbukik, az ismeretlen már nem számít."""
    f = fa("(S<5)&(P>11)")            # a pikk feltétel HAMIS
    assert kiertekel(f, Kez.pbn_bol(OTOS_PIKK_12)) is False


def test_igaz_ag_elnyeli_az_ismeretlent_vagyban():
    f = fa("(S>4)o(P>99)")            # a pikk feltétel IGAZ
    assert kiertekel(f, Kez.pbn_bol(OTOS_PIKK_12)) is True


def test_ismeretlen_marad_ha_dontene():
    f = fa("(S>4)&(P>11)")            # a pikk IGAZ, a P dönt
    assert kiertekel(f, Kez.pbn_bol(OTOS_PIKK_12)) is None


# --- LEGALABB: az "indulóerő többségi döntéssel" ötlet ---------------

def _legalabb(m):
    """HCP>=12, ZAR>=26, LTC<=7 közül legalább m."""
    return {"t": "LEGALABB", "m": m, "gy": [
        {"t": "OSSZE", "op": ">=", "bal": {"t": "ERT", "kod": "HCP"},
         "jobb": {"t": "SZAM", "v": 12}},
        {"t": "OSSZE", "op": ">=", "bal": {"t": "ERT", "kod": "ZAR"},
         "jobb": {"t": "SZAM", "v": 26}},
        {"t": "OSSZE", "op": "<=", "bal": {"t": "ERT", "kod": "LTC"},
         "jobb": {"t": "SZAM", "v": 7}},
    ]}


@pytest.mark.parametrize("m,kez,varhato", [
    (1, KIEGYENSULYOZOTT_12, True),    # a HCP teljesül
    (2, KIEGYENSULYOZOTT_12, False),   # de sem Zar, sem LTC
    (1, "AQ9765.KQ854.3.2", True),     # 6-5-1-1: Zar és LTC igen
    (3, "AQ9765.KQ854.3.2", False),    # de a HCP csak 11
])
def test_legalabb_csomopont(m, kez, varhato):
    assert kiertekel(_legalabb(m), Kez.pbn_bol(kez)) is varhato


def test_es_es_vagy_a_legalabb_specialis_esete():
    k = Kez.pbn_bol(KIEGYENSULYOZOTT_12)
    assert kiertekel(_legalabb(3), k) == kiertekel(
        {"t": "ES", "gy": _legalabb(1)["gy"]}, k)
    assert kiertekel(_legalabb(1), k) == kiertekel(
        {"t": "VAGY", "gy": _legalabb(1)["gy"]}, k)


# --- Szkórhelyzet -----------------------------------------------------

@pytest.mark.parametrize("ules,beli,varhato", [
    ("N", "NONE", "A"), ("N", "ALL", "M"), ("N", "NS", "S"), ("N", "EW", "O"),
    ("E", "NS", "O"), ("E", "EW", "S"),
])
def test_szkorhelyzet(ules, beli, varhato):
    ktx = Kontextus(ules=ules, beliallas=beli)
    assert ktx.szkorhelyzet == varhato
    assert kiertekel(fa(f"@{varhato}"), Kez.pbn_bol(ERŐS_21), ktx) is True


# --- Emberi nyelvű leírás --------------------------------------------

def test_leiras_olvashato():
    sz = leiras(fa("(S>4)&(F[12,14])"))
    assert "pikk" in sz and "figurapont" in sz and "és" in sz
