"""A negatív kontra utáni második licit sávjai és a kvázi gémforsz
(a szerkesztő, 2026-10-31: csapatteszt 1. leosztás, 1♣ (1♠) X (P) ?)."""
from test_szlem_szan import _h


def _n(kez, menet="P 1C 1S X P"):
    # a _h osztója W: W passzol, É nyit
    return _h(kez, menet, "N")


def test_18_pont_jo_6_treff_3c():
    # ♠T3 ♥K4 ♦AK2 ♣AKJT53 (18): nem a „kínunkban” 2♣, hanem 3♣ (17-19)
    assert _n("T3.K4.AK2.AKJT53") == "3C"


def test_12_16_saját_szín_2c():
    assert _n("93.K4.Q2.AKJT532") == "2C"


def test_riverz_18_5_4():
    assert _n("T3.K4.AK93.AKJ53") == "2D"


def test_18_gyenge_szin_fogas_nelkul_felullicit():
    # 18 pont, a treff nem elég jó a 3♣-hoz, pikkfogás nincs: 2♠
    assert _n("T3.AK.AK2.KJ9753") == "2S"
