"""Terítés (claim) a felvevő oldalán — motor/terites.py."""
from kibic.domain import LAPOK, SZINEK, Kontraktus, Lap
from kibic.motor import lejatszas as lj
from kibic.motor.terites import szoveg, terites


def _l(xs: str) -> list[Lap]:
    return [Lap.parse(x) for x in xs.split()]


def _allas(del_: str, eszak: str, kint: str, szin: str = "NT", ules: str = "S",
           szint: int = 3) -> lj.JatekAllas:
    """S a felvevő, N az asztal; `kint`: a védőknél lévő lapok; a többi már lement."""
    S, N, K = _l(del_), _l(eszak), _l(kint)
    assert len(S) == len(N) and len(K) == 2 * len(S)
    ismert = set(S) | set(N) | set(K)
    lement = [Lap(sz, e) for sz in SZINEK for e in LAPOK if Lap(sz, e) not in ismert]
    sor = "WNES"
    jatszott = [(sor[i % 4], l) for i, l in enumerate(lement)]
    kez = S if ules == "S" else N
    return lj.JatekAllas(ules=ules, kontraktus=Kontraktus(szint, szin, "", "S"), asztal="N",
                         lathato={"S": S, "N": N}, lejatszott=jatszott,
                         legalis={l: str(l) for l in kez})


def test_mind_a_harom_magas_lap():
    t = terites(_allas("SA SK SQ", "H2 H3 H4", "SJ ST S9 D2 D3 D4"))
    assert t.mind and t.utesek == 3 and t.elso.szin == "S"
    assert "mind a 3 ütés a miénk" in szoveg(t)


def test_blokkolt_szin_csak_egy_biztos():
    # ♠Á a kézben, ♠KD az asztalon, nincs átmenet: a ♠Á után a kézben ragadunk
    t = terites(_allas("SA H2", "SK SQ", "SJ ST H3 H4"))
    assert t.utesek == 1 and not t.mind


def test_az_asztal_eldobja_a_blokkolo_lapot():
    # ♥ÁK lehívása közben az asztal ♠K-t dob, a ♠2 → ♠Á átmenet
    t = terites(_allas("S2 HA HK", "SA SK D2", "SQ SJ ST D3 D4 D5"))
    assert t.mind


def test_kiaduzas_utan_a_mellekszin():
    # ♠ adu, kint ♠DB: két kör adu, utána a ♥Á biztos
    t = terites(_allas("SA SK HA", "S3 H2 DA", "SQ SJ C2 C3 C4 C5", szin="S"))
    assert t.mind and [l.hivott.szin for l in t.terv] == ["S", "S", "H"]


def test_kint_marad_adu_a_mellekszin_nem_biztos():
    # kint ♠DB10: két kör után egy adu még kint lehet — a ♥Á lopható
    t = terites(_allas("SA SK HA", "S3 H2 DA", "SQ SJ ST C3 C4 C5", szin="S"))
    assert t.utesek == 2 and not t.mind


def test_lopas_az_asztalon_es_atmenet():
    # kint nincs adu: ♣2-t az asztal lopja, onnan ♥3 → ♥Á
    t = terites(_allas("C2 HA", "S2 H3", "CA CK D2 D3", szin="S"))
    assert t.mind
    assert "lopva" in szoveg(t)


def test_vedonel_es_befejezetlen_utesben_nincs():
    a = _allas("SA SK SQ", "H2 H3 H4", "SJ ST S9 D2 D3 D4")
    a.ules = "E"
    assert terites(a) is None
    a = _allas("SA SK SQ", "H2 H3 H4", "SJ ST S9 D2 D3 D4")
    a.lejatszott.append(("S", Lap.parse("SA")))
    assert terites(a) is None


def test_jatek_dontes_teritessel_azonnal():
    a = _allas("SA SK SQ", "H2 H3 H4", "SJ ST S9 D2 D3 D4")
    e = lj.jatek_dontes(a, None, None, dd_fv=lambda *x: (_ for _ in ()).throw(AssertionError))
    assert e.dontes.szabaly == "TERITES" and e.dontes.lap.szin == "S"
    m = lj.meta(e)
    assert m["claim"]["tricks"] == 3 and m["claim"]["remaining"] == 3
    assert m["claim"]["statement"].startswith("Terítek")
    assert lj.magyarazat(e).startswith("Terítés")


def test_reszleges_terites_csak_ha_tobb_ut_nincs():
    # a biztos terv 1 ütés; ha a DD szerint minden mintában 1 — terítés, ha több is lehet — nem
    from types import SimpleNamespace as NS
    a = _allas("SA H2", "SK SQ", "SJ ST H3 H4")

    def dd(utes):
        def f(lo, jatszott, k):
            return [NS(lap=str(l), utesek=utes, felvevo_osszesen=None) for l in a.legalis]
        return f
    import random
    random.seed(1)
    e = lj.jatek_dontes(a, None, None, dd_fv=dd(1), ido_keret_s=5, db=8, mag=1)
    assert e.terites is not None and lj.meta(e)["claim"]["tricks"] == 1
    a = _allas("SA H2", "SK SQ", "SJ ST H3 H4")
    e = lj.jatek_dontes(a, None, None, dd_fv=dd(2), ido_keret_s=5, db=8, mag=1)
    assert e.terites is None and "claim" not in lj.meta(e)


# --- A terítés elbírálása ------------------------------------------------------

import pytest  # noqa: E402

from kibic.motor import terites as tm  # noqa: E402

ELOZMENY = [("W", "C2"), ("N", "C5"), ("E", "C8"), ("S", "CJ"),
            ("S", "CQ"), ("W", "C3"), ("N", "C6"), ("E", "C9"),
            ("S", "CK"), ("W", "C4"), ("N", "C7"), ("E", "CT")]
ESZAK = "D2 D3 D4 D5 D6 D7 D8 D9 DT DJ"


def _biro(del_: str, nyugat: str, kelet: str, ules: str = "W") -> lj.JatekAllas:
    """7NT, S a felvevő; három ütés lement (S vitte), S hív. A bíró: W (látja S-t és N-t)."""
    kez = {"S": _l(del_), "N": _l(ESZAK), "W": _l(nyugat), "E": _l(kelet)}
    lathato = {u: kez[u] for u in ("S", "N", ules)}
    return lj.JatekAllas(ules=ules, kontraktus=Kontraktus(7, "NT", "", "S"), asztal="N",
                         lathato=lathato,
                         lejatszott=[(u, Lap.parse(c)) for u, c in ELOZMENY],
                         legalis={l: str(l) for l in kez[ules]})


@pytest.fixture
def dd_valodi():
    pytest.importorskip("endplay")
    from kibic.solver.dds import lap_elemzes
    return lap_elemzes


def test_elbiral_biztos_magas_lapok(dd_valodi):
    a = _biro("SA SK SQ SJ ST HA HK HQ HJ HT",
              "S9 S8 S7 S6 S5 H9 H8 H7 DQ DK", "S4 S3 S2 H6 H5 H4 H3 H2 DA CA")
    e = tm.elbiral(a, "S", 10, dd_valodi)
    assert e.elfogad and e.ok == "BIZTOS" and e.cel == 13


def test_elbiral_rossz_terites(dd_valodi):
    # a ♠10 ötödik Nyugatnál: a ♠9 nem üt — tökéletes ellenjáték ellen 12
    a = _biro("SA SK SQ SJ S9 HA HK HQ HJ HT",
              "ST S8 S7 S6 S5 H9 H8 H7 DQ DK", "S4 S3 S2 H6 H5 H4 H3 H2 DA CA")
    e = tm.elbiral(a, "S", 10, dd_valodi)
    assert not e.elfogad and e.ok == "DD_KEVES" and e.dd == 12
    # egy ütés átadásával (9) viszont biztos
    e = tm.elbiral(a, "S", 9, dd_valodi)
    assert e.elfogad and e.ok == "BIZTOS"


def test_elbiral_a_valodi_allasban_kijon_de_nem_biztos(dd_valodi, monkeypatch):
    # a ♠10 második Nyugatnál: most kijön, de a terítő nem tudhatja
    monkeypatch.setattr(tm, "VILAG_MINTA", 40)
    a = _biro("SA SK SQ SJ S9 HA HK HQ HJ HT",
              "ST S8 H9 H8 H7 H6 H5 DQ DK DA", "S7 S6 S5 S4 S3 S2 H4 H3 H2 CA")
    e = tm.elbiral(a, "S", 10, dd_valodi)
    assert e.dd == 13 and not e.elfogad and e.ok == "NEM_BIZTOS"


def test_elbiral_vedo_teritese_hamis_dd():
    """Az ellenvonal terítése (a felvevő bírál): a cél a felvevő oldal ütésszáma."""
    from types import SimpleNamespace as NS
    a = _biro("SA SK SQ SJ S9 HA HK HQ HJ HT",
              "ST S8 S7 S6 S5 H9 H8 H7 DQ DK", "S4 S3 S2 H6 H5 H4 H3 H2 DA CA", ules="S")
    a.lathato["W"] = _l("ST S8 S7 S6 S5 H9 H8 H7 DQ DK")        # a terítő (W) keze nyitva
    a.lathato.pop("E", None)

    def dd(ertek):
        return lambda lo, j, k: [NS(lap="SA", utesek=0, felvevo_osszesen=ertek)]
    # W azt mondja: a hátralévő 10-ből 1 a miénk → a felvevőé 3 + 9 = 12
    e = tm.elbiral(a, "W", 1, dd(12))
    assert e.cel == 12 and e.elfogad
    e = tm.elbiral(a, "W", 1, dd(13))                           # a felvevő 13-at vihet
    assert not e.elfogad and e.ok == "DD_KEVES"


def test_atjaro_claim_valasz(dd_valodi):
    from kibic.szolgaltatas.atjaro import claim_dontes
    kez = {"S": "SA SK SQ SJ ST HA HK HQ HJ HT".split(), "N": ESZAK.split(),
           "W": "S9 S8 S7 S6 S5 H9 H8 H7 DQ DK".split()}
    k = {"request_id": "r:claim:1", "decision": "claim_response", "deadline_ms": 20000,
         "actor": {"seat": "W", "acting_for_seat": "W", "is_declarer": False},
         "state": {"dealer": "N", "contract": {"level": 7, "strain": "N"}, "declarer": "S",
                   "dummy": "N", "visible_hands": kez},
         "history": {"play": [{"seat": u, "card": c} for u, c in ELOZMENY]},
         "legal_actions": {"responses": ["accept", "reject"]},
         "claim": {"claimant": "S", "side": "NS", "tricks": 10, "remaining": 10,
                   "total_tricks": 13, "statement": "Terítek."}}
    v = claim_dontes(k)
    assert v["action"] == {"type": "claim_response", "accept": True}
    assert v["meta"]["source"] == "model" and "debug" not in v["meta"]["kibic"]
    k["test_mode"] = True
    k["claim"]["tricks"] = 10
    k["state"]["visible_hands"]["S"] = "SA SK SQ SJ S9 HA HK HQ HJ HT".split()
    k["state"]["visible_hands"]["W"] = "ST S8 S7 S6 S5 H9 H8 H7 DQ DK".split()
    v = claim_dontes(k)
    assert v["action"]["accept"] is False and v["meta"]["kibic"]["debug"]["reason"] == "DD_KEVES"
    assert "♠" not in v["explanation"]
