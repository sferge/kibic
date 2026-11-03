"""A játékmódok gyors esélye (tervmodesely)."""
from kibic.motor import tervmodesely as tm
from kibic.motor import tervszintabla as tsz
from kibic.motor.tervszinkezeles import Elemzo, Feladat, rangok


def _h(s: str) -> dict:
    return {sz: set(rangok(r)) for sz, r in zip("SHDC", s.split("."))}


def test_kimenet_sorrend_csere(monkeypatch):
    # a táblázat kulcsa a két kezet felcserélheti: a mi elosztás-sorrendünk akkor is egyezzen
    X, Y = frozenset(rangok("KJ4")), frozenset(rangok("AT3"))
    k = tsz.kulcs(X, Y)
    kim = tsz.kimenet_szamol(k)
    monkeypatch.setattr(tsz, "_KIMENET", {k: kim})
    sz = tm.Szin(X, Y)
    e = Elemzo(Feladat(X, Y, sz.kint))
    for kk in ((1, 99), (2, 99), (3, 99), (2, 1)):
        km = e.kimenetek(*kk)
        # a két irányból számolt kezelés egyenlő értékű kezelések közt választhat (pl. a
        # kétirányú impassz iránya), de elosztásonként a két védő lapja ugyanaz: a
        # mindent látó csere után az ütések eloszlása egyezik
        sajat, tabla = {}, {}
        for i, (w, _, _) in enumerate(sz.sorok):
            sajat[km[i].utes] = sajat.get(km[i].utes, 0) + w
            u = sz.kim[kk][i][0]
            tabla[u] = tabla.get(u, 0) + w
        assert {u: round(p, 9) for u, p in sajat.items()} == {u: round(p, 9) for u, p in tabla.items()}
    # és a mapping a védők cseréjét követi: a ♠Q a felvevő (KJ4) mögött ülő védőnél (V1)
    # — az AT3 felől impasszolva — más eredményt ad, mint a másik oldalon; egy elosztásnál
    # a T és a táblázat kezelése nem mondhat ellent a mindent látó felső korlátnak
    for i in range(len(sz.sorok)):
        assert sz.kim[(3, 99)][i][0] <= sz.T()[i]


def test_biztos_szerzodes_nincs_nyereseg():
    # 7 szan 13 felső ütéssel: az alap 1, egyik mód sem nyer
    D = _h("AKQJ.AKQ.AKQ.AKQ")
    U = _h("T98.JT9.JT9.JT98")
    e = tm.mod_eselyek(D, U, None, 13, kimenet=False)
    assert e["ALAP"] > 0.999
    assert all(v[1] == 0 for m, v in e.items() if m != "ALAP")


def test_lopas_a_rovid_kezben_nyer():
    # 4♠: a felvevő ♥ vesztőit az asztal lopja (asztal ♥ színhiány, 3 adu)
    D = _h("AKQJ2.5432.A2.A2")
    U = _h("543.-.K8765.K876")
    e = tm.mod_eselyek(D, U, "S", 10, kimenet=False)
    assert e["LOPAS_ROVID"][1] > 0.3


def test_szan_vedoi_szin():
    # 3 szan: 9 felső ütés, de egy színben nincs megállónk — ha kiadjuk a hívást, elfutnak;
    # itt nem kell kiadni: az alap biztos
    D = _h("AKQ.AKQ.AKQ.32")
    U = _h("432.432.432.5432")
    e = tm.mod_eselyek(D, U, None, 9, kimenet=False)
    assert e["ALAP"] > 0.999
