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
