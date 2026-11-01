"""A tervező az élő játékban: bekapcsolás és a legegyszerűbb döntések."""
from kibic.domain import Lap
from kibic.motor import tervdontes as td
from kibic.motor.lejatszas import JatekAllas, Kontraktus


def _l(s):
    return [Lap.parse(x) for x in s.split()]


def test_bekapcsolas(monkeypatch):
    monkeypatch.delenv("KIBIC_TERVEZO", raising=False)
    monkeypatch.setenv("KIBIC_TERVEZO_PROFILOK", "kibic_terv, masik")
    assert td.bekapcsolva({"actor": {"profile_code": "kibic_terv"}})
    assert not td.bekapcsolva({"actor": {"profile_code": "kibic"}})
    monkeypatch.setenv("KIBIC_TERVEZO", "1")
    assert td.bekapcsolva({"actor": {}})


def test_nincs_dontes_a_legkisebb_lap():
    # 3NT Délről; Nyugat ♠K-t hív, az asztal (Észak) színt ad és nem üthet
    k = Kontraktus(3, "NT", felvevo="S")
    ja = JatekAllas(ules="N", kontraktus=k, asztal="N",
                    lathato={"S": _l("SQ S7 HA HK HQ DA DK DQ CA CK CQ CJ CT"),
                             "N": _l("S8 S5 S4 H2 H3 H4 D2 D3 D4 C2 C3 C4 C5")},
                    lejatszott=[("W", Lap.parse("SK"))],
                    legalis={l: str(l) for l in _l("S8 S5 S4")})
    d = td.dontes(ja, "teszt")
    assert d is not None and d.lap == Lap.parse("S4")


def test_vedo_nem_tervez():
    k = Kontraktus(3, "NT", felvevo="S")
    ja = JatekAllas(ules="W", kontraktus=k, asztal="N",
                    lathato={"W": _l("SK"), "N": _l("S8")}, lejatszott=[],
                    legalis={Lap.parse("SK"): "SK"})
    assert td.dontes(ja, "teszt") is None


def test_hatarido_utan_a_hatterben_folytatja(monkeypatch):
    import threading
    import time
    kesz = threading.Event()

    def lassu(ja, kulcs, megallito=None, naplo=None):
        time.sleep(0.5)
        kesz.set()
        return "eredmeny"
    monkeypatch.setattr(td, "dontes", lassu)

    class JA:
        lejatszott = []
        ules = "S"
    d, ok = td.dontes_hataridovel(JA(), "k", 0.05)
    assert (d, ok) == (None, False)
    # ugyanarra a pozícióra nem indul új tervezés; a futó eredményét kapja meg
    d, ok = td.dontes_hataridovel(JA(), "k", 2.0)
    assert (d, ok) == ("eredmeny", True) and kesz.is_set()
