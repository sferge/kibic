"""A domain-mag: lapok, kezek, leosztások, értékelők."""
import pytest

from kibic.domain import (ERTEKELOK, Kez, Lap, Leosztas, beliben,
                          kovetkezo_ules, vonal)
import kibic.domain.ertekelo  # noqa: F401  (regisztrálja a bővítéseket)

DEAL = ("N:J3.9.AQT8.AQJ763 AT6.A754.42.KT85 "
        "K872.QJ83.J73.92 Q954.KT62.K965.4")


def test_lap_parse_mindket_sorrendben():
    assert str(Lap.parse("SA")) == "SA"
    assert str(Lap.parse("AS")) == "SA"
    with pytest.raises(ValueError):
        Lap.parse("XY")


def test_ules_forgatas_es_vonal():
    assert kovetkezo_ules("N") == "E"
    assert kovetkezo_ules("W") == "N"
    assert vonal("N") == vonal("S") == "NS"
    assert beliben("N", "NS") and not beliben("E", "NS")
    assert beliben("E", "ALL")


def test_kez_alak_es_kiegyensulyozottsag():
    k = Kez.pbn_bol("K872.QJ83.J73.92")
    assert k.alak == "4-4-3-2"
    assert k.rendezett_alak == "4-4-3-2"
    assert k.kiegyensulyozott
    assert not Kez.pbn_bol("AQ9765.KQ854.3.").kiegyensulyozott


def test_leosztas_kanonikus_oda_vissza():
    l = Leosztas.pbn_bol(DEAL, "N", "NONE")
    l2 = Leosztas.pbn_bol(l.pbn("N"), "N", "NONE")
    assert l.hash == l2.hash
    assert l.hcp("N") + l.hcp("E") + l.hcp("S") + l.hcp("W") == 40


def test_leosztas_hibas_kiosztast_elutasit():
    with pytest.raises(ValueError):
        Leosztas.pbn_bol("N:AKQ.AKQ.AKQ.AKQA " + " ".join(["..."] * 3))


@pytest.mark.parametrize("kod,varhato", [
    ("HCP", 16), ("NANO", 11), ("KONTROLL", 6),
    ("GYORSUTES", 4), ("EGYENLETES", 1),
    ("F1", 9), ("F2", 7), ("F4", 0),
])
def test_ertekelok_ismert_kezen(kod, varhato):
    # AKQ pikk + AK kőr, más figura nincs
    k = Kez.pbn_bol("AKQ32.AK54.765.32")
    assert ERTEKELOK[kod](k) == varhato


def test_ap_ket_iskolaja_kulonbozik():
    k = Kez.pbn_bol("AQ9765.KQ854.3.")   # 6-5-1-0, 11 HCP
    assert ERTEKELOK["AP_321"](k) == 11 + 3 + 2
    assert ERTEKELOK["AP_531"](k) == 11 + 5 + 3
