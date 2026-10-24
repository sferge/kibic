"""Az indulások kimutatása: a jelleg és a jelentés."""
from kibic.cli import inditaselemzes as ie


def test_osztaly():
    assert ie.osztaly(0) == "NEM_BUKTATHATO" and ie.osztaly(1) == "MINDIG"
    assert ie.osztaly(0.2) == "AKTIV" and ie.osztaly(0.5) == "VEGYES" and ie.osztaly(0.9) == "PASSZIV"


def _e(kibic, ember, valodi_osztaly, minta_osztaly):
    lapok = [{"lap": "SA", "minta": {"vedo_utes": 4.1, "buktat": 0.6, "imp": 0.5},
              "valodi": {"vedo_utes": 4, "buktat": True, "imp": 0}},
             {"lap": "H2", "minta": {"vedo_utes": 3.9, "buktat": 0.5, "imp": 0.9},
              "valodi": {"vedo_utes": 3, "buktat": False, "imp": 10}}]
    return {"tabla": "x#1", "kontraktus": "4S", "felvevo": "S", "indito": "W", "beliallas": "NONE",
            "licit": "S:1S N:4S", "kez": {"S": "A", "H": "2", "D": "", "C": ""}, "lapok": lapok,
            "minta_db": 100, "lazitott": False, "kibic_lap": kibic, "ember_lap": ember, "szabaly": None,
            "jelleg_minta": {"arany": 0.5, "osztaly": minta_osztaly, "eloszlas": {}},
            "jelleg_valodi": {"arany": 0.5, "osztaly": valodi_osztaly, "buktato_szinek": ["S"]}}


def test_osszegzes_es_html():
    el = [_e("H2", "SA", "VEGYES", "AKTIV"), _e("SA", "H2", "VEGYES", "VEGYES")]
    o = ie.osszegzes(el)
    assert o["jelleg_szerint"]["VEGYES"] == {"db": 2, "kibic_imp": 10, "ember_imp": 10}
    assert o["becsult_vs_valodi"] == {"AKTIV": {"VEGYES": 1}, "VEGYES": {"VEGYES": 1}}
    assert o["biztossag"]["0,25–0,5 IMP"]["db"] == 1                 # H2: 0,5 vs SA: 0,9 → 0,4
    assert o["biztossag"]["az emberét látta jobbnak"]["db"] == 1
    assert o["kalibracio"]["50–70%"]["db"] == 2 and o["kalibracio"]["50–70%"]["kibic_lapja"] == 1
    h = ie.html_jelentes(el)
    assert h.startswith("<!doctype html>") and "♠Á" in h and "vegyes" in h



def test_hangolas_osszegzes():
    e = _e("H2", "SA", "VEGYES", "AKTIV")
    e["hangolas"] = {"1.0": {"barmely": 0.8, "buktat": {"SA": 0.6, "H2": 0.5}, "imp": {"SA": 0.5, "H2": 0.9}},
                     "0.3": {"barmely": 0.4, "buktat": {"SA": 0.3, "H2": 0.2}, "imp": {"SA": 0.6, "H2": 0.4}}}
    o = ie.osszegzes([e])
    a = o["hangolas"]["gém/szlem, kontrázatlan | súly 0.3"]
    assert a["kibic_varhato"] == 0.2 and a["kibic_valoban"] == 0 and a["legjobb_imp"] == 10
    assert o["hangolas"]["gém/szlem, kontrázatlan | súly 1.0"]["legjobb_imp"] == 0
    assert ie.vallalas_tipus("4SX") == "szín gém, kontrázva" and ie.vallalas_tipus("2NT") == "szan részszerződés"
    assert "Hangolás" in ie.html_jelentes([e])
