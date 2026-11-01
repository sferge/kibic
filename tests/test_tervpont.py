"""A RELEVANS_UTES szabály: mikor nem kell tervezni egy védői hívásnál."""
from kibic.domain import Lap
from kibic.motor.tervpont import relevans_vedoi_hivas


def _l(s: str) -> set[Lap]:
    return {Lap.parse(x) for x in s.split()}


def test_kicsik_mindket_kezben_nem_relevans():
    # ♠K hívás; nálunk ♠732 / ♠854, kint ♠AQJT9 — semmi sem válhat magassá
    rel, _ = relevans_vedoi_hivas(_l("S7 S3 S2 HA"), _l("S8 S5 S4 HK"), Lap.parse("SK"),
                                  _l("SK SA SQ SJ ST S9 S6"))
    assert not rel


def test_szinhiany_relevans():
    rel, miert = relevans_vedoi_hivas(_l("S7 S3 HA"), _l("HK H2"), Lap.parse("SK"), _l("SK SA SQ"))
    assert rel and "színhiány" in miert


def test_nagyobb_lapunk_relevans():
    rel, _ = relevans_vedoi_hivas(_l("SA S3"), _l("S5 S4"), Lap.parse("SK"), _l("SK SQ"))
    assert rel


def test_magassa_valhat_relevans():
    # ♠A hívás, nálunk ♠Q: kint a hívotton kívül csak a ♠K — egy menet után magas
    rel, _ = relevans_vedoi_hivas(_l("SQ S3"), _l("S5 S4"), Lap.parse("SA"), _l("SA SK SJ"))
    assert rel
    # ♠A hívás, nálunk ♠T: kint a K, Q, J — három nagyobb, két menet után sem magas
    rel, _ = relevans_vedoi_hivas(_l("ST S3"), _l("S5 S4"), Lap.parse("SA"), _l("SA SK SQ SJ"))
    assert not rel
    # menetek: 3 → már releváns
    rel, _ = relevans_vedoi_hivas(_l("ST S3"), _l("S5 S4"), Lap.parse("SA"), _l("SA SK SQ SJ"), 3)
    assert rel
