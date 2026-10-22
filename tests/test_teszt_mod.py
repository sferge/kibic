"""
TESZT MÓD és JEGELT állapot.

  * élesben csak az ELFOGADOTT sorok kellenek a motornak;
  * teszt módban a JAVASOLT és FELULVIZSGALANDO is;
  * a JEGELT (és az ELVETETT) egyikben sem;
  * a licit-szolgáltatás kérésenként is kérhet teszt módot, és a válaszban
    jelzi, melyikben futott.
"""
from kibic.impex.rendszer_yaml import forras_dict
from kibic.motor.feloldas import (ELES_ALLAPOTOK, TESZT_ALLAPOTOK, _sorok,
                                  ervenyes_allapotok)
from kibic.motor.rendszercheck import feloldas_forrasokbol


class _Kurzor:
    """Csak azt jegyzi fel, milyen állapotokra szűrt a lekérdezés."""
    def __init__(self):
        self.arg = None

    def execute(self, sql, arg=()):
        self.sql, self.arg = sql, arg

    def fetchall(self):
        return []


def test_eles_mod_csak_elfogadott():
    assert ervenyes_allapotok(False) == ("ELFOGADOTT",)
    k = _Kurzor()
    _sorok(k, 7, "X", 0, ELES_ALLAPOTOK)
    assert k.arg == (7, "ELFOGADOTT")


def test_teszt_mod_a_javasoltat_is_de_a_jegeltet_nem():
    allapotok = ervenyes_allapotok(True)
    assert "JAVASOLT" in allapotok and "FELULVIZSGALANDO" in allapotok
    assert "JEGELT" not in allapotok and "ELVETETT" not in allapotok
    k = _Kurzor()
    _sorok(k, 7, "X", 0, TESZT_ALLAPOTOK)
    assert k.sql.count("%s") == len(k.arg)


def test_ellenorzes_kihagyja_a_jegelt_sort():
    g = {}
    forras_dict({"rendszer": {"kod": "JEG"}, "szabalyok": [
        {"minta": "1NT", "pont": "15-17"},
        {"minta": "2NT", "pont": "20-21", "allapot": "JEGELT"},
    ]}, "j", g)
    f, _ = feloldas_forrasokbol(g, "JEG")
    assert [s.minta for s in f.sorok] == ["1NT"]


def test_licit_szolgaltatas_keresenkent_teszt_mod():
    from kibic.szolgaltatas.licit import licit_elemzes
    hivasok = []

    def betolto(kod, par, teszt=None):
        hivasok.append(teszt)
        return [], None
    betolto.teszt_alap = False
    kez = ["S2", "S3", "S4", "H2", "H3", "H4", "D2", "D3", "D4", "D5",
           "C2", "C3", "C4"]
    alap = {"hand": kez, "seat": "N", "dealer": "N", "auction": [],
            "system": "X"}
    v = licit_elemzes(dict(alap), betolto)
    assert v["test_mode"] is False and hivasok[-1] is None
    v = licit_elemzes(dict(alap, test_mode=True), betolto)
    assert v["test_mode"] is True and hivasok[-1] is True


# --- alert és tanító nyom ----------------------------------------------

def _stayman_rendszer():
    from kibic.motor.kriterium import Parametertar
    g = {}
    forras_dict({"rendszer": {"kod": "MINI"}, "szabalyok": [
        {"minta": "1NT-2C", "pont": "8+", "prioritas": 58,
         "vagy": [{"hossz": {"S": "4+"}}, {"hossz": {"H": "4+"}}],
         "alert": "Stayman: 4-es nemest kérdez"},
        {"minta": "1NT-2D", "hossz": {"H": "5+"}, "alert": "Transzfer"},
        {"minta": "1NT-3NT", "pont": "10-15", "magyarazat": "Leállás",
         "prioritas": 40},
    ]}, "mini", g)
    f, _ = feloldas_forrasokbol(g, "MINI")
    bet = lambda k, p, teszt=None: (f.sorok, Parametertar())   # noqa: E731
    return bet


_KEZ = ["SK", "SQ", "S8", "S2", "HJ", "H7", "H3", "DA", "D9", "D2",
        "CQ", "C6", "C4"]                       # 12 FP, 4 pikk, 3 kőr


def test_alert_a_valaszban_emberi_magyarazattal():
    from kibic.szolgaltatas.licit import licit_elemzes
    v = licit_elemzes({"hand": _KEZ, "seat": "S", "dealer": "N",
                       "auction": ["1NT", "P"], "system": "MINI"},
                      _stayman_rendszer())
    assert v["call"] == "2C"
    assert v["alert"]["text"] == "Stayman: 4-es nemest kérdez"
    assert "figurapont" not in v["explanation"]       # nem a gépies szöveg
    assert "debug" not in v                            # élesben nincs nyom


def test_tanito_nyom_miert_nem():
    from kibic.szolgaltatas.licit import licit_elemzes
    v = licit_elemzes({"hand": _KEZ, "seat": "S", "dealer": "N",
                       "auction": ["1NT", "P"], "system": "MINI",
                       "test_mode": True}, _stayman_rendszer())
    d = v["debug"]
    assert d["hand"]["hcp"] == 12 and d["hand"]["shape"]["S"] == 4
    assert d["chosen"]["rule"] == "1NT-2C"
    nem = {n["rule"]: n for n in d["considered"]}
    assert nem["1NT-2D"]["result"] == "HAMIS"
    assert any("kőr hossz >= 5 (a kézben: 3)" in x
               for x in nem["1NT-2D"]["why_not"])
    assert nem["1NT-3NT"]["result"] == "IGAZ"         # teljesült, de kikapott
