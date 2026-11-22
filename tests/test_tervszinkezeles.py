"""Az egyszínű elemző (a színkezelés taktikai szintje)."""
import pytest

from kibic.motor.tervszinkezeles import Feladat, kinalat, rangok


def _kinalat(x, y, m=99):
    X, Y = rangok(x), rangok(y)
    return kinalat(Feladat(X, Y, frozenset(range(2, 15)) - X - Y), m)


def test_adu_9_lap_kint_qjt7():
    k = _kinalat("K98654", "A32")
    assert k.eselyek[6][0] == pytest.approx(0.407, abs=0.001)    # 2-2
    assert k.eselyek[5][0] == pytest.approx(0.904, abs=0.001)    # nem 4-0
    assert k.biztos == 4


def test_ejtes_es_impassz_egy_szinben_nem_kombinalhato():
    """♦AK2 / JT94, vesztés nélkül 3 ütés: az ejtés és az impassz ugyanabban a
    színben nem adódik össze (a K előbb, aztán impassz: ~51%; 2026-11-22 óta a védők
    bármelyik lapot tehetik — MINDEN_VEDOLAP —, 51,2%)."""
    k = _kinalat("AK2", "JT94", m=0)
    assert k.eselyek[3][0] == pytest.approx(0.512, abs=0.002)
    assert k.eselyek[2][0] == 1.0


def test_impassz_a_dama_fele():
    # (2026-11-22, MINDEN_VEDOLAP) a védők bármelyik lapot tehetik: a ♠Kx Nyugatnál
    # nem különböztethető meg Kelet ♠Kx-étől (eddig a gépi védő kis lapjaiból igen —
    # 54,8%); garantáltan az impassz és a szingli K: 50,5%
    k = _kinalat("AQ5", "763")
    assert k.eselyek[2][0] == pytest.approx(0.505, abs=0.002)


def test_elbukott_cel_utan_abbahagyja():
    """♥AK842 a színhiányos (5 adus) kéz mellett, 3 ütés vesztés nélkül (két lopással a
    5. kör): 4-4-nél sikerül. Ha a látott lapokból már kiderült, hogy nem sikerülhet
    (pl. 5-3), a felvevő abbahagyja a színt — nem hív vesztőre (2026-11-03: a
    próba-szín kudarca így nem visz el ütést a következő technika elől)."""
    from kibic.motor.tervszinkezeles import Elemzo, Feladat, rangok
    e = Elemzo(Feladat(frozenset(), rangok("AK842"), rangok("QJT97653"), 11, 11, 5, 0))
    km = e.kimenetek(3, 0)
    assert abs(e.esely(3, 0)[0] - 0.341) < 0.002
    ot_harom = [km[i] for i, (v1, v2, _) in enumerate(e.tart) if sorted((len(v1), len(v2))) == [3, 5]]
    # (néhány tartásnál a vesztés még a kudarc kiderülése előtt jön — az elkerülhetetlen)
    assert sum(1 for k in ot_harom if k.vesztes == 0) >= 0.9 * len(ot_harom)
    assert all(k.utes == 2 for k in ot_harom)


def test_relevans_lapok_a_kis_lapok_egyformak():
    """A szerkesztő (2026-11-22, BM A-11): ♦DB2 / ♦K9876, hiányzik az Á10543, 3 ütés
    legfeljebb 1 vesztéssel. Csak a releváns lapokat (♦Á, ♦10) különböztetjük meg; a
    ♦5, ♦4, ♦3 egyformák (x). Eddig a gépi védő szabályszerű kislap-választásából a
    felvevő „kiolvasta” a többi lap helyét: a szingli ♦4 ellen más eredmény jött ki,
    mint a szingli ♦3 vagy ♦5 ellen."""
    from kibic.motor.tervszinkezeles import vedo_csoportok
    from kibic.motor.tervszinpolitika import SzinPolitika

    # a népszerűbb (több tartásban tehető) lapot választja az, akinek mindegy
    assert vedo_csoportok([(14,), (10, 14)], [1.0, 1.0]) == [14, 14]
    p = SzinPolitika(frozenset({12, 11, 2}), frozenset({13, 9, 8, 7, 6}),
                     frozenset({14, 10, 5, 4, 3}), 12, 12, 3, 1)
    el = p.el
    allapot, idx, l1, l2, k, m = p.node
    ossz = sum(el.tart[i][2] for i in idx)
    maradek = [(el.tart[i][0] - l1[j], el.tart[i][1] - l2[j]) for j, i in enumerate(idx)]
    kint = frozenset().union(*[a | b for a, b in maradek])
    for akc in (("X", 11), ("Y", 6)):
        hivo, c = akc
        nbx, nby = next((x, y) for h, cc, x, y in el._hivasok(allapot, kint) if (h, cc) == akc)
        _, siker = el._utes(allapot, nbx, nby, idx, l1, l2, k, m, hivo, c, maradek, ("x", hivo, c))
        # a szingli kis lap Nyugatnál (Kelet ♦Á10xx): a három x-tartás egyformán jár
        x_szingli = [i for i in idx if len(el.tart[i][0]) == 1 and max(el.tart[i][0]) < 10]
        assert len({i in siker for i in x_szingli}) == 1, akc
