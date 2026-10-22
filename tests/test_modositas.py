"""020: módosított konvenció, zárójeles lapszám, zónás pont, asztali pont, Bánky-szabály."""
import pytest

from kibic.impex.rendszer_yaml import (ForrasHiba, fajtak_ellenorzese,
                                       forras_dict, import_sorrend)
from kibic.motor.kriterium import Parametertar
from kibic.motor.licital import licit_rang
from kibic.motor.rendszercheck import feloldas_forrasokbol


def _g(*doks):
    g = {}
    for i, d in enumerate(doks):
        forras_dict(d, f"f{i}.yaml", g)
    fajtak_ellenorzese(g, hierarchia=False)
    return g


LEB = {"rendszer": {"kod": "LEB", "fajta": "KONVENCIO", "tema": "1NT után kettes közbeszólás"},
       "szabalyok": [{"minta": "1NT (2H) 2NT", "pont": "0-7", "magyarazat": "leállás"},
                     {"minta": "1NT (2H) 3NT", "pont": "10+", "magyarazat": "gém, fogással"},
                     {"minta": "1NT (2H) X", "pont": "8+", "magyarazat": "büntető"}]}
MOHA_LEB = {"rendszer": {"kod": "MLEB", "fajta": "KONVENCIO", "alapja": "LEB"},
            "szabalyok": [{"minta": "1NT (2H) X", "pont": "7+", "magyarazat": "értéket mutat"},
                          {"minta": "1NT (2H) 3NT", "torol": True}]}


def test_modositott_konvencio_felulir_es_kivesz():
    g = _g(LEB, MOHA_LEB, {"rendszer": {"kod": "PAR", "fajta": "RENDSZER"},
                            "hivatkozasok": ["MLEB"]})
    assert g["MLEB"].tema == "1NT után kettes közbeszólás"      # örökölt téma
    assert g["MLEB"].viszony == "MODOSITAS"
    f, _ = feloldas_forrasokbol(g, "PAR")
    szoveg = {s.minta: s.magyarazat for s in f.sorok}
    assert szoveg == {"1NT (2H) 2NT": "leállás",                # az alapból
                      "1NT (2H) X": "értéket mutat"}             # felülírva
    assert f.torolt and not f.tema_csere and not f.tema_utkozes  # az alap él mögötte


def test_torles_csak_modositasban_es_alap_import_elobb():
    with pytest.raises(ForrasHiba, match="torol"):
        _g({"rendszer": {"kod": "XX1", "fajta": "KONVENCIO"},
            "szabalyok": [{"minta": "1C", "torol": True}]})
    g = _g(LEB, MOHA_LEB)
    s = import_sorrend(g)
    assert s.index("LEB") < s.index("MLEB")


def test_zonas_pont_es_zarojeles_lapszam():
    g = _g({"rendszer": {"kod": "M1M", "fajta": "KONVENCIO"}, "szabalyok": [
        {"minta": "1H", "kulcs": "1H-34", "ha": {"ules": [3, 4]},
         "pont": {"O": "8-11", "S": "11"}, "hossz": {"H": "(4)5+"},
         "lehetoseg": {"hossz": {"S": "3+"}}, "prioritas": 61},
        {"minta": "1S", "hossz": {"S": "(4)5+"}, "pont": "12+"}]})
    sorok = {s.kulcs: s for s in g["M1M"].sorok}
    assert set(sorok) == {"1H-34", "1H-34~H4", "1S", "1S~S4"}
    assert sorok["1H-34~H4"].jelentes["hossz"] == {"H": {"min": 4, "max": 4},
                                                   "S": {"min": 3}}
    assert sorok["1H-34"].jelentes["pont"] == {"min": 8, "max": 11}
    assert sorok["1H-34~H4"].dontesi_mod == "SORREND"          # van feltétele
    assert sorok["1S~S4"].dontesi_mod == "MERLEGELO"           # nincs: mérlegelés
    assert "zónától függően: 8-11 (ők bellben) · 11 (mi bellben)" in \
        sorok["1H-34"].feltetel_szoveg
    assert "kőr hossz = 4" in sorok["1H-34~H4"].feltetel_szoveg
    assert sorok["1H-34~H4"].jegyzet.startswith("LEHETŐSÉG-SOR")


def test_adupont_negy_adunal_531():
    g = _g({"rendszer": {"kod": "BRG", "fajta": "KONVENCIO"}, "szabalyok": [
        {"minta": "1M-3C", "ap": "7-9", "hossz": {"M": "4+"}},
        {"minta": "1M-2M", "ap": "6-9", "hossz": {"M": "3"}}]})
    s = {x.minta: x for x in g["BRG"].sorok}
    assert "AP_531" in str(s["1M-3C"].feltetel)
    assert "AP_321" in str(s["1M-2M"].feltetel)
    assert s["1M-3C"].jelentes["pont"] == {"max": 9}           # FP legfeljebb ennyi


def test_banky_egyforma_jeloltek_kozul_a_legalacsonyabb():
    from kibic.szolgaltatas.licit import licit_elemzes
    g = _g({"rendszer": {"kod": "BNK"}, "szabalyok": [
        {"minta": "1S", "pont": "12+", "hossz": {"S": "4+"}, "prioritas": 60},
        {"minta": "1H", "pont": "12+", "hossz": {"H": "4+"}, "prioritas": 60}]})
    f, _ = feloldas_forrasokbol(g, "BNK")
    kez = ["SA", "SK", "S7", "S2", "HA", "HQ", "H7", "H2", "D9", "D4", "D3",
           "C6", "C4"]                                          # 13 FP, 4-4 nemes
    v = licit_elemzes({"hand": kez, "seat": "N", "dealer": "N", "auction": [],
                       "system": "BNK", "test_mode": True},
                      lambda k, p, t=None: (f.sorok, Parametertar()))
    assert v["call"] == "1H"
    assert v["debug"]["chosen"]["tie_break"]["among"] == ["1H", "1S"]
    assert licit_rang("P") < licit_rang("X") < licit_rang("1C") < licit_rang("7NT")


@pytest.mark.parametrize("beli, pikk, vart", [
    ("none", 3, "1H"),        # senki sincs bellben: 9+ kell, 10 van; 3 pikk
    ("none", 2, "P"),         # négy kőr, de csak 2 pikk: nem nyithat 1♥-t
    ("ns", 3, "P"),           # mi bellben, ők nem: 11+ kellene
])
def test_moha_1m_harmadik_kezben(beli, pikk, vart):
    from pathlib import Path

    from kibic.impex.rendszer_yaml import betolt
    from kibic.szolgaltatas.licit import licit_elemzes
    pytest.importorskip("yaml")
    utak = Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"
    g = betolt([utak / "konvenciok" / "moha_1m.yaml"])
    f, _ = feloldas_forrasokbol(g, "MOHA_1M")
    kez = ["HA", "HK", "H7", "H2"] + ["SQ", "S8", "S3"][:pikk] + \
          ["DJ", "D7", "D4", "D2"][:6 - pikk] + ["C9", "C6", "C3"]
    assert len(kez) == 13
    v = licit_elemzes({"hand": kez, "seat": "S", "dealer": "N",
                       "vulnerability": beli, "auction": ["P", "P"],
                       "system": "MOHA_1M"},
                      lambda k, p, t=None: (f.sorok, Parametertar()))
    assert (v["call"] or "P") == vart


def test_moha_1m_negy_negy_nemessel_1h():
    from pathlib import Path

    from kibic.impex.rendszer_yaml import betolt
    from kibic.szolgaltatas.licit import licit_elemzes
    pytest.importorskip("yaml")
    utak = Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"
    g = betolt([utak / "konvenciok" / "moha_1m.yaml"])
    f, _ = feloldas_forrasokbol(g, "MOHA_1M")
    kez = ["HA", "HK", "H7", "H2", "SQ", "S8", "S3", "S2",
           "DJ", "D7", "D4", "C6", "C3"]                  # 10 FP, 4-4 nemes
    v = licit_elemzes({"hand": kez, "seat": "S", "dealer": "N",
                       "vulnerability": "none", "auction": ["P", "P"],
                       "system": "MOHA_1M"},
                      lambda k, p, t=None: (f.sorok, Parametertar()))
    assert v["call"] == "1H"


def test_jegyzetek_rendszer_fejezet_szabaly():
    g = _g({"rendszer": {"kod": "JGY", "fajta": "KONVENCIO", "jegyzet": "Miért van ez."},
            "fejezetek": [{"fejezet": "F1", "jegyzet": "A fejezet oka.",
                           "szabalyok": [{"minta": "1C", "pont": "12+",
                                          "jegyzet": "A szabály oka."}]}]})
    r = g["JGY"]
    assert r.jegyzet == "Miért van ez." and r.fejezet_jegyzetek == {"F1": "A fejezet oka."}
    assert r.sorok[0].jegyzet == "A szabály oka."


def test_helyzet_szovege_a_ha_feltetelbol():
    g = _g({"rendszer": {"kod": "HSZ", "fajta": "KONVENCIO"}, "szabalyok": [
        {"minta": "1S", "kulcs": "1S-34", "ha": {"ules": [3, 4]},
         "pont": "8-10", "hossz": {"S": "(4)5+"}},
        {"minta": "1H", "ha": {"szkor": ["O", "A"]}, "pont": "10+"}]})
    s = {x.kulcs: x for x in g["HSZ"].sorok}
    assert s["1S-34"].ha_feltetel_szoveg == "3./4. kézben"
    assert s["1S-34~S4"].ha_feltetel_szoveg == "3./4. kézben"     # a lehetőség-sor is
    assert s["1H"].ha_feltetel_szoveg == \
        "zóna: ők bellben vagy senki"
