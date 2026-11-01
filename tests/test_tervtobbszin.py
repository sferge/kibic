"""A többszínű elemző (adu + mellékszín együtt): egy színre az egyszínű elemzővel
egyező eredmény; lopással az adu körei is ütések."""
import pytest

from kibic.motor.tervtobbszin import Elemzo, Feladat, kod


def _lapok(s: str) -> frozenset:
    ki = set()
    for resz in s.split():
        sz, r = resz.split(":")
        i = "SHDC".index(sz)
        for c in r:
            ki.add(kod(i, "23456789TJQKA".index(c) + 2))
    return frozenset(ki)


def _esely(x, y, szinek, adu, k, m=99, **kw):
    X, Y = _lapok(x), _lapok(y)
    kint = frozenset(kod(i, r) for i in szinek for r in range(2, 15)) - X - Y
    return Elemzo(Feladat(X, Y, kint, szinek, adu, **kw)).megold(k, m)


def test_egy_szin_mint_az_egyszinu():
    assert _esely("D:AQ5", "D:763", (2,), None, 2)[0] == pytest.approx(0.548, abs=0.002)
    assert _esely("H:K98654", "H:A32", (1,), 1, 6)[0] == pytest.approx(0.407, abs=0.001)
    assert _esely("H:K98654", "H:A32", (1,), 1, 5)[0] == pytest.approx(0.904, abs=0.001)


def test_lopas_a_rovid_kezben():
    """♠A2 ♥AKQJT / ♥432: ♠A, a ♠2-t az asztal lopja, aztán öt kőr — 7 ütés,
    vesztés nélkül (csak ha egy védő pikk-színhiányos, lophat felül)."""
    p, _, leiras = _esely("S:A2 H:AKQJT", "H:432", (0, 1), 1, 7, 0)
    assert p > 0.99
