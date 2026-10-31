"""
A tervező végrehajthatóság-ellenőrzője (2026-10-31, Felvevő tervjáték).

A tervező az esélyt egyszerűsített védőkkel számolja (lásd `tervezo.py`): a védő
csak akkor lop, ha színhiányos és van adója; más védekezést nem ismer. Ez a
modul a tervet konkrét (sorsolt) világokon VALÓDI lapokkal játssza le, DD-védők
ellen:

  1. a világ osztálya (hosszak, a releváns figurák helye) → a tervező útja ebben
     az osztályban, a terv rögzített politikájával (a megfigyelésen múló döntések
     ugyanazok, mint a számolásban) — ez a modell jóslata (0/1);
  2. a mi lapjaink az út szerint, a védőké a DD szerint; ha a valóság eltér a
     modelltől (más nyeri az ütést, más hív), a maradékot a DD játssza (ez
     enyhén optimista, ezért külön számoljuk);
  3. ha a terv célt ért (vagy a begyűjtést halasztja), a maradékot a DD játssza.

Az eredmény: a terv „végrehajtott” esélye, és a modell jóslatától eltérő
világok (ezekből látszik, mit nem tud még a séma vagy a tervező).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..domain import Lap, kovetkezo_ules, vonal
from ..domain.kartya import Kez, Leosztas
from . import tervjatszo as tj
from .tervezo import Allapot, Eset, Ertekelo, Helyzet, Terv, kezdo_allapot
from .tervszamolo import Korlat, Osztaly


@dataclass
class Ellenorzes:
    n: int = 0
    teljesult: int = 0
    modell: int = 0
    elteres: int = 0                      # a valóság eltért a modell útjától
    egyezik: int = 0
    peldak: list = field(default_factory=list)   # (modell, valóság, E lapjai)

    @property
    def esely(self) -> float:
        return self.teljesult / self.n if self.n else 0.0

    @property
    def modell_esely(self) -> float:
        return self.modell / self.n if self.n else 0.0


def vilagok(leosztas: Leosztas, jatszott: list[tuple[str, Lap]], kint: set[Lap], db: int,
            korlatok: list[Korlat] = (), mag: int = 1) -> list[Leosztas]:
    """Sorsolt világok: a kint lévő lapok véletlen elosztása a két védő között
    (egyenletesen, a korlátok mellett)."""
    rnd = random.Random(mag)
    lejatszott = {u: {l for uu, l in jatszott if uu == u} for u in "NESW"}
    kint_l = sorted(kint, key=str)
    n_e = 13 - len(lejatszott["E"])
    ki = []
    probak = 0
    while len(ki) < db and probak < db * 200:
        probak += 1
        e = set(rnd.sample(kint_l, n_e))
        w = set(kint_l) - e
        jo = True
        for k in korlatok:
            h = sum(1 for l in (e if k.kez == "E" else w) if l.szin == k.szin)
            if not (k.min <= h <= k.max):
                jo = False
        if not jo:
            continue
        ki.append(Leosztas({"N": leosztas.kezek["N"], "S": leosztas.kezek["S"],
                            "E": Kez(frozenset(e | lejatszott["E"])),
                            "W": Kez(frozenset(w | lejatszott["W"]))},
                           leosztas.oszto, leosztas.beliallas))
    return ki


def _ut(l: Lap, nyl: Lap, hivott: str, adu: str | None) -> bool:
    """Az `l` lap üti-e a mostani nyerő `nyl` lapot?"""
    if l.szin == nyl.szin:
        return l.rang > nyl.rang
    return bool(adu) and l.szin == adu and nyl.szin != adu


def _osztaly(vilag: Leosztas, kint: set[Lap], relevans: set[Lap], azon: int) -> Osztaly:
    hossz, birt = {}, {}
    for u in ("E", "W"):
        lapok = set(vilag.kezek[u].lapok) & kint
        for sz in "SHDC":
            hossz[(u, sz)] = sum(1 for l in lapok if l.szin == sz)
        for l in relevans:
            if l in lapok:
                birt[l] = u
    return Osztaly(hossz, birt, 1, azon)


def ellenoriz(helyzet: Helyzet, terv: Terv, politika: dict, vilaglista: list[Leosztas],
              kontraktus, jatszott: list[tuple[str, Lap]], relevans: set[Lap], dd_fv=None,
              kezdo: Allapot | None = None) -> Ellenorzes:
    if dd_fv is None:
        from ..solver.dds import lap_elemzes as dd_fv
    a = helyzet.allas
    adu = a.adu
    cel_osszes = 6 + kontraktus.szint
    if kezdo is None:
        kezdo = kezdo_allapot(a)
    ki = Ellenorzes()
    for i, lo in enumerate(vilaglista):
        o = _osztaly(lo, a.kint, relevans, 100000 + i)
        ert = Ertekelo(helyzet, terv, kockazat=True)
        ert.politika_rogzitett = politika
        ert.ut = []
        st = ert.kiaduzas(kezdo, "mind" if terv.kiaduzas >= 13 else terv.kiaduzas)
        modell = ert.futtat([Eset(o, 1, helyzet.tartalek, helyzet.hiany)], 0, 0, st) > 0
        ut = list(ert.ut)

        g = tj.Jatek({u: set(lo.kezek[u].lapok) for u in "NESW"}, a.felvevo, adu, [], tj.Terv(()))
        g.tesz(jatszott[0][0], jatszott[0][1])
        for u, l in jatszott[1:]:
            g.tesz(g.soron(), l)
        jovo = {l for e in ut if e[0] in ("kor", "adu") for l in e[2].values()}
        foglalt = {l for pp in terv.lepesek for l in pp.hasznal}
        elter = False

        def dd(u: str) -> Lap:
            ered = dd_fv(lo, [str(l) for _, l in g.lapok], kontraktus)
            if vonal(u) == vonal(a.felvevo):
                legj = max(e.felvevo_osszesen for e in ered)
                jo = [e for e in ered if e.felvevo_osszesen == legj]
            else:
                legj = max(e.utesek for e in ered)
                jo = [e for e in ered if e.utesek == legj]
            return min((Lap.parse(e.lap) for e in jo), key=lambda l: (l.rang, l.szin))

        def kor_lejatszasa(hivo: str, lapok: dict) -> bool:
            """Egy kör: a mi lapjaink a lapok szerint, a védőké DD; True, ha a
            valóság egyezik (mi hívtunk, és a lapjaink szabályosak)."""
            if g.soron() != hivo or g.aktualis():
                return False
            for j in range(4):
                u = kovetkezo_ules(hivo, j)
                if u in lapok:
                    l = lapok[u]
                    utes = g.aktualis()
                    van = [x for x in g.kezek[u] if utes and x.szin == utes[0][1].szin]
                    if l not in g.kezek[u] or (van and l.szin != utes[0][1].szin):
                        return False
                    if utes:
                        # fedés: ha a védő lapja viszi az ütést, és a tervezett lapunk nem
                        # üti, a legolcsóbb lapunk, amely üti (a kotta „ha fed: fölé” szabálya)
                        nyu, nyl = g.nyertes(utes)
                        if vonal(nyu) != vonal(a.felvevo) and not _ut(l, nyl, utes[0][1].szin, adu):
                            jobb = [x for x in (van or g.kezek[u]) if _ut(x, nyl, utes[0][1].szin, adu)]
                            if jobb:
                                l = min(jobb, key=lambda x: (x.szin == adu and utes[0][1].szin != adu, x.rang))
                    g.tesz(u, l)
                else:
                    g.tesz(u, dd(u))
            return True

        def kint_adu() -> int:
            return sum(1 for u in ("E", "W") for l in g.kezek[u] if l.szin == adu) if adu else 0

        for e in ut:
            if elter:
                break
            if e[0] in ("adu", "kor"):
                if not kor_lejatszasa(e[1], e[2]):
                    elter = True
            elif e[0] == "adu_vegig":
                # „mind”: amíg a védőknél adu van (a modell a legvalószínűbb körszámig ment)
                while kint_adu() > 0 and not elter:
                    T = max(("N", "S") if a.felvevo in "NS" else ("E", "W"),
                            key=lambda k: sum(1 for l in g.kezek[k] if l.szin == adu))
                    sajat = sorted((l for l in g.kezek[T] if l.szin == adu), key=lambda l: -l.rang)
                    if not sajat or g.soron() != T:
                        elter = True
                        break
                    pt = kovetkezo_ules(T, 2)
                    pa = sorted((l for l in g.kezek[pt] if l.szin == adu), key=lambda l: l.rang)
                    if pa:
                        pl = pa[0]
                    else:
                        # dobás: nem a terv lapja, a leghosszabb szabad színből a legkisebb
                        szabad = [l for l in g.kezek[pt] if l not in jovo and l not in foglalt] \
                            or [l for l in g.kezek[pt] if l not in jovo] or list(g.kezek[pt])
                        hossz = {sz: sum(1 for l in szabad if l.szin == sz) for sz in "SHDC"}
                        pl = min(szabad, key=lambda l: (-hossz[l.szin], l.rang))
                    if not kor_lejatszasa(T, {T: sajat[0], pt: pl}):
                        elter = True
            elif e[0] in ("halaszt", "siker", "kudarc"):
                break
        veg = ut[-1][0] if ut else "kudarc"
        # a maradék: a DD (a terv célt ért, vagy a valóság eltért)
        while len(g.lapok) < 52:
            u = g.soron()
            g.tesz(u, dd(u))
        tel = g.felvevo_utesek() >= cel_osszes
        if not elter and veg == "kudarc":
            tel = False                        # a terv elfogyott: nem a terv érdeme
        ki.n += 1
        ki.teljesult += tel
        ki.modell += modell
        ki.elteres += elter
        ki.egyezik += (tel == modell)
        if tel != modell and len(ki.peldak) < 8:
            e_lapok = " ".join(sorted(str(l) for l in lo.kezek["E"].lapok if l in a.kint))
            ki.peldak.append((int(modell), int(tel), "eltérés" if elter else "", e_lapok))
    return ki
