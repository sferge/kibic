"""A színtáblázat: kulcs, közelítés, eloszlás."""
import pytest

from kibic.motor import tervszintabla as tsz


def test_kulcs_szimmetrikus():
    assert tsz.kulcs({14, 12, 5}, {7, 6, 3}) == tsz.kulcs({7, 6, 3}, {14, 12, 5})
    assert len(tsz.kulcs({14}, {2})) == 13


def test_kozelites_es_eloszlas(tmp_path, monkeypatch):
    monkeypatch.setenv("KIBIC_SZINTABLA", str(tmp_path / "t.pkl"))
    monkeypatch.setattr(tsz, "_TABLA", None)
    p, pontos = tsz.eselyek({14, 13, 12, 5, 4}, {6, 3, 2})
    assert not pontos
    assert p[3] == pytest.approx(1.0) and p[5] == pytest.approx(0.678, abs=0.001)
    e, _ = tsz.eloszlas({14, 13, 12, 5, 4}, {6, 3, 2})
    assert sum(e.values()) == pytest.approx(1.0)


def test_szamol_pontos():
    t = tsz.szamol(tsz.kulcs({14, 12, 5}, {7, 6, 3}))
    assert t[99][2] == pytest.approx(0.548, abs=0.002)
