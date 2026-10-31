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


def test_masodik_szandek_kontra():
    # p (p) p (1♦) ?  ♠AJ875 ♥QT73 ♦7 ♣QT4 (9, szingli káró): két nemes, kontra
    assert _h("AJ875.QT73.7.QT4", "P P P 1D", "W") == "X"


def test_masodik_szandek_hatos_szin_nem_kontra():
    # 6-4 a másik nemesben: nem kontra, hanem a jó szín (2-es szinten)
    assert _h("75.AKJ953.7.QT43", "P P P 1S", "W") == "2H"


def test_1nt_hatos_kor_transzfer_invit():
    # 2. parti: ♠2 ♥K98654 ♦763 ♣KQ6 — nem 2♣, hanem 2♦, majd 3♥
    assert _h("2.K98654.763.KQ6", "P 1NT P", "S") == "2D"
    assert _h("2.K98654.763.KQ6", "P 1NT P 2D P 2H P", "S") == "3H"


def test_1nt_otos_nemes_gemforsz_3nt():
    assert _h("32.KJ865.A73.K62", "P 1NT P 2D P 2H P", "S") == "3NT"
