"""A tervtár: fogalmak, tervsorok, hivatkozás (motor/terv.py)."""
import pytest

from kibic.domain import Lap
from kibic.motor import terv as tv


def _l(s):
    return {Lap.parse(x) for x in s.split()}


def test_hivatkozas_kivon_felulir(tmp_path):
    pytest.importorskip("yaml")
    (tmp_path / "t.yaml").write_text("""
- tipus: T
  szuro: {hiany: "1+", kiadhato: "2+"}
  szinenkent: igen
  cimkek: [X]
- valtozat: A
  alap: T
  ha: {szin.impasszolhato: igen}
- valtozat: B
  alap: A
  kivon: [kiadhato]
  felulir: {ha: {hiany: "2+"}}
""", encoding="utf-8")
    s = {x.kod: x for x in tv.tervsorok_yamlbol([tmp_path])}
    assert s["A"].feltetel == {"hiany": "1+", "kiadhato": "2+", "szin.impasszolhato": "igen"}
    assert s["B"].feltetel == {"hiany": "2+", "szin.impasszolhato": "igen"}
    assert s["B"].tipus == "T" and s["B"].szinenkent and s["B"].cimkek == ["X"]


def test_korkoros_hivatkozas(tmp_path):
    pytest.importorskip("yaml")
    (tmp_path / "t.yaml").write_text("- valtozat: A\n  alap: B\n- valtozat: B\n  alap: A\n",
                                     encoding="utf-8")
    with pytest.raises(tv.TervHiba):
        tv.tervsorok_yamlbol([tmp_path])


def test_fogalmak_impassz_es_lopas():
    # 4♠: a kézben ♠ÁKDB2 ♥ÁD ♦xx …, az asztalon ♥ kicsi, ♦ egy lap
    h = tv.Helyzet("S", 4, "S",
                   _l("SA SK SQ SJ S2 HA HQ D3 D4 D5 C2 C3 C4"),
                   _l("S5 S6 S7 H2 H3 H4 H5 D6 C5 C6 C7 C8 C9"))
    g, sz = tv.jellemzok(h)
    assert sz["H"]["impasszolhato"] and not sz["C"]["impasszolhato"]
    assert g["felvetel"] == "SZIN" and g["lopas_rovid"] >= 1 and g["vesztok"] >= 3


def test_feltetel_nyelv():
    assert tv._illik(3, "1+") and not tv._illik(0, "1+") and tv._illik(2, "1-3")
    assert tv._illik(True, "igen") and tv._illik(False, "nem") and tv._illik("SZAN", "SZAN")
    assert tv._illik(5, ["1-2", "4+"]) and not tv._illik(3, ["1-2", "4+"])


def test_a_tervtar_betoltheto():
    pytest.importorskip("yaml")
    from pathlib import Path
    sorok = tv.tervsorok_yamlbol([Path(__file__).resolve().parents[1] / "rendszerek" / "tervek"])
    assert {"KIMAGASITAS", "LOPAS", "BESZORITAS"} <= {s.tipus for s in sorok}
