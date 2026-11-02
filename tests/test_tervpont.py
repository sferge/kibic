"""A RELEVANS_UTES szabály: mikor kell tervezni egy védői hívásnál."""
from kibic.domain import Lap
from kibic.motor.tervpont import DOBAS, NINCS_DONTES, UTES_DONTES, utes_fajta


def _l(s: str) -> set[Lap]:
    return {Lap.parse(x) for x in s.split()}


def test_nincs_dontes():
    # ♠K hívás; nálunk ♠Q73 / ♠854: nem üthetünk, színt adunk
    assert utes_fajta(_l("SQ S7 S3 HA"), _l("S8 S5 S4 HK"), Lap.parse("SK"), "H")[0] == NINCS_DONTES


def test_dobas():
    # szanzaduban színhiány: dobni kell
    assert utes_fajta(_l("S7 S3 HA"), _l("HK H2"), Lap.parse("SK"), None)[0] == DOBAS
    # adu van, de a színhiányos kézben nincs adu
    assert utes_fajta(_l("S7 S3 HA"), _l("DK D2"), Lap.parse("SK"), "H")[0] == DOBAS


def test_utes_dontes():
    assert utes_fajta(_l("SA S3"), _l("S5 S4"), Lap.parse("SK"), None)[0] == UTES_DONTES
    assert utes_fajta(_l("S7 S3"), _l("H5 H4"), Lap.parse("SK"), "H")[0] == UTES_DONTES


def test_deblokk_dontes():
    # Nyugat ♠A-t hív; nálunk ♠K3 / ♠D4, kint a ♠B — a K vagy a D magassá válik: döntés
    kint = _l("SA SJ S9 S8 S7 S6 S5 S2")
    assert utes_fajta(_l("SK S3 HA"), _l("SQ S4 HK"), Lap.parse("SA"), None, kint)[0] == UTES_DONTES
    # kint nélkül (régi hívás) marad a „nincs döntés”
    assert utes_fajta(_l("SK S3 HA"), _l("SQ S4 HK"), Lap.parse("SA"), None)[0] == NINCS_DONTES
