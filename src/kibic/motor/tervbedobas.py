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


def _vedo_hivja(X: tuple, Y: tuple, W: tuple, E: tuple, hivo: str, memo: dict) -> int:
    """A legkevesebb ütés, amit a színben viszünk, ha a `hivo` védő hív, és amíg a védők
    ütnek, ők hívnak tovább (a bedobott védőnek nincs más szabad lapja). A mi lapjaink:
    második kézben a legkisebb, negyedikben a legolcsóbb, amely üt (ha a partnerünk nem
    üt), különben a legkisebb. Ha mi ütünk, a maradékból a biztos ütések jönnek."""
    kulcs = (X, Y, W, E, hivo)
    if kulcs in memo:
        return memo[kulcs]
    H, P = (W, E) if hivo == "W" else (E, W)
    if not H:
        # a hívó védőnek nincs több lapja a színben: más színt kell hívnia — az
        # eliminált színben dob-lop, ez is a mi ütésünk (a bedobás feltételei szerint)
        ki = 99
        memo[kulcs] = ki
        return ki
    # a védő hívására: W hív → az asztal (Y) a második, E hív → a felvevő (X)
    K2, K4 = (Y, X) if hivo == "W" else (X, Y)
    legjobb = None
    for l1 in set(H):
        for l3 in (set(P) or {0}):
            k2 = K2[0] if K2 else 0
            leg = max(l1, l3)
            if k2 > leg:
                k4 = K4[0] if K4 else 0
            else:
                nagy = [r for r in K4 if r > leg]
                k4 = nagy[0] if nagy else (K4[0] if K4 else 0)
            mi = max(k2, k4)
            X2, Y2 = list(K2), list(K4)
            if k2:
                X2.remove(k2)
            if k4:
                Y2.remove(k4)
            if hivo == "E":
                X2, Y2 = X2, Y2                      # K2 = X, K4 = Y
            else:
                X2, Y2 = Y2, X2                      # K2 = Y, K4 = X
            H2 = tuple(r for r in H if r != l1)
            P2 = tuple(r for r in P if r != l3)
            W2, E2 = (H2, P2) if hivo == "W" else (P2, H2)
            if mi > leg:
                ert = 1 + _biztos(X2, Y2, list(H2) + list(P2))
            else:
                # a védők ütöttek: az ütő védő hív tovább
                uj = hivo if l1 > l3 else ("E" if hivo == "W" else "W")
                ert = _vedo_hivja(tuple(X2), tuple(Y2), W2, E2, uj, memo)
            if legjobb is None or ert < legjobb:
                legjobb = ert
    memo[kulcs] = legjobb
    return legjobb


def vedo_hivas_nyer(a, sz: str, max_kint: int = 9) -> bool:
    """Kényszerszín: ha a védő hívja meg a színt (és amíg ő üt, ő hív tovább), egy
    ütéssel többet viszünk, mint a biztos ütéseink — akárhogy oszlik el, és akármit
    hívnak és tesznek a védők. Impasszba hívás (kétirányú villa), fagyott szín (a két
    védtelen figura a két kezünkben: aki meghívja, veszít egy ütést)."""
    X = tuple(sorted(l.rang for l in _szin(a, a.felvevo, sz)))
    Y = tuple(sorted(l.rang for l in _szin(a, a.asztal, sz)))
    kint = [l.rang for l in a.kint_szin(sz)]
    if not X or not Y or not kint or len(kint) > max_kint:
        return False
    alap = _biztos(list(X), list(Y), kint)
    if alap >= max(len(X), len(Y)):
        return False                       # nincs vesztőnk a színben
    memo: dict = {}
    for oszt in product((0, 1), repeat=len(kint)):
        W = tuple(sorted(r for r, o in zip(kint, oszt) if o == 0))
        E = tuple(sorted(r for r, o in zip(kint, oszt) if o == 1))
        for hivo, H in (("W", W), ("E", E)):
            if H and _vedo_hivja(X, Y, W, E, hivo, memo) < alap + 1:
                return False
    return True


def lopva_eliminalhato(a, sz: str) -> bool:
    """A színt lopással tüntetjük el (a szerkesztő, 2026-11-21, BM A-6 #2): az egyik
    kezünk a színben legfeljebb annyi lapot tart, ahány nyerőnk van (ezekre követ, aztán
    üres), és van adója; a másik kéz maradékát ez a kéz lopja. A lopásokat egy másik
    egység végzi (pl. az asztalfordítás) — a bedobás ezt a tervben megköveteli."""
    if not a.adu or sz == a.adu:
        return False
    k1, k2 = a.kezek
    kint = a.kint_szin(sz)
    nyero = [l for k in a.kezek for l in _szin(a, k, sz) if not kint or l.rang > kint[0].rang]
    for R, M in ((k1, k2), (k2, k1)):
        r, m = len(_szin(a, R, sz)), len(_szin(a, M, sz))
        if r < m and r <= len(nyero) and a.szin(R, a.adu):
            return True
    return False


def lopva_eliminalando(a, sz: str) -> list[str]:
    return [s for s in SZINEK if s not in (a.adu, sz) and not ures_mindket(a, s)
            and not eliminalhato(a, s) and lopva_eliminalhato(a, s)]


def kenyszer_szinek(a, sz: str) -> list[str]:
    """A bedobás után a védőnek maradó mellékszínek (sem eliminálható — tükörben vagy
    lopással —, sem üres a két kezünkben); mindegyikben a védő hívása nekünk ütést ad —
    különben üres lista."""
    ki = []
    for s in SZINEK:
        if s in (a.adu, sz) or ures_mindket(a, s) or eliminalhato(a, s) or lopva_eliminalhato(a, s):
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
    """A bedobó szín: a nyerőink lehívása után a rövidebb kezünk vesztőinek száma (ennyi
    kiadás után a rövidebb kéz üres). Ha a hosszabb kézben marad lap, azt a rövidebb kéz
    lopja, ha a védő meghívja (BM A-6 #2: ♦432 / ♦65 — két kiadás, a harmadik lopható)."""
    if not a.adu:
        return 0
    if sz == a.adu:
        # az aduszín a bedobó szín (BM A-6 #3: ♠AJxx / ♠KTxx, hiányzik a D): a felső
        # aduk lehívása után egyetlen kint lévő adu áll a mieink fölött — az az egy kiadás
        kint = [l.rang for l in a.kint_szin(sz)]
        mi = sorted((l.rang for l in a.mi_szin(sz)), reverse=True)
        if not kint or not mi:
            return 0
        f = max(kint)
        felso = [r for r in mi if r > f]
        alatta = [r for r in mi if r < f]
        tobbi = sorted(kint, reverse=True)[1:]
        if felso and alatta and (not tobbi or alatta[0] > tobbi[0]):
            return 1
        return 0
    k1, k2 = a.kezek
    n1, n2 = len(_szin(a, k1, sz)), len(_szin(a, k2, sz))
    if min(n1, n2) == 0:
        return 0
    kint = a.kint_szin(sz)
    nyero = [l for k in a.kezek for l in _szin(a, k, sz) if not kint or l.rang > kint[0].rang]
    return max(0, min(n1, n2) - len(nyero))


def adu_marad(a) -> bool:
    """A kiaduzás után legalább az egyik kezünkben marad adu (a dob-lophoz: az egyik
    kéz lop, a másik dob)."""
    if not a.adu:
        return False
    kint = len(a.kint_szin(a.adu))
    return max(len(a.szin(k, a.adu)) for k in a.kezek) > kint
