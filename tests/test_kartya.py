"""A konvenciókártya: a szabályokból generált rész és a kézzel írt blokk."""
from pathlib import Path

import pytest

from kibic.impex.rendszer_yaml import forras_dict
from kibic.motor.kartya import kartya_html, kartya_yamlbol, szep


def _forrasok():
    g = {}
    forras_dict({"rendszer": {"kod": "ALAPR", "fajta": "LICITRENDSZER",
                              "nev": "Alap"},
                 "hivatkozasok": ["STAYMAN"],
                 "szabalyok": [
                     {"minta": "1NT", "pont": "15-17", "elosztas": "BAL",
                      "magyarazat": "15-17, egyenletes"},
                     {"minta": "1H", "pont": "12-21", "hossz": {"H": "5+"},
                      "magyarazat": "5+ kőr"},
                     {"minta": "1M-2M", "pont": "6-9", "hossz": {"M": "3"},
                      "magyarazat": "Egyszerű emelés"},
                     {"minta": "2C", "pont": "22+", "alert": "Erős 2♣"},
                 ]}, "a", g)
    forras_dict({"rendszer": {"kod": "STAYMAN", "nev": "Stayman",
                              "leiras": "4-es nemest kérdez"},
                 "szabalyok": [{"minta": "1NT-2C", "pont": "8+",
                                "alert": "Stayman"},
                               {"minta": "1NT-2C-2D", "hossz": {"S": "0-3", "H": "0-3"}}]},
                "s", g)
    forras_dict({"rendszer": {"kod": "KARTYA1", "fajta": "KONVENCIOKARTYA",
                              "nev": "Próbakártya"},
                 "hivatkozasok": ["ALAPR"],
                 "kartya": {"altalanos": "Ötös nemes, erős szan",
                            "jelzesek": {"hívás": "alacsony hív"}}}, "k", g)
    return g


def test_szep():
    assert szep("1NT-2C") == "1NT–2♣" and szep("(1S) 2H") == "(1♠) 2♥"


def test_nyitasok_tablazata():
    k = kartya_yamlbol(_forrasok(), "KARTYA1")
    ny = {o["opening"]: o for o in k["openings"]}
    assert list(ny) == ["1H", "1NT", "2C"]
    assert ny["1NT"]["points"] == [15, 17]
    assert ny["1H"]["min_length"] == 5
    assert ny["2C"]["artificial"] is True
    valasz = {v["call"]: v for v in ny["1NT"]["responses"]}
    assert valasz["2♣"]["alert"] is True
    assert "Stayman" in ny["1NT"]["subsequent"]
    # a változós minta (1M-2M) a konkrét nyitásra oldódik fel
    assert "2♥" in {v["call"] for v in ny["1H"]["responses"]}


def test_kezzel_irt_blokk_es_konvenciok():
    k = kartya_yamlbol(_forrasok(), "KARTYA1")
    assert k["general"] == "Ötös nemes, erős szan"
    assert k["signals"] == {"hívás": "alacsony hív"}
    assert [c["code"] for c in k["conventions"]] == ["STAYMAN"]


def test_html():
    h = kartya_html(kartya_yamlbol(_forrasok(), "KARTYA1"))
    assert h.startswith("<!doctype html>") and "Próbakártya" in h
    assert "kitöltendő" in h                     # a hiányzó indulások jelölve


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / "rendszerek" / "yaml").is_dir(),
                    reason="nincs rendszerek/yaml")
def test_a_kibic_stand_kartyaja():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    k = kartya_yamlbol(g, "KIBIC_STAND")
    ny = {o["opening"]: o for o in k["openings"]}
    assert ny["1NT"]["points"] == [15, 17]
    assert ny["1C"]["min_length"] == 2              # 1TREFF_DUBLO: lehet dubló
    assert k["competitive"]["vs_nt"]
