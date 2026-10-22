"""
A vonalak rendszere (mohabridzs-ai/1.2, 2026-10-01): a kibic az ellenfél
licitjeit az Ő rendszerük (vagy rendszercsaládjuk) szerint érti, és a
saját védekezése az ellenfél családjához / licitjének jelentéséhez
köthető (`ha: {ellenfel_csalad}`, `ha: {ellenfel_pont}`).
"""
from pathlib import Path

import pytest

from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol


def _pbn(s):
    return [sz + e for sz, l in zip("SHDC", s.split(".")) for e in l]


@pytest.fixture(scope="module")
def betolto():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt, forras_dict
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    forras_dict({"rendszer": {"kod": "PROBA_VED", "fajta": "KONVENCIO"},
                 "fejezetek": [{"fejezet": "erős treff ellen", "szabalyok": [
                     {"minta": "(1C) X", "ha": {"ellenfel_pont": "16+"}, "pont": "0+",
                      "hossz": {"S": "4+", "H": "4+"}, "prioritas": 70,
                      "alert": "PRÓBA: erős treff ellen mindkét nemes"},
                     {"minta": "(1C) 1D", "ha": {"ellenfel_csalad": "STRONG_CLUB"},
                      "pont": "0+", "hossz": {"D": "5+"}, "prioritas": 79,
                      "alert": "PRÓBA: erős treff család ellen"}]}]}, "p.yaml", g)
    forras_dict({"rendszer": {"kod": "PROBA_KARTYA", "fajta": "RENDSZER"},
                 "hivatkozasok": ["PROBA_VED", "KIBIC_STAND"]}, "k.yaml", g)
    tar: dict = {}

    def bet(kod, par=None, teszt=None):
        if kod not in tar:
            tar[kod] = feloldas_forrasokbol(g, kod)[0].sorok
        return tar[kod], Parametertar()
    return bet


def _licit(bet, pbn, menet, ellen=None, csaladok=None, ules="E"):
    from kibic.szolgaltatas.licit import licit_elemzes
    return licit_elemzes({"hand": _pbn(pbn), "seat": ules, "dealer": "N",
                          "vulnerability": "none", "auction": menet,
                          "system": "PROBA_KARTYA", "opponent_system": ellen,
                          "families": csaladok or {}, "test_mode": True}, bet)


def test_az_ellenfel_1treffje_az_o_rendszeruk_szerint(betolto):
    # a saját rendszerünk szerint az 1♣ 12-21; erős treff ellen 16+
    v = _licit(betolto, "432.32.5432.5432", ["1C"])
    assert v["constraints"]["N"]["points"] == [12, 21]
    v = _licit(betolto, "432.32.5432.5432", ["1C"], "STRONG_CLUB", {"NS": "STRONG_CLUB"})
    assert v["constraints"]["N"]["points"][0] == 16


def test_vedekezes_a_jelenteshez_kotve(betolto):
    # erős treff ellen él, természetes 1♣ ellen nem
    erős = _licit(betolto, "KJ32.QJ32.32.432", ["1C"], "STRONG_CLUB", {"NS": "STRONG_CLUB"})
    assert erős["call"] == "X" and "erős treff" in erős["alert"]["text"]
    termeszetes = _licit(betolto, "KJ32.QJ32.32.432", ["1C"], "NATURAL", {"NS": "NATURAL"})
    assert "PRÓBA" not in ((termeszetes.get("alert") or {}).get("text") or "")


def test_az_eros_treffesek_2treffje_ellen_nincs(betolto):
    v = _licit(betolto, "KJ32.QJ32.32.432", ["2C"], "STRONG_CLUB", {"NS": "STRONG_CLUB"})
    assert v["constraints"]["N"]["points"] == [11, 15]
    assert "PRÓBA" not in (v.get("alert") or {}).get("text", "")


def test_csaladhoz_kotott_vedekezes_csak_ha_tudjuk(betolto):
    tud = _licit(betolto, "2.32.KQJ432.5432", ["1C"], "STRONG_CLUB", {"NS": "STRONG_CLUB"})
    assert tud["call"] == "1D"
    nem_tud = _licit(betolto, "2.32.KQJ432.5432", ["1C"])
    assert nem_tud["call"] != "1D"


def test_amit_a_csaladjuk_nem_ir_le_azt_termeszetesen_ertjuk(betolto):
    # a mi 1♠ nyitásunk után az ellenfél 2♥ közbeszólása: a STRONG_CLUB
    # család nem írja le, a mi rendszerünk szerint természetes
    v = _licit(betolto, "AKQ32.32.K32.432", ["1S", "2H", "P", "P"],
               "STRONG_CLUB", {"EW": "STRONG_CLUB"}, ules="N")
    assert v["auction_understanding"][1]["understood"] is True


def test_vonal_feloldas(monkeypatch):
    from kibic.szolgaltatas import profil
    monkeypatch.setattr(profil, "ISMERT_FORRAS", lambda: {
        "KIBIC_STAND": {"kind": "RENDSZER", "family": "NATURAL"},
        "STRONG_CLUB": {"kind": "RENDSZERCSALAD", "family": "STRONG_CLUB"},
        "PRECISION_X": {"kind": "ALAPRENDSZER", "family": "STRONG_CLUB"}})
    monkeypatch.setattr(profil, "KINALT_FORRAS", lambda: [])
    # család kódja
    v = profil.vonal_feloldas({"game": {"systems": {"NS": "STRONG_CLUB", "EW": "KIBIC_STAND"}}}, "E")
    assert v["own"] == "KIBIC_STAND" and v["own_source"] == "systems"
    assert v["opponents_system"] == "STRONG_CLUB" and v["families"] == {"EW": "NATURAL", "NS": "STRONG_CLUB"}
    # ismert rendszer: annak a családja
    v = profil.vonal_feloldas({"game": {"systems": {"NS": "precision_x"}}}, "E")
    assert v["opponents_system"] == "PRECISION_X" and v["opponents_family"] == "STRONG_CLUB"
    # ismeretlen rendszer ismert családdal
    v = profil.vonal_feloldas({"game": {"systems": {
        "NS": {"code": "KOVACS_RENDSZER", "family": "STRONG_CLUB"}}}}, "E")
    assert v["opponents"] == "KOVACS_RENDSZER" and v["opponents_system"] == "STRONG_CLUB"
    # semmi: a profil, az ellenfél ismeretlen
    v = profil.vonal_feloldas({}, "E")
    assert v["own_source"] in ("profile", "default") and v["opponents_system"] is None
