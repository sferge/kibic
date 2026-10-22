"""Eredménypontozás — a 0. fázis kilépési feltételének egyik fele."""
import pytest

from kibic.domain import Kontraktus, imp, pontszam, pontszam_ns


@pytest.mark.parametrize("kontr,utes,beli,varhato", [
    # A tanpartik ACBL-fájljából igazolt esetek
    ("3CX", 10, "NONE", 570),    # 120*2 + gém 300 + kontra 50 + többlet 100
    ("3NT",  8, "NS", -100),     # 1 bukás beliben (a felvevő É-D)
    ("4H",  10, "EW",   420),
    # Szlemek
    ("6NT", 12, "ALL", 1440),
    ("7S",  13, "NONE", 1510),
    # Bukások
    ("4S",   8, "ALL",  -200),   # 2 bukás beliben
    ("2SX",  6, "NONE", -300),   # 2 bukás kontrázva, beli nélkül: 100+200
    ("1NTXX", 7, "NONE", 560),   # 40*4=160 + gém 300 + rekontra 100
])
def test_pontszam_ismert_esetek(kontr, utes, beli, varhato):
    k = Kontraktus.parse(kontr, "N")
    assert pontszam(k, utes, beli) == varhato


def test_passzolt_lap_nulla():
    assert pontszam_ns(None, 0, "NONE") == 0


def test_ns_elojelezes():
    k_ns = Kontraktus.parse("4H", "N")
    k_ew = Kontraktus.parse("4H", "W")
    assert pontszam_ns(k_ns, 10, "NONE") == 420
    assert pontszam_ns(k_ew, 10, "NONE") == -420


@pytest.mark.parametrize("kul,varhato", [
    (0, 0), (10, 0), (20, 1), (50, 2), (420, 9), (-420, -9), (1100, 15),
])
def test_imp_atvaltas(kul, varhato):
    assert imp(kul) == varhato
