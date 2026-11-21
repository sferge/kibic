"""
Elimináció és bedobás (kényszerhívás) — a szerkesztő, 2026-11-21 (minta: BM A-6 #1).

Adus felvételben egy mellékszínt „eltüntetünk” mindkét kezünkből (elimináció). Ha
utána szándékosan kiadunk egy ütést, a védő kénytelen „rosszat” hívni:
  * az eliminált színt — dob-lop: az egyik kéz lop, a másik vesztőt dob;
  * vagy egy olyan színt, amelyben a hívása nekünk ütést ad (impasszba, fagyott szín).

Ez a modul a látott lapokból számolja a fogalmakat; a séma (`technikak.yaml`,
BEDOBAS) ezekből építi a köröket.
"""
from __future__ import annotations

from itertools import product

from ..domain import SZINEK


def _szin(a, k: str, sz: str) -> list:
    """A kéz lapjai a színben a folyó ütés után: ha a kéznek még követnie kell a hívott
    színt, abból a legkisebb lapja lemegy (a nyerőket ez nem érinti)."""
    lapok = a.szin(k, sz)
    if lapok and a.kovetes.get(k) == sz:
        lapok = lapok[:-1]
    return lapok


def eliminalhato(a, sz: str) -> bool:
    """A színt a saját lehívásainkkal mindkét kezünkből eltüntethetjük: tükörszín —
    a két kézben egyforma hosszú, és a nyerőink legalább annyian vannak (v1)."""
    if not a.adu or sz == a.adu:
        return False
    k1, k2 = a.kezek
    n1, n2 = len(_szin(a, k1, sz)), len(_szin(a, k2, sz))
    if n1 != n2 or n1 == 0:
        return False
    kint = a.kint_szin(sz)
    nyero = [l for k in a.kezek for l in _szin(a, k, sz) if not kint or l.rang > kint[0].rang]
    return len(nyero) >= n1


def ures_mindket(a, sz: str) -> bool:
    return all(not _szin(a, k, sz) for k in a.kezek)


def _biztos(X: list[int], Y: list[int], kint: list[int]) -> int:
    """Biztos ütések a maradék lapokkal (felülről): a kint lévőknél nagyobb lapjaink,
    legfeljebb a hosszabb kéz hossza."""
    f = max(kint) if kint else 0
    felso = [r for r in X + Y if r > f]
    return min(len(felso), max(len(X), len(Y)))


def vedo_hivas_nyer(a, sz: str, max_kint: int = 9) -> bool:
    """Ha a védő hívja meg a színt, egy ütéssel többet viszünk, mint a biztos
    ütéseink — akárhogy oszlik el, és akármit hív és tesz a védő. A mi lapjaink:
    második kézben a legkisebb, negyedik kézben a legolcsóbb, amely üt (ha a
    partnerünk nem üt), különben a legkisebb (impasszba hívás, fagyott szín)."""
    X = sorted(l.rang for l in a.szin(a.felvevo, sz))
    Y = sorted(l.rang for l in a.szin(a.asztal, sz))
    kint = [l.rang for l in a.kint_szin(sz)]
    if not X or not Y or not kint or len(kint) > max_kint:
        return False
    alap = a.biztos_utesek(sz)
    if alap >= max(len(X), len(Y)):
        return False                       # nincs vesztőnk a színben
    for oszt in product((0, 1), repeat=len(kint)):
        W = [r for r, o in zip(kint, oszt) if o == 0]
        E = [r for r, o in zip(kint, oszt) if o == 1]
        # a védők a mi két kezünk között ülnek: a felvevő után a bal védő (W)
        for hivo, H, P in (("W", W, E), ("E", E, W)):
            if not H:
                continue
            # a hívó után a második kéz: W hív → az asztal (Y) jön, E hív → a felvevő (X)
            K2, K4 = (Y, X) if hivo == "W" else (X, Y)
            for l1 in set(H):
                k2 = K2[0]                                   # második kéz: kicsi
                for l3 in (set(P) or {0}):
                    leg = max(l1, l3)
                    mi = k2 if k2 > leg else None
                    if mi is not None:
                        k4 = K4[0]
                    else:
                        nagy = [r for r in K4 if r > leg]
                        k4 = nagy[0] if nagy else K4[0]
                    nyert = max(k2, k4) > leg
                    X2, Y2 = list(K2), list(K4)
                    X2.remove(k2)
                    Y2.remove(k4)
                    H2 = [r for r in H if r != l1]
                    P2 = [r for r in P if r != l3]
                    if int(nyert) + _biztos(X2, Y2, H2 + P2) < alap + 1:
                        return False
    return True


def kenyszer_szinek(a, sz: str) -> list[str]:
    """A bedobás után a védőnek maradó mellékszínek (sem eliminálható, sem üres a két
    kezünkben); mindegyikben a védő hívása nekünk ütést ad — különben üres lista."""
    ki = []
    for s in SZINEK:
        if s in (a.adu, sz) or ures_mindket(a, s) or eliminalhato(a, s):
            continue
        if not vedo_hivas_nyer(a, s):
            return []
        ki.append(s)
    return ki


def eliminalo_lapok(a, sz: str) -> list:
    """A lehívandó nyerők: minden más eliminálható mellékszínből annyi, ahány lap a
    színből egy kezünkben van (a rövidebb kézé előbb, felülről)."""
    ki = []
    for s in SZINEK:
        if s in (a.adu, sz) or not eliminalhato(a, s):
            continue
        # a lehívandó lapok a mostani lapokból (a folyó ütés lapja, ha nyerő, kimarad a
        # végrehajtásból: már nincs a kézben)
        n = max(len(a.szin(k, s)) for k in a.kezek)
        kint = a.kint_szin(s)
        nyero = [l for l in a.mi_szin(s) if not kint or l.rang > kint[0].rang][:n]
        ki += sorted(nyero, key=lambda l: -l.rang)
    return ki


def bedobo_kiad(a, sz: str) -> int:
    """A bedobó szín: mindkét kézben egyforma hosszú; a nyerőink lehívása után ennyi
    vesztő marad kezenként (ennyi kiadás után a szín mindkét kezünkből elfogy)."""
    if not a.adu or sz == a.adu:
        return 0
    k1, k2 = a.kezek
    n1, n2 = len(a.szin(k1, sz)), len(a.szin(k2, sz))
    if n1 != n2 or n1 == 0:
        return 0
    kint = a.kint_szin(sz)
    nyero = [l for l in a.mi_szin(sz) if not kint or l.rang > kint[0].rang]
    return n1 - min(len(nyero), n1)


def adu_marad(a) -> bool:
    """A kiaduzás után mindkét kezünkben marad adu (a dob-lophoz)."""
    if not a.adu:
        return False
    kint = len(a.kint_szin(a.adu))
    return min(len(a.szin(k, a.adu)) for k in a.kezek) > kint
