"""Az egyszínű elemző (a színkezelés taktikai szintje)."""
import pytest

from kibic.motor.tervszinkezeles import Feladat, kinalat, rangok


def _kinalat(x, y, m=99):
    X, Y = rangok(x), rangok(y)
    return kinalat(Feladat(X, Y, frozenset(range(2, 15)) - X - Y), m)


def test_adu_9_lap_kint_qjt7():
    k = _kinalat("K98654", "A32")
    assert k.eselyek[6][0] == pytest.approx(0.407, abs=0.001)    # 2-2
    assert k.eselyek[5][0] == pytest.approx(0.904, abs=0.001)    # nem 4-0
    assert k.biztos == 4


def test_ejtes_es_impassz_egy_szinben_nem_kombinalhato():
    """♦AK2 / JT94, vesztés nélkül 3 ütés: az ejtés és az impassz ugyanabban a
    színben nem adódik össze (a K előbb, aztán impassz: ~51,6%)."""
    k = _kinalat("AK2", "JT94", m=0)
    assert k.eselyek[3][0] == pytest.approx(0.516, abs=0.002)
    assert k.eselyek[2][0] == 1.0


def test_impassz_a_dama_fele():
    k = _kinalat("AQ5", "763")
    assert k.eselyek[2][0] == pytest.approx(0.548, abs=0.002)   # = a mindent látó korlát (♠A előbb, aztán impassz)
    assert k.eselyek[2][1].startswith("felvevő hív: A")   # a szingli K ellen előbb az A
