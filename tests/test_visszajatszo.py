"""Visszajátszó: licit- és lejátszás-ellenőrzés."""
from kibic.domain import Kontraktus, Leosztas
from kibic.motor.visszajatszo import licit_ellenoriz, visszajatszik

DEAL = ("N:J3.9.AQT8.AQJ763 AT6.A754.42.KT85 "
        "K872.QJ83.J73.92 Q954.KT62.K965.4")


def _licit(*tokenek, kezdo="N"):
    from kibic.domain import kovetkezo_ules
    ki, u = [], kezdo
    for t in tokenek:
        ki.append({"ules": u, "licit": t})
        u = kovetkezo_ules(u)
    return ki


def test_felvevo_az_aki_a_szint_eloszor_mondta():
    """1H-2H: az EMELÉS a partneré, de a felvevő a NYITÓ."""
    k, felvevo, hibak, _ = licit_ellenoriz(
        _licit("1H", "PASS", "2H", "PASS", "PASS", "PASS"), "N")
    assert not hibak
    assert str(k) == "2H" and felvevo == "N"


def test_kontra_szorzot_ad_de_felvevot_nem_valt():
    k, felvevo, hibak, _ = licit_ellenoriz(
        _licit("1C", "X", "1H", "X", "2C", "PASS", "PASS", "2D",
               "3C", "X", "PASS", "PASS", "PASS"), "N")
    assert not hibak
    assert str(k) == "3CX" and felvevo == "N"


def test_szabalytalan_licitek():
    _, _, hibak, _ = licit_ellenoriz(_licit("1H", "PASS", "1C"), "N")
    assert any("nem magasabb" in h for h in hibak)
    _, _, hibak2, _ = licit_ellenoriz(_licit("1H", "X", "XX", "X"), "N")
    assert hibak2


def test_szinkotelezettseg_megsertese_kiderul():
    l = Leosztas.pbn_bol(DEAL, "N", "NONE")
    k = Kontraktus.parse("3CX", "N")
    # E kezd; a második lapot S-nek kell a hívott színbe tennie
    er = visszajatszik(l, None, ["D4", "SJ"], jk_kontraktus=k, jk_felvevo="N")
    assert not er.rendben


def test_nem_letezo_lap_kiderul():
    l = Leosztas.pbn_bol(DEAL, "N", "NONE")
    k = Kontraktus.parse("3CX", "N")
    er = visszajatszik(l, None, ["SK"], jk_kontraktus=k, jk_felvevo="N")  # SK a délé
    assert any("nincs a kezében" in h for h in er.hibak)


def test_utes_gyoztese_aduval():
    l = Leosztas.pbn_bol(DEAL, "N", "NONE")
    k = Kontraktus.parse("3CX", "N")
    er = visszajatszik(l, None, ["D4", "DJ", "DK", "DA"],
                       jk_kontraktus=k, jk_felvevo="N")
    assert er.utesek[0].gyoztes == "N"       # DA viszi
    assert er.felvevo_utesek == 1
