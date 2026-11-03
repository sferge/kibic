"""
Játékmódok gyors esélye (2026-11-03, Felvevő tervjáték): a speciális módok
(jatekmodok.yaml) sikerfeltételeinek valószínűsége, lejátszás nélkül.

A modell (ugyanaz minden módhoz, hogy az esélyek összevethetők legyenek):
  - színenként a védők lapjainak minden elosztása (súllyal); a színek függetlenek;
  - elosztásonként a szín három száma:
      T  a mi ütéseink a színben (a választott kezeléssel),
      L  a védők ütései a színben (vesztés),
      X  a dobásra jó többletnyerők (színjátékban: a másik kéz hosszabb nyerőire a
         mester kéz vesztőt dob);
  - a kezelés: a színtáblázat kimenetei (a látott lapokon döntő felvevő,
    tervszintabla.kimenet_tabla), ha vannak; különben a mindent látó játék;
  - a vesztés: a mi kezelésünk vesztései és a védők hívásával elvihető ütések
    (mindent látó játék a védők szemszögéből) közül a több; színjátékban legfeljebb
    annyi, ahány lapja a mester kéznek van a színben (utána lop);
  - SIKER: ΣT >= cél és ΣL - ΣX <= tartalék (13 - cél).

Az ALAP: a mester kéz a hosszabb adus kéz, lopás nincs (kiaduzás), mellékszínben
legfeljebb 1 vesztéses kezelés, aduban bármilyen. Egy mód NYERESÉGE: a mód esélye
mínusz az ALAP esélye; a rangsor a nyereség szerint megy.

Módonként (a séma „siker” mezőjének számolható alakja):
  KIMAGASITAS     egy hosszú mellékszínben a korlátlan vesztésű (kimagasító) kezelés,
                  színjátékban a rövid adus kéz lopásaival is (mindent látó játék)
  LOPAS_ROVID     a rövid adus kéz lopja a mester kéz vesztőit (legfeljebb az adui
                  számáig); felüllopás, ha a mögötte ülő védő már színhiányos
  ASZTALFORDITAS  a mester kéz a rövid adus kéz; a hosszú adus kéz lop; ha a védők
                  hosszabb adu-fele hosszabb a rövid adunál, a különbség vesztés
  KERESZTLOPAS    mindkét kéz lop (a színben rövidebb kéz), kiaduzás nélkül
  VEGJATEK        egy színben a védő kénytelen indítani (mi választjuk, melyikük):
                  a vesztés a védők így elvihető ütése; × BEDOBAS
  BESZORITAS      egy vesztés a sok, és ugyanaz a védő egyedül őriz két színt; × BESZORITAS_F
A VESZTOCSERE és az ADUPUCCS még nincs (0).
"""
from __future__ import annotations

from itertools import combinations, product
from math import comb

from . import tervszinkezeles as ts

MODOK = ("KIMAGASITAS", "LOPAS_ROVID", "ASZTALFORDITAS", "KERESZTLOPAS", "VEGJATEK", "BESZORITAS")
MAX_KINT = 9             # ennél több kint lévő lap (legfeljebb 3 lapunk): hosszak szerint, felső ütésekkel
FELULLOPAS = 0.4         # felüllopás esélye, ha a lopó mögött ülő védő már színhiányos (és a lopó adu kicsi)
BEDOBAS = 0.7            # a bedobás kivitelezhetősége színjátékban (elimináció, a jó védő kerül hívásba)
BEDOBAS_SZAN = 0.35      # szanban (nincs elimináció)
BESZORITAS_F = 0.8       # az egyszerű beszorítás kivitelezhetősége (átmenetek, ütésszám-igazítás)
MAX_LOPAS = 3            # a lopásos kimagasításhoz legfeljebb ennyi lopás
_KOMBINACIO = 400        # az alapkezelés választásánál eddig minden kombinációt megnéz


def _felso(X, Y, kint) -> int:
    n = 0
    for r in range(14, 1, -1):
        if r in kint:
            break
        if r in X or r in Y:
            n += 1
    return min(n, max(len(X), len(Y)))


def _vedok(X, Y, V1, V2, ki=None) -> int:
    """A védők ütései a színben (mindent látva); `ki`: a kezdő védő (V1/V2), None: szabad.
    A védők szemszögéből az ülésrend V1, Y, V2, X — ők az X', Y' = V1, V2."""
    if not V1 and not V2:
        return 0
    if ki is None:
        return ts.dd(V1, V2, Y, X, 0, 0)
    if not (V1 if ki == "V1" else V2):
        return 99
    return ts._dd_rek(V1, V2, Y, X, 0, 0, ts.SORREND["X" if ki == "V1" else "Y"], ())


def _or(X, Y, V, W, T, ki) -> bool:
    """`ki` védő (lapjai V) egyedül őrzi-e a színt: bármely lapját dobja, több ütésünk lesz."""
    if not V:
        return False
    for c in V:
        V_ = V - {c}
        t = ts.dd(X, Y, V_, W, 0, 0) if ki == "V1" else ts.dd(X, Y, W, V_, 0, 0)
        if t <= T:
            return False
    return True


class Szin:
    """Egy szín elosztásai és a módokhoz kellő értékek (lustán)."""

    def __init__(self, X: frozenset, Y: frozenset, adu: bool = False, kimenet: bool = True):
        self.X, self.Y, self.adu = X, Y, adu
        self.kint = frozenset(r for r in range(2, 15) if r not in X and r not in Y)
        n = len(self.kint)
        self.n = n
        # durva: túl sok kint lévő lap (vagy egy sincs) — csak a hosszak számítanak
        self.durva = n > MAX_KINT or n == 0 or (not X and not Y)
        self.sorok = []                       # (súly, V1, V2); durván V1/V2 csak a hosszt hordozza
        kint = sorted(self.kint)
        W = 0
        for k in range(n + 1):
            w = comb(26 - n, 13 - k) if 0 <= 13 - k <= 26 - n else 0
            if not w:
                continue
            if self.durva:
                w *= comb(n, k)
                self.sorok.append((w, frozenset(kint[:k]), frozenset(kint[k:])))
                W += w
                continue
            for v1 in combinations(kint, k):
                v1 = frozenset(v1)
                self.sorok.append((w, v1, self.kint - v1))
                W += w
        self.sorok = [(w / W, a, b) for w, a, b in self.sorok]
        self._T = self._F = self._Fv = self._or = None
        self.kim = self._kimenetek() if kimenet and not self.durva else {}
        self.valasztott: list | None = None    # az alapkezelés (ütés, saját vesztés) elosztásonként

    # --- a kezelések ---
    def _kimenetek(self) -> dict:
        """A színtáblázat kimenetei a mi elosztás-sorrendünkben: {(k, m): [(ütés, vesztés)]}."""
        from . import tervszintabla as tsz
        k = tsz.kulcs(self.X, self.Y)
        km = tsz.kimenet_tabla().get(k)
        if not km:
            return {}
        Xt = frozenset(14 - i for i, c in enumerate(k) if c == "x")
        csere = Xt != self.X                 # a táblázat x keze a mi Y-unk: a védők is cserélődnek
        Yt = self.X if csere else self.Y
        from .tervszinkezeles import Feladat
        hely = {v1: i for i, (v1, _, _) in enumerate(Feladat(Xt, Yt, self.kint).tartasok())}
        idx = [hely[b if csere else a] for _, a, b in self.sorok]
        return {kk: [v[i] for i in idx] for kk, v in km.items()}

    def T(self) -> list[int]:
        """A mindent látó felvevő ütései (lopás nélkül)."""
        if self._T is None:
            if self.durva:
                self._T = [_felso(self.X, self.Y, self.kint)] * len(self.sorok)
            else:
                self._T = [ts.dd(self.X, self.Y, a, b, 0, 0) for _, a, b in self.sorok]
        return self._T

    def dd_kezeles(self, m: int, rx: int = 0, ry: int = 0) -> list[tuple[int, int]]:
        """Mindent látó kezelés: a legtöbb ütés legfeljebb m vesztéssel → (ütés, vesztés)."""
        ki = []
        for (_, a, b), t in zip(self.sorok, self.T()):
            if self.durva:
                ki.append((t, 0))
                continue
            if rx or ry:
                t = ts.dd(self.X, self.Y, a, b, rx, ry)
            jo = (0, 0)
            for k in range(t, 0, -1):
                v = next((mm for mm in range(0, min(m, 13) + 1)
                          if ts.dd_cel(self.X, self.Y, a, b, rx, ry, k, mm)), None)
                if v is not None:
                    jo = (k, v)
                    break
            ki.append(jo)
        return ki

    def kezelesek(self, m: int) -> list[list[tuple[int, int]]]:
        """Az alapkezelés jelöltjei (elosztásonként (ütés, saját vesztés)): a táblázat
        kimenetei legfeljebb m vesztéssel, ha vannak; különben a mindent látó."""
        if self.kim:
            ki, latott = [], set()
            for (kk, mm), v in sorted(self.kim.items()):
                if mm == m and tuple(v) not in latott:
                    latott.add(tuple(v))
                    ki.append(list(v))
            if ki:
                return ki
        return [self.dd_kezeles(m)]

    # --- a védők ---
    def F(self) -> list[int]:
        """A védők ütései (szabad kezdéssel), elosztásonként."""
        if self._F is None:
            if self.durva:
                self._F = [max(0, max(len(a), len(b)) - t) for (_, a, b), t in zip(self.sorok, self.T())]
            else:
                self._F = [_vedok(self.X, self.Y, a, b) for _, a, b in self.sorok]
        return self._F

    def F_bedobas(self) -> list[int]:
        """A védők ütései, ha MI választjuk, melyikük indítja a színt."""
        if self._Fv is None:
            if self.durva:
                self._Fv = list(self.F())
            else:
                self._Fv = [min(_vedok(self.X, self.Y, a, b, "V1"), _vedok(self.X, self.Y, a, b, "V2"))
                            for _, a, b in self.sorok]
        return self._Fv

    def orok(self) -> list[tuple[bool, bool]]:
        if self._or is None:
            if self.durva:
                self._or = [(False, False)] * len(self.sorok)
            else:
                self._or = [(_or(self.X, self.Y, a, b, t, "V1"), _or(self.X, self.Y, b, a, t, "V2"))
                            for (_, a, b), t in zip(self.sorok, self.T())]
        return self._or

    def hossz(self, ki: str, i: int) -> int:
        _, a, b = self.sorok[i]
        return len(a) if ki == "V1" else len(b)


# --- a szín számai egy kezeléssel -------------------------------------------------------------

def harmasok(sz: Szin, kez: list, mester: str | None, szan: bool = False) -> list[tuple[int, int, int]]:
    """(T, L, X) elosztásonként.
    Szanban: L = a saját kezelésünk vesztései, X = amennyivel a védők többet vihetnek
    a színben, ha ők hívják (ezt akkor viszik el, ha hívásba kerülnek).
    Színjátékban (a nyerőink a színben előbb jönnek, a vesztők utánuk): a teljes
    vesztés legfeljebb a mi leghosszabb kezünk köreiig tart (utána lopunk); `mester`
    ("X"/"Y") esetén csak a mester kéz köreiben (utána a mester kéz lop), és
    X = a másik kéz többletnyerői, amelyekre a mester kéz vesztőt dob."""
    lx, ly = len(sz.X), len(sz.Y)
    ki = []
    for (u, v), f in zip(kez, sz.F()):
        if szan:
            ki.append((u, v, max(0, f - v)))
            continue
        L = min(max(v, f), max(0, max(lx, ly) - u))
        Xd = 0
        if mester is not None:
            lm, lo = (lx, ly) if mester == "X" else (ly, lx)
            L = min(L, max(0, lm - min(u, lm)))
            if lo > lm:
                Xd = max(0, u - lm)
        ki.append((u, L, Xd))
    return ki


def _eloszlas(sz: Szin, h: list) -> dict:
    d: dict = {}
    for (w, _, _), x in zip(sz.sorok, h):
        d[x] = d.get(x, 0.0) + w
    return d


def _osszead(a: dict, b: dict, cel: int, tart: int, szan: bool = False) -> dict:
    """Két (T, L, X) eloszlás összege (vágva: T a célig, L és X ahol már nem számít);
    szanban az X a színek legnagyobbja (a védők egy színt futtatnak), különben összeg."""
    uj: dict = {}
    for (t1, l1, x1), p1 in a.items():
        for (t2, l2, x2), p2 in b.items():
            k = (min(cel, t1 + t2), min(tart + 9, l1 + l2), max(x1, x2) if szan else min(8, x1 + x2))
            uj[k] = uj.get(k, 0.0) + p1 * p2
    return uj


def _osszes(eloszlasok: list[dict], cel: int, tart: int, szan: bool = False) -> dict:
    ossz = {(0, 0, 0): 1.0}
    for e in eloszlasok:
        ossz = _osszead(ossz, e, cel, tart, szan)
    return ossz


def _siker(t, l, x, cel, tart, szan=False) -> bool:
    """Szanban: ha egyszer is kiadjuk a hívást, a védők a legjobb színüket is futtatják."""
    if szan:
        return t >= cel and l + (x if l > 0 else 0) <= tart
    return t >= cel and l - x <= tart


def _p(ossz: dict, cel: int, tart: int, szan: bool = False) -> float:
    return sum(p for (t, l, x), p in ossz.items() if _siker(t, l, x, cel, tart, szan))


def _binom(n: int, q: float) -> dict:
    return {k: comb(n, k) * q ** k * (1 - q) ** (n - k) for k in range(n + 1)}


# --- az alap --------------------------------------------------------------------------------

def alap(szinek: dict, adu: str | None, mester: str | None, cel: int) -> tuple[dict, float]:
    """Színenként a legjobb kezelés (együtt a legnagyobb eséllyel) → ({szín: hármasok}, esély).
    Kevés kombinációnál mindet nézi, különben színenként javít, amíg tud."""
    tart = 13 - cel
    jel = {}
    for s, sz in szinek.items():
        jel[s] = [(k, harmasok(sz, k, None if s == adu else mester, adu is None))
                  for k in sz.kezelesek(99 if s == adu else 1)]
    el = {s: [_eloszlas(szinek[s], h) for _, h in jel[s]] for s in szinek}
    S = list(szinek)
    db = 1
    for s in S:
        db *= len(jel[s])

    szan = adu is None

    def ertek(vv):
        return _p(_osszes([el[s][i] for s, i in zip(S, vv)], cel, tart, szan), cel, tart, szan)

    if db <= _KOMBINACIO:
        legjobb, valaszt = -1.0, None
        for vv in product(*(range(len(jel[s])) for s in S)):
            p = ertek(vv)
            if p > legjobb + 1e-12:
                legjobb, valaszt = p, vv
    else:
        valaszt = [max(range(len(jel[s])), key=lambda i: sum(h[0] * p for h, p in el[s][i].items())) for s in S]
        legjobb = ertek(valaszt)
        javult = True
        while javult:
            javult = False
            for j, s in enumerate(S):
                for i in range(len(jel[s])):
                    vv = list(valaszt)
                    vv[j] = i
                    p = ertek(vv)
                    if p > legjobb + 1e-12:
                        legjobb, valaszt, javult = p, vv, True
    for s, i in zip(S, valaszt):
        szinek[s].valasztott = jel[s][i][0]
    return {s: jel[s][i][1] for s, i in zip(S, valaszt)}, legjobb


# --- lopások ---------------------------------------------------------------------------------

def _lopas(sz: Szin, h: list, lopo: str, magas: bool, lm: int) -> list[dict]:
    """Elosztásonként {(T, L, X, lopás): p}: a `lopo` kéz (X/Y; a színben rövidebb)
    lopja a vesztéseket a saját lapjai elfogyta után. A körök: előbb a nyerőink (a
    vesztést számoló kéz `lm` körén belül), utána a vesztők. Felüllopás: ha a lopó
    mögött ülő védő (X mögött V1, Y mögött V2) a lopás körében már színhiányos, és a
    lopó adu nem magasabb minden kint lévő adunál."""
    hl = len(sz.X) if lopo == "X" else len(sz.Y)
    mog = "V1" if lopo == "X" else "V2"
    ki = []
    for i, (t, l, x) in enumerate(h):
        kezd = min(t, lm)
        tol = max(hl, kezd)
        r = max(0, kezd + l - tol)
        if not r:
            ki.append({(t, l, x, 0): 1.0})
            continue
        if magas:
            ki.append({(t + r, l - r, x, r): 1.0})
            continue
        vh = sz.hossz(mog, i)
        biztos = sum(1 for k in range(tol + 1, tol + r + 1) if k <= vh)
        d = {}
        for k, p in _binom(r - biztos, 1 - FELULLOPAS).items():
            j = biztos + k
            d[(t + j, l - j, x, r)] = p        # a lopás akkor is elfogy, ha felüllopták
        ki.append(d)
    return ki


def _dp_lopas(tagok: list, kap: tuple, cel: int, tart: int) -> dict:
    """tagok: (szín, elosztásonként {(T, L, X, r1, ...): p}); kap: lopó kezenként a
    kapacitás (adu). A kapacitáson túli lopás vesztés marad. → {(T, L, X): p}."""
    nk = len(kap)
    allapot = {(0, 0, 0) + (0,) * nk: 1.0}
    for sz, lo in tagok:
        e: dict = {}
        for (w, _, _), d in zip(sz.sorok, lo):
            for k, p in d.items():
                e[k] = e.get(k, 0.0) + w * p
        uj: dict = {}
        for k0, p0 in allapot.items():
            for k2, p2 in e.items():
                k = (min(cel + 9, k0[0] + k2[0]), min(tart + 9, k0[1] + k2[1]), min(8, k0[2] + k2[2])) + \
                    tuple(min(9, k0[3 + j] + k2[3 + j]) for j in range(nk))
                uj[k] = uj.get(k, 0.0) + p0 * p2
        allapot = uj
    ki: dict = {}
    for k, p in allapot.items():
        tobb = sum(max(0, k[3 + j] - kap[j]) for j in range(nk))
        kk = (min(cel, k[0] - tobb), k[1] + tobb, k[2])
        ki[kk] = ki.get(kk, 0.0) + p
    return ki


def _nincs_lopas(h: list, nk: int = 1) -> list[dict]:
    return [{(t, l, x) + (0,) * nk: 1.0} for t, l, x in h]


# --- a módok --------------------------------------------------------------------------------

def mod_eselyek(D: dict, U: dict, adu: str | None, cel: int, kimenet: bool = True) -> dict:
    """D, U: {szín: rangok halmaza} (felvevő, asztal). → {"ALAP": P, mód: (P, nyereség)}."""
    szinek = {s: Szin(frozenset(D.get(s, ())), frozenset(U.get(s, ())), s == adu, kimenet) for s in "SHDC"}
    tart = 13 - cel
    oldal = [s for s in "SHDC" if s != adu]
    tD = len(D.get(adu, ())) if adu else 0
    tU = len(U.get(adu, ())) if adu else 0
    mester = None if not adu else ("X" if tD >= tU else "Y")
    alap_h, p_alap = alap(szinek, adu, mester, cel)
    alap_el = {s: _eloszlas(szinek[s], h) for s, h in alap_h.items()}
    szan = adu is None
    ki: dict = {"ALAP": p_alap}

    def ered(p):
        return (max(p, p_alap), max(0.0, p - p_alap))

    def tobbi(s):
        return _osszes([alap_el[t] for t in "SHDC" if t != s], cel, tart, szan)

    # --- KIMAGASITAS: egy hosszú mellékszín (7+ együtt, egyik kéz hosszabb) ---
    legjobb = 0.0
    for s in oldal:
        sz = szinek[s]
        lx, ly = len(sz.X), len(sz.Y)
        if lx + ly < 7 or lx == ly:
            continue
        kez = sz.kezelesek(99)
        if adu:
            rx = min(MAX_LOPAS, tD) if lx < ly and tD <= tU else 0
            ry = min(MAX_LOPAS, tU) if ly < lx and tU <= tD else 0
            if rx or ry:
                kez = kez + [sz.dd_kezeles(99, rx, ry)]
        masik = tobbi(s)
        for k in kez:
            p = _p(_osszead(masik, _eloszlas(sz, harmasok(sz, k, mester, szan)), cel, tart, szan), cel, tart, szan)
            legjobb = max(legjobb, p)
    ki["KIMAGASITAS"] = ered(legjobb)

    if adu:
        top_kint = max(szinek[adu].kint, default=0)

        def magas(lopo):
            lapok = D.get(adu, ()) if lopo == "X" else U.get(adu, ())
            return bool(lapok) and min(lapok) > top_kint

        aduszin = szinek[adu]
        adu_h = alap_h[adu]

        def oldal_tagok(lopo, m_):
            """A mellékszínek a `m_` mester kézzel; a `lopo` kéz lop, ahol rövidebb."""
            tagok = []
            for s in oldal:
                sz = szinek[s]
                h = harmasok(sz, sz.valasztott, m_)
                hl, hm = (len(sz.X), len(sz.Y)) if lopo == "X" else (len(sz.Y), len(sz.X))
                lm = len(sz.X) if m_ == "X" else len(sz.Y)
                tagok.append((sz, _lopas(sz, h, lopo, magas(lopo), lm) if hl < hm else _nincs_lopas(h)))
            return tagok

        # --- LOPAS_ROVID: a mester kéz a hosszú adus; a rövid adus kéz lop ---
        p_lop = 0.0
        for lopo, t_lopo, t_mas in (("X", tD, tU), ("Y", tU, tD)):
            if t_lopo == 0 or t_lopo > t_mas:
                continue
            tagok = oldal_tagok(lopo, "Y" if lopo == "X" else "X")
            tagok.append((aduszin, _nincs_lopas(adu_h)))
            p_lop = max(p_lop, _p(_dp_lopas(tagok, (t_lopo,), cel, tart), cel, tart))
        ki["LOPAS_ROVID"] = ered(p_lop)

        # --- ASZTALFORDITAS: a mester kéz a rövid adus; a hosszú adus kéz lop ---
        p_af = 0.0
        if tD != tU and min(tD, tU) >= 2:
            lopo, tL, tS = ("X", tD, tU) if tD > tU else ("Y", tU, tD)
            tagok = oldal_tagok(lopo, "Y" if lopo == "X" else "X")
            # az adu ütései a rövid adu hosszáig (a hosszú adus kéz lopásai a mellékszínekben
            # jönnek vissza); ha a védők hosszabb fele hosszabb a rövid adunál, a különbség vesztés
            adu_t = []
            for (w, a, b), (t, l, x) in zip(aduszin.sorok, adu_h):
                dmax = max(len(a), len(b))
                adu_t.append({(max(0, t - (tL - tS)), l + max(0, dmax - tS), 0, 0): 1.0})
            tagok.append((aduszin, adu_t))
            p_af = _p(_dp_lopas(tagok, (tL,), cel, tart), cel, tart)
        ki["ASZTALFORDITAS"] = ered(p_af)

        # --- KERESZTLOPAS: mindkét kéz lop, kiaduzás nélkül ---
        p_kl = 0.0
        if tD >= 2 and tU >= 2:
            tagok = []
            for s in oldal:
                sz = szinek[s]
                h = harmasok(sz, sz.valasztott, None)
                lx, ly = len(sz.X), len(sz.Y)
                lopo = "X" if lx < ly else "Y" if ly < lx else None
                if lopo is None:
                    tagok.append((sz, _nincs_lopas(h, 2)))
                    continue
                tagok.append((sz, [{(k[0], k[1], k[2]) + ((k[3], 0) if lopo == "X" else (0, k[3])): p
                                    for k, p in d.items()} for d in _lopas(sz, h, lopo, magas(lopo), max(lx, ly))]))
            # az adu: nincs kiaduzás; az aduk a lopásokban visznek ütést
            tagok.append((aduszin, [{(0, 0, 0, 0, 0): 1.0}] * len(aduszin.sorok)))
            p_kl = _p(_dp_lopas(tagok, (tD, tU), cel, tart), cel, tart)
        ki["KERESZTLOPAS"] = ered(p_kl)
    else:
        for m in ("LOPAS_ROVID", "ASZTALFORDITAS", "KERESZTLOPAS"):
            ki[m] = (p_alap, 0.0)

    # --- VEGJATEK: egy színben a védő kénytelen indítani ---
    f = BEDOBAS if adu and tD >= 1 and tU >= 1 else BEDOBAS_SZAN if not adu else 0.0
    legjobb = p_alap
    if f:
        for s in oldal:
            sz = szinek[s]
            if sz.durva:
                continue
            h = [(t + max(0, l - fv), min(l, fv), x) for (t, l, x), fv in zip(alap_h[s], sz.F_bedobas())]
            legjobb = max(legjobb, _p(_osszead(tobbi(s), _eloszlas(sz, h), cel, tart, szan), cel, tart, szan))
    ny = max(0.0, f * (legjobb - p_alap))
    ki["VEGJATEK"] = (p_alap + ny, ny)

    # --- BESZORITAS: egy vesztés a sok, és ugyanaz a védő egyedül őriz két színt ---
    allapot = {(0, 0, 0, 0, 0): 1.0}
    for s in "SHDC":
        sz = szinek[s]
        orok = sz.orok() if s != adu else [(False, False)] * len(sz.sorok)
        e: dict = {}
        for (w, _, _), (t, l, x), (o1, o2) in zip(sz.sorok, alap_h[s], orok):
            k = (t, l, x, o1, o2)
            e[k] = e.get(k, 0.0) + w
        uj: dict = {}
        for (t, l, x, c1, c2), p0 in allapot.items():
            for (t2, l2, x2, o1, o2), p2 in e.items():
                k = (min(cel, t + t2), min(tart + 9, l + l2), max(x, x2) if szan else min(8, x + x2),
                     min(2, c1 + o1), min(2, c2 + o2))
                uj[k] = uj.get(k, 0.0) + p0 * p2
        allapot = uj
    p_egy = sum(p for (t, l, x, c1, c2), p in allapot.items()
                if (c1 >= 2 or c2 >= 2) and not _siker(t, l, x, cel, tart, szan)
                and _siker(t + 1, max(0, l - 1), x, cel, tart, szan))
    ki["BESZORITAS"] = (p_alap + BESZORITAS_F * p_egy, BESZORITAS_F * p_egy)
    # a kerekítési zaj ne számítson nyereségnek
    return {m: v if m == "ALAP" else (v[0], v[1] if v[1] > 1e-9 else 0.0) for m, v in ki.items()}


def gyorsitotar_urites() -> None:
    for fv in (ts.dd, ts._dd_rek, ts.dd_cel, ts._cel_rek):
        fv.cache_clear()
