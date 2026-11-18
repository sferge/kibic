"""
A helyzetfelmérés (2026-11-18, Felvevő tervjáték) — a tervkészítés első lépése, a
szerkesztő leírása szerint (ahogy a jó játékos kezdi):

  1. a biztos ütések színenként (a felső lapok, amelyeket a hívás elvesztése nélkül
     lehívhatunk);
  2. a hiányzó ütések: a vállalás − a biztos ütések;
  3. a biztosan kiadó ütések: amit semmilyen játékkal nem kerülhetünk el (a kint lévő
     lapok, amelyek a mi legnagyobb lapunk fölött vannak — amíg a kezünkben van
     a színből, és lopni nem tudunk);
  4. az egyenleg: a megengedett kiadás (hátralévő ütések − vállalás) − a biztosan
     kiadó ütések. Ha nem negatív, elvileg lehet terv;
  5. színjátékban a vesztők a fő kéz (a hosszabb adus kéz) szemszögéből: a várható
     vesztők elosztásonként (a felső lapokkal lejátszva, impassz nélkül — a védők
     a felső lapjukat akkor teszik, ha üt). A vesztőtöbblet (várható vesztők − a
     megengedett kiadás) mondja meg, hány vesztőtől kell megszabadulni (lopás,
     dobás, impassz, kimagasítás).

Ez csak számolás a látott lapokon és a kint lévő lapok elosztásain (keresés nincs).
A források (2. lépés) és a kombinálás erre épül.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import comb

from ..domain import Lap

SZIN = dict(zip("SHDC", "♠♥♦♣"))


@dataclass
class SzinFelmeres:
    szin: str
    mi: tuple[int, int]               # a két kezünk hossza (felvevő, asztal)
    kint: int                         # a kint lévő lapok száma
    biztos: int                       # biztos ütések (felső lapok)
    kiado: int                        # biztosan kiadó ütések
    vesztok: float                    # várható vesztők (színjátékban a fő kéz köreiben)
    vesztok_max: int                  # a legrosszabb elosztásnál (legalább 5% eséllyel)


@dataclass
class Felmeres:
    adu: str | None
    fo_kez: str | None
    cel: int                          # a hátralévő ütésekből ennyi kell
    hatra: int
    szinek: list[SzinFelmeres] = field(default_factory=list)

    @property
    def biztos(self) -> int:
        return sum(s.biztos for s in self.szinek)

    @property
    def hiany(self) -> int:
        return max(0, self.cel - self.biztos)

    @property
    def megengedett(self) -> int:
        return self.hatra - self.cel

    @property
    def kiado(self) -> int:
        return sum(s.kiado for s in self.szinek)

    @property
    def egyenleg(self) -> int:
        return self.megengedett - self.kiado

    @property
    def vesztok(self) -> float:
        return sum(s.vesztok for s in self.szinek)

    @property
    def vesztotobblet(self) -> float:
        return self.vesztok - self.megengedett

    def sorok(self) -> list[str]:
        """Olvasható összefoglaló (a tanári asztalnak)."""
        ki = [f"Kell még {self.cel} ütés a hátralévő {self.hatra}-ből; megengedett kiadás: {self.megengedett}.",
              f"Biztos ütés: {self.biztos} — hiányzik {self.hiany}.",
              f"Biztosan kiadó: {self.kiado} — egyenleg: {self.egyenleg:+d} "
              + ("(elvileg lehet terv)" if self.egyenleg >= 0 else "(nincs terv: a biztos kiadás több a megengedettnél)")]
        if self.adu:
            ki.append(f"Vesztők a fő kéz ({self.fo_kez}) szemszögéből: várhatóan {self.vesztok:.1f}; "
                      + (f"ebből {self.vesztotobblet:.1f}-től kell megszabadulni (lopás, dobás, impassz, kimagasítás)."
                         if self.vesztotobblet > 0.05 else "nem kell vesztőtől megszabadulni."))
        return ki


def _rangok(lapok, sz) -> list[int]:
    return sorted((l.rang for l in lapok if l.szin == sz), reverse=True)


def _elosztasok(kint: list[int], n1: int, n2: int):
    """A kint lévő lapok (egy szín) minden elosztása a két védő között, súllyal: a
    védők n1, n2 ismeretlen lapja közül ennyi esik erre a színre (hipergeometrikus,
    minden konkrét elosztás egyformán valószínű)."""
    N = n1 + n2
    m = len(kint)
    for k in range(0, m + 1):
        if k > n1 or m - k > n2:
            continue
        w = comb(N - m, n1 - k) if 0 <= n1 - k <= N - m else 0
        if not w:
            continue
        for a in combinations(kint, k):
            b = [r for r in kint if r not in a]
            yield w, list(a), b


def _verseny(X: list[int], Y: list[int], V1: list[int], V2: list[int], korok: int) -> int:
    """A védők ütései az első `korok` körben, ha felülről játszunk (impassz nélkül):
    körönként a nagyobb lapunk megy (a másik kezünk a legkisebbjét adja), a védők a
    legnagyobb lapjukat teszik, ha üt, különben a legkisebbet."""
    X, Y, V1, V2 = sorted(X), sorted(Y), sorted(V1), sorted(V2)    # növekvő: [-1] a legnagyobb
    vedo = 0
    for _ in range(korok):
        if not X and not Y:
            break
        if not V1 and not V2:
            break
        a = X[-1] if X else 0
        b = Y[-1] if Y else 0
        mi = max(a, b)
        if a >= b:
            X.pop()
            if Y:
                Y.pop(0)
        else:
            Y.pop()
            if X:
                X.pop(0)
        legjobb = max(V1[-1] if V1 else 0, V2[-1] if V2 else 0)
        if legjobb > mi:
            vedo += 1
            if V1 and V1[-1] == legjobb:
                V1.pop()
                if V2:
                    V2.pop(0)
            else:
                V2.pop()
                if V1:
                    V1.pop(0)
        else:
            if V1:
                V1.pop(0)
            if V2:
                V2.pop(0)
    return vedo


def felmeres(kezek: dict[str, set[Lap]], felvevo: str, asztal: str, kint: set[Lap],
             vedo_lapok: tuple[int, int], adu: str | None, cel: int, hatra: int) -> Felmeres:
    """`kezek`: a két kezünk MOSTANI lapjai; `kint`: a védők még le nem játszott lapjai;
    `vedo_lapok`: a két védő kezében lévő lapok száma."""
    fo = None
    if adu:
        a1, a2 = (len([l for l in kezek[u] if l.szin == adu]) for u in (felvevo, asztal))
        fo = felvevo if a1 >= a2 else asztal
    mas = asztal if fo == felvevo else felvevo
    f = Felmeres(adu, fo, cel, hatra)
    n1, n2 = vedo_lapok
    for sz in "SHDC":
        X, Y = _rangok(kezek[felvevo], sz), _rangok(kezek[asztal], sz)
        K = sorted((l.rang for l in kint if l.szin == sz), reverse=True)
        kmax = K[0] if K else 0
        felso = sum(1 for r in X + Y if r > kmax)
        hosszabb = max(len(X), len(Y))
        # ha a felső lapjainkkal a védők minden lapját kihúzzuk, a hosszabb kéz minden lapja nyerő
        biztos = hosszabb if felso >= len(K) and (X or Y) else min(felso, hosszabb)
        mi_max = max(X + Y, default=0)
        fole = sum(1 for r in K if r > mi_max)
        # a körök, amelyekben a kezünkből adni kell (színjátékban a fő kéz köreiben;
        # ha a másik kéz rövidebb és van adója, utána lophat)
        if adu and sz != adu:
            Mh = len(X) if fo == felvevo else len(Y)
            Oh = len(Y) if fo == felvevo else len(X)
            o_adu = sum(1 for l in kezek[mas] if l.szin == adu)
            korok = Mh if not (Oh < Mh and o_adu) else Oh
            korok_v = Mh
        else:
            korok = hosszabb
            korok_v = hosszabb
        kiado = min(fole, korok, len(K))
        # várható vesztők: a felülről játszott körökben a védők ütései, elosztásonként
        ossz = suly = 0
        eloszl = []
        if K and (X or Y):
            for w, a, b in _elosztasok(K, n1, n2):
                v = _verseny(X, Y, a, b, korok_v)
                ossz += w * v
                suly += w
                eloszl.append((v, w))
        vart = ossz / suly if suly else 0.0
        vmax = 0
        if eloszl:
            for v, w in sorted(eloszl, reverse=True):
                if sum(ww for vv, ww in eloszl if vv >= v) / suly >= 0.05:
                    vmax = v
                    break
        f.szinek.append(SzinFelmeres(sz, (len(X), len(Y)), len(K), biztos, kiado, vart, vmax))
    return f


def felmeres_jatekbol(j, cel_osszes: int) -> Felmeres:
    """A felmérés egy `tervjatszo.Jatek` mostani állásából (a felvevő látta lapokból)."""
    F, A = j.felvevo, j.asztal
    kint = {l for sz in "SHDC" for l in j.kint(sz)}
    vedok = [u for u in "NESW" if u not in (F, A)]
    lejatszott = {u: sum(1 for uu, _ in j.lapok if uu == u) for u in vedok}
    n = tuple(13 - lejatszott[u] for u in vedok)
    hatra = 13 - len(j.lapok) // 4
    cel = max(0, cel_osszes - j.felvevo_utesek())
    return felmeres({F: set(j.kezek[F]), A: set(j.kezek[A])}, F, A, kint, n, j.adu, cel, hatra)
