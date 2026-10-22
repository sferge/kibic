"""
RENDSZERCSALÁD → ALAPRENDSZER → RENDSZER (2026-10-02): a YAML-ellenőrzés,
a katalógus (GET /v1/bridge/systems) és a PRECISION-alias.
"""
import pytest

from kibic.impex.rendszer_yaml import ForrasHiba, fajtak_ellenorzese, forras_dict
from kibic.szolgaltatas.katalogus import alaprendszer_terkep, katalogus


def _g(*doks):
    g = {}
    for i, d in enumerate(doks):
        forras_dict(d, f"f{i}.yaml", g)
    fajtak_ellenorzese(g)
    return g


ALAP = {"rendszer": {"kod": "ALAP", "fajta": "ALAPRENDSZER", "csalad": "NATURAL"},
        "fejezetek": [{"fejezet": "x", "szabalyok": [{"minta": "1NT", "pont": "15-17"}]}]}
ALAP2 = {"rendszer": {"kod": "ALAP_KETTO", "fajta": "ALAPRENDSZER", "csalad": "NATURAL"},
         "fejezetek": [{"fejezet": "x", "szabalyok": [{"minta": "1C", "pont": "12+"}]}]}
KONV = {"rendszer": {"kod": "KONV", "fajta": "KONVENCIO"},
        "fejezetek": [{"fejezet": "x", "szabalyok": [{"minta": "1NT-2C", "pont": "8+"}]}]}


def test_jo_hierarchia():
    pytest.importorskip("yaml")
    _g(ALAP, KONV, {"rendszer": {"kod": "PAR", "fajta": "RENDSZER", "csalad": "NATURAL"},
                    "hivatkozasok": ["KONV", "ALAP"]})


@pytest.mark.parametrize("par, resz", [
    ({"kod": "PAR", "fajta": "RENDSZER"}, "kötelező a `csalad`"),
    ({"kod": "PAR", "fajta": "RENDSZER", "csalad": "PRECISION"}, "nem rendszercsalád"),
    ({"kod": "PAR", "fajta": "RENDSZER", "csalad": "STRONG_CLUB"}, "nem egyezik"),
])
def test_csalad(par, resz):
    pytest.importorskip("yaml")
    with pytest.raises(ForrasHiba, match=resz):
        _g(ALAP, {"rendszer": par, "hivatkozasok": ["ALAP"]})


def test_pontosan_egy_alaprendszer():
    pytest.importorskip("yaml")
    with pytest.raises(ForrasHiba, match="nem hivatkozik alaprendszerre"):
        _g(KONV, {"rendszer": {"kod": "PAR", "fajta": "RENDSZER", "csalad": "NATURAL"},
                  "hivatkozasok": ["KONV"]})
    with pytest.raises(ForrasHiba, match="több alaprendszerre"):
        _g(ALAP, ALAP2, {"rendszer": {"kod": "PAR", "fajta": "RENDSZER", "csalad": "NATURAL"},
                         "hivatkozasok": ["ALAP", "ALAP_KETTO"]})
    # egy másik rendszeren át is számít
    _g(ALAP, {"rendszer": {"kod": "PAR", "fajta": "RENDSZER", "csalad": "NATURAL"},
              "hivatkozasok": ["ALAP"]},
       {"rendszer": {"kod": "PAR_KETTO", "fajta": "RENDSZER", "csalad": "NATURAL"},
        "hivatkozasok": ["PAR"]})


def test_a_valodi_rendszerek_rendben_vannak():
    pytest.importorskip("yaml")
    from pathlib import Path

    from kibic.impex.rendszer_yaml import alaprendszerei, betolt
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    assert alaprendszerei(g, "KIBIC_STAND")[0] == ["KIBICEGY_STAND"]
    assert g["POLISH"].fajta == "RENDSZERCSALAD"


def test_katalogus():
    rendszerek = [
        {"code": "NATURAL", "kind": "RENDSZERCSALAD", "family": "NATURAL", "name": "Term."},
        {"code": "STRONG_CLUB", "kind": "RENDSZERCSALAD", "family": "STRONG_CLUB"},
        {"code": "KIBICEGY_STAND", "kind": "ALAPRENDSZER", "family": "NATURAL"},
        {"code": "KIBIC_STAND", "kind": "RENDSZER", "family": "NATURAL", "name": "Kibic"},
        {"code": "ARVA", "kind": "RENDSZER", "family": "NATURAL"},
        {"code": "CSOMAG", "kind": "GYUJTEMENY", "family": "EGYEB"},
    ]
    hiv = [("KIBIC_STAND", "STAYMAN", True), ("KIBIC_STAND", "KIBICEGY_STAND", True),
           ("ARVA", "CSOMAG", True)]
    k = katalogus(rendszerek, hiv, {"KIBIC_STAND"}, "KIBIC_STAND")
    rsz = {r["code"]: r for r in k["systems"]}
    assert rsz["KIBIC_STAND"]["base_system"] == "KIBICEGY_STAND" and rsz["KIBIC_STAND"]["playable"]
    assert rsz["ARVA"]["base_system"] is None and "problem" in rsz["ARVA"]
    assert k["base_systems"][0]["systems"] == ["KIBIC_STAND"]
    cs = {c["code"]: c for c in k["families"]}
    assert cs["NATURAL"]["base_systems"] == ["KIBICEGY_STAND"] and cs["STRONG_CLUB"]["generic_system"]
    assert k["default_system"] == "KIBIC_STAND"
    assert alaprendszer_terkep({"A": "RENDSZER", "B": "ALAPRENDSZER"}, [("A", "B", False)]) == {"A": []}


def test_precision_csaladkent_eros_treff(monkeypatch):
    from kibic.szolgaltatas import profil
    monkeypatch.setattr(profil, "ISMERT_FORRAS", lambda: {
        "KIBIC_STAND": {"kind": "RENDSZER", "family": "NATURAL"},
        "STRONG_CLUB": {"kind": "RENDSZERCSALAD", "family": "STRONG_CLUB"}})
    monkeypatch.setattr(profil, "KINALT_FORRAS", lambda: [])
    v = profil.vonal_feloldas({"game": {"systems": {"NS": "PRECISION", "EW": "KIBIC_STAND"}}}, "E")
    assert v["opponents"] == "PRECISION" and v["opponents_family"] == "STRONG_CLUB"
    assert v["opponents_system"] == "STRONG_CLUB"
    v = profil.vonal_feloldas({"game": {"systems": {
        "NS": {"code": "X_PREC", "family": "PRECISION"}}}}, "E")
    assert v["opponents_family"] == "STRONG_CLUB"
