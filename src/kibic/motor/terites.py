"""
Terítés (claim) a felvevő oldalán — 2026-10-24.

A terítés szabálya: a bejelentett terv a lapok BÁRMELY elhelyezkedése és
bármilyen ellenjáték ellen hozza a bejelentett ütésszámot. A licitből vett
következtetés NEM számít, csak a fizikai tények: a mi két kezünk és a
lejátszott lapok.

A terv: „föntről lefelé” lehívott biztos ütések, utána a maradék átadása.
Egy ütés akkor biztos, ha a nyerő lapunk felett nem lehet védőlap:

  * a hívott színben: a lapunk a még kint lévő lapok mindegyikénél nagyobb
    (vagy a színből már nincs kint lap), és színfelvételnél kint már nincs adu
    (különben egy renonsz védő lophat);
  * aduval (adu hívása, vagy a partnerkéz lop): az adunk a kint lévő aduk
    mindegyikénél nagyobb, vagy kint már nincs adu.

A „kint lévő lapok” a legrosszabb esetet követik: a hívott színből
ütésenként csak EGY lap fogy (egy védőnél lehet az összes), és a legmagasabb
kint lévő lap marad meg utoljára. Így a terv minden elosztás ellen áll; az
ütésszám ezért alsó becslés (bonyolult tervet — pl. beszorítást — nem lát).

A keresés mélységi, emlékezettel: melyik kézből melyik színt (a legkisebb
vagy a legnagyobb lappal), a másik kéz melyik lapot teszi hozzá (színre: a
legkisebbet vagy a legnagyobbat; renonszra: színenként a legkisebbet, adunál
a legnagyobbat is) — így a kézváltás (átmenet) és a blokkolás feloldása is
benne van.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..domain import LAPOK, SZINEK, Lap, kovetkezo_ules, vonal

CSUCS_LIMIT = 40000        # ennyi keresési csúcs után a legjobb eddigi terv marad (az is érvényes)


@dataclass
class Lepes:
    hivo: str               # ki hív (ülés)
    hivott: Lap
    tevo: str               # a partnerkéz
    tett: Lap
    nyero: str              # melyik kéz viszi


@dataclass
class Terites:
    utesek: int                     # a hátralévőkből ennyi biztosan a miénk
    hatralevo: int                  # ennyi ütés van még hátra
    eddig: int                      # a mi oldalunk eddigi ütései
    felvevo: str = ""
    terv: list[Lepes] = field(default_factory=list)

    @property
    def elso(self) -> Lap | None:
        return self.terv[0].hivott if self.terv else None

    @property
    def osszes(self) -> int:
        return self.eddig + self.utesek

    @property
    def mind(self) -> bool:
        return self.utesek == self.hatralevo


def _szep(l: Lap) -> str:
    return {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}[l.szin] + \
        {"A": "Á", "Q": "D", "J": "B", "T": "10"}.get(l.ertek, l.ertek)


def _nyero(utes: list[tuple[str, Lap]], adu: str | None) -> str:
    hivott = utes[0][1].szin
    def kulcs(x):
        l = x[1]
        return (2 if adu and l.szin == adu else 1 if l.szin == hivott else 0, l.rang)
    return max(utes, key=kulcs)[0]


def _eddigi_utesek(lejatszott, adu: str | None, oldal: str) -> int:
    n = 0
    for i in range(0, len(lejatszott) - len(lejatszott) % 4, 4):
        if vonal(_nyero(lejatszott[i:i + 4], adu)) == oldal:
            n += 1
    return n


def terites(allas) -> Terites | None:
    """
    A legjobb biztos terv (`allas`: lejatszas.JatekAllas). None, ha nem a felvevő
    oldal hív (befejezetlen ütésben nem terítünk), vagy nem látszik a két kéz.
    """
    if allas.vedo or allas.aktualis:
        return None
    felvevo, asztal = allas.felvevo, allas.asztal
    if felvevo not in allas.lathato or asztal not in allas.lathato:
        return None
    adu = allas.adu
    kezek = {felvevo: frozenset(allas.lathato[felvevo]), asztal: frozenset(allas.lathato[asztal])}
    hatralevo = 13 - len(allas.lejatszott) // 4
    if not kezek[allas.ules] or len(kezek[allas.ules]) != hatralevo:
        return None
    ismert = set(kezek[felvevo]) | set(kezek[asztal]) | {l for _, l in allas.lejatszott}
    kint = [Lap(sz, e) for sz in SZINEK for e in LAPOK if Lap(sz, e) not in ismert]
    csucs = {sz: max((l.rang for l in kint if l.szin == sz), default=-1) for sz in SZINEK}
    n0 = tuple(sum(1 for l in kint if l.szin == sz) for sz in SZINEK)
    idx = {sz: i for i, sz in enumerate(SZINEK)}
    partner = {felvevo: asztal, asztal: felvevo}
    emlek: dict = {}
    csucsok = [0]

    def biztos(w: Lap, hivott_szin: str, n: tuple) -> bool:
        if adu and w.szin == adu:
            return n[idx[adu]] == 0 or w.rang > csucs[adu]
        if w.szin != hivott_szin:
            return False
        if adu and n[idx[adu]] > 0:
            return False
        return n[idx[hivott_szin]] == 0 or w.rang > csucs[hivott_szin]

    def lepesek(H: frozenset, P: frozenset):
        for sz in SZINEK:
            sajat = sorted((l for l in H if l.szin == sz), key=lambda l: l.rang)
            if not sajat:
                continue
            hivhato = {sajat[0], sajat[-1]}
            szinben = sorted((l for l in P if l.szin == sz), key=lambda l: l.rang)
            if szinben:
                tehetok = {szinben[0], szinben[-1]}
            else:
                tehetok = set()
                for t in SZINEK:
                    ts = sorted((l for l in P if l.szin == t), key=lambda l: l.rang)
                    if ts:
                        tehetok.add(ts[0])
                        if adu and t == adu:
                            tehetok.add(ts[-1])
            for h in sorted(hivhato, key=lambda l: -l.rang):
                # a partnerkéz előbb a kis lapot próbálja: a terv így természetesebb
                for t in sorted(tehetok, key=lambda l: (bool(adu) and l.szin == adu, l.rang)) or [None]:
                    yield h, t

    def keres(hivo: str, H: frozenset, P: frozenset, n: tuple, maradek: int):
        kulcs = (hivo, H, P, n)
        if kulcs in emlek:
            return emlek[kulcs]
        csucsok[0] += 1
        legjobb: tuple[int, list] = (0, [])
        if maradek <= 0 or csucsok[0] > CSUCS_LIMIT:
            return legjobb
        for h, t in lepesek(H, P):
            if t is None:               # a partnerkéz üres (nem fordulhat elő szabályos állásban)
                continue
            if t.szin == h.szin:
                nyero, w = (partner[hivo], t) if t.rang > h.rang else (hivo, h)
            elif adu and t.szin == adu:
                nyero, w = partner[hivo], t
            else:
                nyero, w = hivo, h
            if not biztos(w, h.szin, n):
                continue
            n2 = list(n)
            if n2[idx[h.szin]] > 0:
                n2[idx[h.szin]] -= 1
            H2, P2 = H - {h}, P - {t}
            kezek2 = {hivo: H2, partner[hivo]: P2}
            alatta = keres(nyero, kezek2[nyero], kezek2[partner[nyero]], tuple(n2), maradek - 1)
            if 1 + alatta[0] > legjobb[0]:
                legjobb = (1 + alatta[0], [Lepes(hivo, h, partner[hivo], t, nyero)] + alatta[1])
                if legjobb[0] == maradek:
                    break
        emlek[kulcs] = legjobb
        return legjobb

    db, terv = keres(allas.ules, kezek[allas.ules], kezek[partner[allas.ules]], n0, hatralevo)
    return Terites(db, hatralevo, _eddigi_utesek(allas.lejatszott, adu, vonal(felvevo)),
                   felvevo, terv)


def szoveg(t: Terites) -> str:
    """A bejelentés: a lehívás sorrendje kezenként, és amit átadunk."""
    if not t.terv:
        return f"Terítek: a hátralévő {t.hatralevo} ütés a védőké."
    reszek: list[tuple[str, list[str]]] = []
    for l in t.terv:
        hol = "kézből" if l.hivo == t.felvevo else "asztalról"
        if l.nyero == l.hivo:
            jel = _szep(l.hivott)
        elif l.tett.szin == l.hivott.szin:
            jel = f"{_szep(l.hivott)}→{_szep(l.tett)}"
        else:
            jel = f"{_szep(l.hivott)} lopva {_szep(l.tett)}"
        if reszek and reszek[-1][0] == hol:
            reszek[-1][1].append(jel)
        else:
            reszek.append((hol, [jel]))
    sor = "; ".join(f"{hol} {' '.join(j)}" for hol, j in reszek)
    if t.mind:
        return f"Terítek: mind a {t.hatralevo} ütés a miénk. Sorban: {sor}."
    return (f"Terítek: a hátralévő {t.hatralevo} ütésből {t.utesek} a miénk, "
            f"{t.hatralevo - t.utesek} a védőké. Sorban: {sor}, a többit átadom.")
