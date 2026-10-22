"""
A YAML-forrású rendszerek próbája — adatbázis nélkül.

  * a fordító: egy kéz-leírásból feltétel ÉS jelentés;
  * a feloldás sorrendje: azonos mélységben a kártyán előbb álló nyer;
  * az ellentmondás-kereső megtalálja a szándékosan elrontott szabályt;
  * az import megőrzi a jóváhagyást, ha a tartalom nem változott;
  * a rendszerek/yaml/ minden fájlja lefordul, és a KIBIC_STAND feloldható.
"""
from pathlib import Path

import pytest

from kibic.domain import Kez
from kibic.impex.rendszer_yaml import (ForrasHiba, betolt, forras_dict,
                                       import_sorrend, sav, szabaly)
from kibic.motor.kifejezes import Kontextus, kiertekel
from kibic.motor.minta import minta_parse
from kibic.motor.rendszercheck import ellenoriz, feloldas_forrasokbol

GYOKER = Path(__file__).resolve().parents[1]
YAML_KONYVTAR = GYOKER / "rendszerek" / "yaml"


def _kez(pbn: str) -> Kez:
    return Kez.pbn_bol(pbn)


# --- elemzők -----------------------------------------------------------

@pytest.mark.parametrize("be, ki", [
    ("15-17", (15, 17)), ("12+", (12, None)), ("5", (5, 5)),
    ("0-7", (0, 7)), (6, (6, 6)),
])
def test_sav(be, ki):
    assert sav(be) == ki


def test_hibas_sav():
    with pytest.raises(ForrasHiba):
        sav("tizenkettő")


def test_egyetlen_licit_nyitas_paroslicit():
    """Az "1NT" nyitás pároslicit, nem küzdelmi (korábban KUZDELMI lett)."""
    m = minta_parse("1NT")
    assert m.paroslicit and m.ag == "PAROS"
    assert minta_parse("(1S) X").ag == "VEDEKEZO"


# --- a fordító ---------------------------------------------------------

def test_egy_leiras_ket_kimenet():
    s = szabaly({"minta": "1NT", "pont": "15-17", "elosztas": "BAL"}, 10, "Nyitás")
    assert s.jelentes["pont"] == {"min": 15, "max": 17}
    assert s.jelentes["hossz"]["S"] == {"min": 2, "max": 5}
    assert s.jelentes["forsz"] == "NEM"
    assert kiertekel(s.feltetel, _kez("AK2.KQ3.J432.Q32")) is True     # 15, 4333
    assert kiertekel(s.feltetel, _kez("AK2.KQ3.J432.Q3.2".replace(".2", "2"))) is True
    assert kiertekel(s.feltetel, _kez("AKQ2.KQ32.J432.2")) is False     # szingli


def test_valtozo_es_szarmaztatott_szin():
    """A `@oM` a kötött nemes párja — a feltételben és a jelentésben is."""
    s = szabaly({"minta": "1M-2M-3oM", "hossz": {"oM": "0-1"}}, 10, None)
    ktx = Kontextus(kotesek={"M": "H"})
    assert kiertekel(s.feltetel, _kez("5.AKJ32.KQ42.A32"), ktx) is True
    assert kiertekel(s.feltetel, _kez("52.AKJ32.KQ4.A32"), ktx) is False
    assert s.jelentes["hossz"] == {"@oM": {"min": 0, "max": 1}}


def test_vagy_es_alert():
    s = szabaly({"minta": "1NT-2C", "pont": "8+",
                 "vagy": [{"hossz": {"S": "4+"}}, {"hossz": {"H": "4+"}}],
                 "alert": "Stayman"}, 10, None)
    assert s.alert and s.magyarazat == "Stayman"
    assert len(s.jelentes["vagy"]) == 2
    assert kiertekel(s.feltetel, _kez("AJ32.K32.Q32.432")) is True
    assert kiertekel(s.feltetel, _kez("AJ3.K32.Q432.432")) is False


def test_fogas_es_aszok():
    s = szabaly({"minta": "1D-2C-2H", "fogas": ["H"]}, 10, None)
    assert kiertekel(s.feltetel, _kez("432.K3.AQ432.432")) is True     # Kx
    assert kiertekel(s.feltetel, _kez("432.Q3.AK432.432")) is False    # Dx
    a = szabaly({"minta": "1NT-4C-4S", "aszok": 2}, 10, None)
    assert kiertekel(a.feltetel, _kez("A32.A32.K432.432")) is True


def test_ismeretlen_kulcs_hiba():
    with pytest.raises(ForrasHiba, match="ismeretlen kulcs"):
        szabaly({"minta": "1NT", "pnt": "15-17"}, 10, None)


def test_yaml_rendszer_prioritas_dont():
    """Minden YAML-sor azonos specifikusságú: a prioritás dönt köztük."""
    a = szabaly({"minta": "1M-2M-3C"}, 10, None)
    b = szabaly({"minta": "1M-2M-3oM"}, 20, None)
    assert a.specifikussag == b.specifikussag


# --- feloldás: a hivatkozások sorrendje -------------------------------

def _forrasok():
    g = {}
    forras_dict({"rendszer": {"kod": "ALAP", "fajta": "LICITRENDSZER"},
                 "szabalyok": [{"minta": "2D", "pont": "22+", "magyarazat": "alap"}]},
                "alap", g)
    forras_dict({"rendszer": {"kod": "MULTI"},
                 "szabalyok": [{"minta": "2D", "pont": "6-10", "hossz": {"H": "6+"},
                                "magyarazat": "multi"}]}, "multi", g)
    forras_dict({"rendszer": {"kod": "KARTYA", "fajta": "KONVENCIOKARTYA"},
                 "hivatkozasok": ["MULTI", "ALAP"]}, "kartya", g)
    return g


def test_azonos_melysegben_az_elobb_hivatkozott_nyer():
    f, hianyzo = feloldas_forrasokbol(_forrasok(), "KARTYA")
    assert not hianyzo
    ketto = [s for s in f.sorok if s.kulcs == "2D"]
    assert [s.magyarazat for s in ketto] == ["multi"]
    assert f.sorrendi_felulirasok and "MULTI" in f.sorrendi_felulirasok[0]


def test_kikapcsolt_hivatkozas_kimarad():
    g = _forrasok()
    g["KARTYA"].hivatkozasok[0].aktiv = False
    f, _ = feloldas_forrasokbol(g, "KARTYA")
    assert [s.magyarazat for s in f.sorok if s.kulcs == "2D"] == ["alap"]


def test_import_sorrend_elobb_a_hivatkozott():
    sorrend = import_sorrend(_forrasok())
    assert sorrend.index("KARTYA") > sorrend.index("MULTI")


# --- ellentmondás-kereső ----------------------------------------------

def test_ellentmondas_kereso_megtalalja_az_utkozest():
    g = {}
    forras_dict({"rendszer": {"kod": "HIBAS"}, "szabalyok": [
        {"minta": "1C", "pont": "12-21", "hossz": {"C": "3+"}},
        {"minta": "1D", "pont": "12-21", "hossz": {"D": "3+"}},
    ]}, "hibas", g)
    f, _ = feloldas_forrasokbol(g, "HIBAS")
    er = ellenoriz(f.sorok, kez_db=120)
    assert not er.rendben
    assert er.utkozesek[0].licitek == ("1C", "1D")


def test_ellentmondas_kereso_prioritassal_rendben():
    g = {}
    forras_dict({"rendszer": {"kod": "JO"}, "szabalyok": [
        {"minta": "1C", "pont": "12-21", "hossz": {"C": "3+"}, "prioritas": 50},
        {"minta": "1D", "pont": "12-21", "hossz": {"D": "3+"}, "prioritas": 51},
    ]}, "jo", g)
    f, _ = feloldas_forrasokbol(g, "JO")
    assert ellenoriz(f.sorok, kez_db=120).rendben


# --- import: a jóváhagyás megőrzése -----------------------------------

def test_jovahagyas_megmarad_ha_a_tartalom_valtozatlan():
    from kibic.cli.rendszerimport import uj_allapotok
    s = szabaly({"minta": "1NT", "pont": "15-17"}, 10, None)
    regi = [("1NT", "1NT", s.feltetel, s.jelentes, None, "ELFOGADOTT", "sanyi", None)]
    assert uj_allapotok([s], regi)[0][:2] == ("ELFOGADOTT", "sanyi")


def test_valtozott_elfogadott_sor_felulvizsgalando():
    from kibic.cli.rendszerimport import uj_allapotok
    regi_s = szabaly({"minta": "1NT", "pont": "15-17"}, 10, None)
    uj_s = szabaly({"minta": "1NT", "pont": "14-16"}, 10, None)
    regi = [("1NT", "1NT", regi_s.feltetel, regi_s.jelentes, None, "ELFOGADOTT", "x", None)]
    assert uj_allapotok([uj_s], regi)[0][0] == "FELULVIZSGALANDO"
    assert uj_allapotok([uj_s], [])[0][0] == "JAVASOLT"


# --- a valódi forrásfájlok --------------------------------------------

@pytest.mark.skipif(not YAML_KONYVTAR.is_dir(), reason="nincs rendszerek/yaml")
def test_minden_forrasfajl_lefordul_es_a_kartya_feloldhato():
    pytest.importorskip("yaml")
    g = betolt([YAML_KONYVTAR])
    assert {"KIBICEGY_STAND", "KIBIC_STAND", "STAYMAN"} <= set(g)
    f, hianyzo = feloldas_forrasokbol(g, "KIBIC_STAND")
    assert set(hianyzo) <= {"FESU"}              # az SQL-lel betöltött
    assert len(f.sorok) > 500


@pytest.mark.skipif(not YAML_KONYVTAR.is_dir(), reason="nincs rendszerek/yaml")
def test_az_alaprendszer_nyitasai_ellentmondasmentesek():
    pytest.importorskip("yaml")
    g = betolt([YAML_KONYVTAR])
    f, _ = feloldas_forrasokbol(g, "KIBICEGY_STAND")
    nyitasok = [s for s in f.sorok if "-" not in s.minta and "(" not in s.minta]
    er = ellenoriz(nyitasok, kez_db=400)
    assert er.rendben, er.jelentes()


# --- a passz-elv: csak ha a partner nem forszolt ------------------------

def test_passz_elv_forsz_nelkul_passzol_forszra_nem():
    from kibic.motor.kriterium import Parametertar
    from kibic.szolgaltatas.licit import licit_elemzes
    g = {}
    forras_dict({"rendszer": {"kod": "ELVES"}, "szabalyok": [
        {"minta": "1NT", "pont": "15-17", "elosztas": "BAL"},
        {"minta": "2C", "pont": "22+", "forsz": "EGY_MENET"},
        {"minta": ".. nA P", "fajta": "ELV", "ha": {"partner_forszol": False}},
        {"minta": ".. nNT P", "fajta": "ELV", "ha": {"partner_forszol": False}},
    ]}, "elves", g)
    f, _ = feloldas_forrasokbol(g, "ELVES")
    bet = lambda k, p: (f.sorok, Parametertar())            # noqa: E731
    kez = ["S2", "S3", "S4", "H2", "H3", "H4", "D2", "D3", "D4", "D5",
           "C2", "C3", "C4"]
    v = licit_elemzes({"hand": kez, "seat": "S", "dealer": "N",
                       "auction": ["1NT", "P"], "system": "ELVES"}, bet)
    assert v["call"] == "P" and v["source"] == "ELV"
    v = licit_elemzes({"hand": kez, "seat": "S", "dealer": "N",
                       "auction": ["2C", "P"], "system": "ELVES",
                       "gap_principle": False}, bet)
    assert v["call"] is None and v["source"] == "NINCS"
    # a hézag-elvvel: forszra nem passzol (a legolcsóbb licitet mondja)
    v = licit_elemzes({"hand": kez, "seat": "S", "dealer": "N",
                       "auction": ["2C", "P"], "system": "ELVES"}, bet)
    assert v["call"] not in (None, "P") and v["source"] == "HEZAG"
