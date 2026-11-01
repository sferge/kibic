"""
Tervezés ütés közben (2026-11-01, Felvevő tervjáték): a védő hívott, és nekünk
döntésünk van (RELEVANS_UTES 2. és 3. eset: dobás, ütés-döntés).

    jelöltek: a két kezünk lépései az ütésben — a második helyen ülő kezünk
              lapja (kicsi; minden nagyobb lapcsoport legkisebbje; lopás kis /
              nagy aduval; dobás színenként), a negyedik helyen ülő kezünk
              politikája (üt, ha kell — a legolcsóbbal; kicsi; átvétel a
              partner nyerője fölé; dobás színenként)
    világok:  a védők lapjai sorsolva (a megfigyelt színhiányokkal); a harmadik
              helyen ülő védő üt, ha tud (a legolcsóbbal, lopással is), ha a
              partnere nem viszi; különben a legkisebbet adja
    érték:    az ütés után kialakult állás (a látott lapok szerint csoportosítva)
              legjobb tervének esélye (a tervező; a drága tervek becsléssel); ha a
              védők hívnak, a számunkra legrosszabb visszahívás színe (világonként),
              `visszahivas_melyseg` mélységig; alatta úgy számolunk, mintha mi
              hívnánk (egyszerűsítés)

A jelölt értéke a csoportok súlyozott átlaga. A választott jelölt a mostani
lapunkat adja; a negyedik kéz politikája az ütés végén dönt.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..domain import SZINEK, Lap, kovetkezo_ules
from .tervsema import Allas, strategiak_betoltese
from .tervszamolo import Korlat


@dataclass(frozen=True)
class Lepes:
    """Egy kezünk lépése: lap (2. hely) vagy politika (4. hely)."""
    fajta: str                    # lap / kicsi / ut / atvesz / dob
    lap: Lap | None = None
    szin: str | None = None       # dob: ebből a színből a legkisebb

    def szoveg(self) -> str:
        if self.fajta == "lap":
            return str(self.lap)
        if self.fajta == "dob":
            return f"dob {'♠♥♦♣'['SHDC'.index(self.szin)]}"
        return {"kicsi": "kicsi", "ut": "üt, ha kell", "atvesz": "átvesz"}[self.fajta]


@dataclass
class UtesAllas:
    felvevo: str
    adu: str | None
    kezek: dict[str, set[Lap]]        # a két kezünk lapjai az ütés elején
    kint: set[Lap]                    # a védők le nem játszott lapjai (a hívott nélkül)
    hivo: str                         # a hívó védő
    hivott: Lap
    cel: int                          # a hátralévő ütésekből (ezzel együtt) ennyi kell
    hatra: int                        # hátralévő ütések (ezzel együtt)
    korlatok: list[Korlat] = field(default_factory=list)   # megfigyelt színhiányok

    @property
    def asztal(self) -> str:
        return kovetkezo_ules(self.felvevo, 2)

    def sorrend(self) -> list[str]:
        return [kovetkezo_ules(self.hivo, i) for i in range(4)]


@dataclass
class JeloltErtek:
    lepesek: dict[str, Lepes]
    ertek: float
    csoportok: list = field(default_factory=list)    # (súly, leírás, érték)

    politika: dict = field(default_factory=dict)    # a 4. kéz: a 3. lap → lépés

    def szoveg(self) -> str:
        if len(set(self.politika.values())) > 1:
            k2, k4 = list(self.lepesek)
            return (f"{k2}: {self.lepesek[k2].szoveg()}, {k4}: a 3. kéz lapja szerint ("
                    + "; ".join(f"{l}-re {p.szoveg()}" for l, p in self.politika.items()) + ")")
        return ", ".join(f"{k}: {l.szoveg()}" for k, l in self.lepesek.items())


# --- lapok és szabályok egy ütésben ---------------------------------------------------

def _rang(l: Lap) -> int:
    return l.rang


def _nyero(utes: list[tuple[str, Lap]], adu: str | None) -> tuple[str, Lap]:
    hivott = utes[0][1].szin
    def kulcs(x):
        l = x[1]
        return (2 if adu and l.szin == adu else 1 if l.szin == hivott else 0, l.rang)
    return max(utes, key=kulcs)


def _ut(l: Lap, nyero: Lap, hivott: str, adu: str | None) -> bool:
    """l üti-e a mostani nyerőt."""
    if l.szin == nyero.szin:
        return l.rang > nyero.rang
    if adu and l.szin == adu:
        return nyero.szin != adu
    return False


def _dobas(kez: set[Lap], adu: str | None, szin: str | None = None) -> Lap:
    if szin:
        sajat = [l for l in kez if l.szin == szin]
        if sajat:
            return min(sajat, key=_rang)
    jelolt = [l for l in kez if l.szin != adu] or list(kez)
    hossz = Counter(l.szin for l in jelolt)
    return min(jelolt, key=lambda l: (-hossz[l.szin], l.rang))


def _csoportok(lapok: list[Lap], kint_szin: set[Lap]) -> list[Lap]:
    """Egyenértékű lapok (köztük nincs kint lévő lap): a csoportok legkisebbje."""
    lapok = sorted(lapok, key=_rang)
    ki = []
    for l in lapok:
        if ki and not any(ki[-1].rang < k.rang < l.rang for k in kint_szin):
            continue
        ki.append(l)
    return ki


def _vedo_lap(kez: set[Lap], utes: list, adu: str | None, partner: str) -> Lap:
    """A védő: ha a partnere viszi, kicsi; különben üt a legolcsóbbal, ha tud."""
    hivott = utes[0][1].szin
    nyu, nyl = _nyero(utes, adu)
    sajat = [l for l in kez if l.szin == hivott]
    if nyu == partner:
        return min(sajat, key=_rang) if sajat else _dobas(kez, adu)
    if sajat:
        ut = [l for l in sajat if _ut(l, nyl, hivott, adu)]
        return min(ut or sajat, key=_rang)
    if adu:
        ut = [l for l in kez if l.szin == adu and _ut(l, nyl, hivott, adu)]
        if ut:
            return min(ut, key=_rang)
    return _dobas(kez, adu)


def _mi_lap(kez: set[Lap], lepes: Lepes, utes: list, adu: str | None, partner: str,
            hely: int) -> Lap:
    hivott = utes[0][1].szin
    sajat = [l for l in kez if l.szin == hivott]
    nyu, nyl = _nyero(utes, adu)
    if lepes.fajta == "lap":
        return lepes.lap
    if lepes.fajta == "dob":
        if sajat:
            return min(sajat, key=_rang)
        return _dobas(kez, adu, lepes.szin)
    if lepes.fajta == "atvesz" and nyu == partner:
        felette = [l for l in sajat if l.rang > nyl.rang]
        if felette:
            return min(felette, key=_rang)
    if lepes.fajta == "ut" and nyu != partner:
        ut = [l for l in sajat if _ut(l, nyl, hivott, adu)]
        if not sajat and adu:
            ut = [l for l in kez if l.szin == adu and _ut(l, nyl, hivott, adu)]
        if ut:
            return min(ut, key=_rang)
    if sajat:
        return min(sajat, key=_rang)
    return _dobas(kez, adu)


def jeloltek(a: UtesAllas) -> list[dict[str, Lepes]]:
    """A két kezünk lépései (2. hely: lap; 4. hely: politika)."""
    sor = a.sorrend()
    masodik, negyedik = sor[1], sor[3]
    sz = a.hivott.szin
    kint_sz = {l for l in a.kint if l.szin == sz} | {a.hivott}

    def lapok_masodik() -> list[Lepes]:
        kez = a.kezek[masodik]
        sajat = [l for l in kez if l.szin == sz]
        if sajat:
            nagy = [l for l in sajat if l.rang > a.hivott.rang]
            ki = [Lepes("lap", min(sajat, key=_rang))]
            ki += [Lepes("lap", l) for l in _csoportok(nagy, kint_sz) if l != ki[0].lap]
            return ki
        ki = []
        if a.adu and a.adu != sz:
            adu = sorted((l for l in kez if l.szin == a.adu), key=_rang)
            if adu:
                ki.append(Lepes("lap", adu[0]))
                if adu[-1] != adu[0]:
                    ki.append(Lepes("lap", adu[-1]))
        for s in SZINEK:
            if s != sz and s != a.adu and any(l.szin == s for l in kez):
                ki.append(Lepes("dob", szin=s))
        return ki or [Lepes("kicsi")]

    def politika_negyedik() -> list[Lepes]:
        kez = a.kezek[negyedik]
        sajat = [l for l in kez if l.szin == sz]
        ki = [Lepes("ut"), Lepes("atvesz")] if sajat else []
        if sajat:
            ki.append(Lepes("kicsi"))
            return ki
        if a.adu and a.adu != sz and any(l.szin == a.adu for l in kez):
            ki.append(Lepes("ut"))
        for s in SZINEK:
            if s != sz and s != a.adu and any(l.szin == s for l in kez):
                ki.append(Lepes("dob", szin=s))
        return ki or [Lepes("kicsi")]

    return [{masodik: l2, negyedik: l4} for l2 in lapok_masodik() for l4 in politika_negyedik()]


# --- világok ---------------------------------------------------------------------------

def vilagok(kint: set[Lap], meret: dict[str, int], hiany: dict[str, set[str]], db: int,
            mag: int = 1) -> list[dict[str, set[Lap]]]:
    """A kint lévő lapok szétosztása a két védő közt (méret szerint), a megfigyelt
    színhiányokkal: a kényszerű lapok előbb, a többi egyenletesen."""
    v1, v2 = list(meret)
    rnd = random.Random(mag)
    ki = []
    for _ in range(db):
        kez = {v1: set(), v2: set()}
        szabad = []
        for l in kint:
            if l.szin in hiany.get(v1, ()):
                kez[v2].add(l)
            elif l.szin in hiany.get(v2, ()):
                kez[v1].add(l)
            else:
                szabad.append(l)
        rnd.shuffle(szabad)
        kell = meret[v1] - len(kez[v1])
        if kell < 0 or kell > len(szabad):
            continue
        kez[v1] |= set(szabad[:kell])
        kez[v2] |= set(szabad[kell:])
        ki.append(kez)
    return ki


# --- az értékelés ----------------------------------------------------------------------

class UtesTervezo:
    def __init__(self, a: UtesAllas, db: int | None = None, melyseg: int | None = None,
                 naplo=None):
        _, szab = strategiak_betoltese()
        r = next((s for s in szab if s.get("szabaly") == "RELEVANS_UTES"), {})
        self.db = db or int(r.get("vilagok", 120))
        self.melyseg = int(r.get("visszahivas_melyseg", 1)) if melyseg is None else melyseg
        self.a = a
        self.tar: dict = {}
        self.naplo = naplo
        self.tervezesek = 0
        self.gyujt: dict | None = None     # gyűjtő menet: a szükséges állások

    # az ütés után: a tervező értéke (gyorsítótárral; gyűjtő menetben csak felírja)
    def _allas_erteke(self, kezek, kint, cel, hatra, soron, korlatok) -> float:
        if cel <= 0:
            return 1.0
        if cel > hatra:
            return 0.0
        kulcs = (tuple(sorted((k, frozenset(v)) for k, v in kezek.items())), frozenset(kint),
                 cel, hatra, soron, tuple(sorted(set((k.kez, k.szin) for k in korlatok))))
        if kulcs in self.tar:
            return self.tar[kulcs]
        if self.gyujt is not None:
            self.gyujt[kulcs] = (self.a.felvevo, self.a.adu, kulcs)
            return 0.5
        v = _allas_tervezese((self.a.felvevo, self.a.adu, kulcs))[1]
        self.tervezesek += 1
        self.tar[kulcs] = v
        return v

    def _szamol_gyujtottek(self) -> None:
        """A gyűjtő menet állásai: tervezés párhuzamosan (külön folyamatonként egy
        állás; a folyamaton belül az elemzések egy szálon)."""
        from concurrent.futures import ProcessPoolExecutor
        import multiprocessing as mp
        from .tervparhuzam import szalak_szama
        feladat = [f for k, f in self.gyujt.items() if k not in self.tar]
        self.gyujt = None
        if not feladat:
            return
        n = min(szalak_szama(), len(feladat))
        self.tervezesek += len(feladat)
        if n <= 1:
            for f in feladat:
                k, v = _allas_tervezese(f)
                self.tar[k] = v
            return
        belso = max(1, szalak_szama() // n)
        with ProcessPoolExecutor(max_workers=n, mp_context=mp.get_context("fork"),
                                 initializer=_szalak, initargs=(belso,)) as pool:
            for k, v in pool.map(_allas_tervezese, feladat):
                self.tar[k] = v

    @staticmethod
    def _jel(utes, mi: dict[str, set[Lap]]) -> tuple:
        """A látott ütés csoportkulcsa: a védők lapjai közül egyenértékűek azok,
        amelyek között nincs lapunk a színben (a sávjuk: hány lapunk van alattuk;
        ha a színben nincs lapunk, mind egyenértékű)."""
        ki = []
        for u, l in utes:
            if u in mi:
                ki.append((u, l))
                continue
            sajat = [x.rang for k in mi.values() for x in k if x.szin == l.szin]
            sav = sum(1 for r in sajat if r < l.rang) if sajat else "x"
            ki.append((u, l.szin, sav))
        return tuple(ki)

    def _utes(self, kezek, kint_vedo: dict[str, set[Lap]], sorrend, elso_lap,
              lepesek: dict[str, Lepes] | None):
        """Egy ütés lejátszása egy világban: (ütés, nyerő ülés)."""
        utes = [(sorrend[0], elso_lap)]
        for i, u in enumerate(sorrend[1:], start=1):
            partner = kovetkezo_ules(u, 2)
            if u in kezek:
                lep = lepesek.get(u) if lepesek else None
                l = _mi_lap(kezek[u], lep or _alap_lepes(i), utes, self.a.adu, partner, i)
            else:
                l = _vedo_lap(kint_vedo[u], utes, self.a.adu, partner)
            utes.append((u, l))
        return utes, _nyero(utes, self.a.adu)[0]

    def _ertekel_utes(self, kezek, kint, cel, hatra, korlatok, hivo, vilagok_, elso,
                      lepesek, melyseg, vilag_ertek: dict | None = None) -> tuple[float, list]:
        """Az ütés (a hívó első lapjával, világonként) és utána az állás értéke.
        `elso`: világ → a hívó lapja (None: ebben a világban nem hívhatja).
        `vilag_ertek`: ide kerül világonként (index) a csoportja értéke."""
        sorrend = [kovetkezo_ules(hivo, i) for i in range(4)]
        csop: dict = defaultdict(list)
        for i, w in enumerate(vilagok_):
            c = elso(w)
            if c is None:
                continue
            w2 = {u: set(v) for u, v in w.items()}
            w2[hivo].discard(c)
            utes, nyu = self._utes(kezek, w2, sorrend, c, lepesek)
            csop[self._jel(utes, kezek)].append((w, utes, nyu, i))
        n = sum(len(v) for v in csop.values())
        if not n:
            return 0.0, []
        ossz, leiras = 0.0, []
        for jel, elemek in csop.items():
            # a csoport képviselője: a leggyakoribb pontos ütés
            utes, nyu = Counter((tuple(x[1]), x[2]) for x in elemek).most_common(1)[0][0]
            mi_nyer = nyu in kezek
            kezek2 = {k: v - {l for u, l in utes if u == k} for k, v in kezek.items()}
            latott = {l for u, l in utes}
            kint2 = kint - latott
            kor2 = list(korlatok)
            for u, l in utes[1:]:
                if u not in kezek and l.szin != utes[0][1].szin:
                    kor2.append(Korlat(u, utes[0][1].szin, 0, 0, "megfigyelt"))
            cel2 = cel - (1 if mi_nyer else 0)
            if mi_nyer or melyseg <= 0:
                soron = nyu if mi_nyer else self.a.felvevo
                v = self._allas_erteke(kezek2, kint2, cel2, hatra - 1, soron, kor2)
            else:
                v = self._visszahivas(kezek2, kint2, cel2, hatra - 1, kor2, nyu,
                                      [(x[0], x[1]) for x in elemek], utes, melyseg - 1)
            w = len(elemek) / n
            ossz += w * v
            if vilag_ertek is not None:
                for x in elemek:
                    vilag_ertek[x[3]] = v
            leiras.append((w, " ".join(f"{u}:{l}" for u, l in utes) + (" (mi)" if mi_nyer else " (védők)"), v))
        return ossz, leiras

    def _visszahivas(self, kezek, kint, cel, hatra, korlatok, hivo, vilagok_, utes, melyseg):
        """A védő hív: világonként a számunkra legrosszabb szín (a legkisebb lapja)."""
        if cel > hatra:
            return 0.0
        # a világok a csoport képviselő ütéséhez igazítva: ha a világban egy másik (vele
        # egyenértékű kis) lapot adott a védő, a két lapot felcseréljük
        vil = []
        rep = {l for u, l in utes}
        for w, utes_w in vilagok_:
            akt = {l for u, l in utes_w}
            w2 = {u: set(v) - akt for u, v in w.items()}
            kulcs = lambda l: ("SHDC".index(l.szin), l.rang)
            for r, t in zip(sorted(rep - akt, key=kulcs), sorted(akt - rep, key=kulcs)):
                for v in w2:
                    if r in w2[v]:
                        w2[v].discard(r)
                        w2[v].add(t)
                        break
            vil.append(w2)
        ertekek = {}
        for s in SZINEK:
            def elso(w, s=s):
                lap = [l for l in w[hivo] if l.szin == s]
                return min(lap, key=_rang) if lap else None
            # a válaszunk rögzített szabály (üt, ha kell; kicsi; dobás)
            ertekek[s] = {}
            self._ertekel_utes(kezek, kint, cel, hatra, korlatok, hivo, vil, elso, None,
                               melyseg, ertekek[s])
        osszes = [min(ertekek[s][i] for s in SZINEK if i in ertekek[s])
                  for i in range(len(vil)) if any(i in ertekek[s] for s in SZINEK)]
        return sum(osszes) / len(osszes) if osszes else 0.0

    def tervez(self) -> list[JeloltErtek]:
        a = self.a
        hiany = defaultdict(set)
        for k in a.korlatok:
            if k.max == 0:
                hiany[k.kez].add(k.szin)
        vedok = [kovetkezo_ules(a.felvevo, 1), kovetkezo_ules(a.felvevo, 3)]
        meret = {v: a.hatra - (1 if v == a.hivo else 0) for v in vedok}
        vil = vilagok(a.kint, meret, hiany, self.db)
        for w in vil:
            w[a.hivo].add(a.hivott)         # a hívó lapja a világban is
        # két menet: az első csak összegyűjti az ütések utáni állásokat (a lejátszás
        # olcsó), ezeket párhuzamosan tervezzük, a második menet már a tárból számol
        self.gyujt = {}
        for lep in jeloltek(a):
            self._ertekel_utes(a.kezek, a.kint | {a.hivott}, a.cel, a.hatra, a.korlatok,
                               a.hivo, vil, lambda w: a.hivott, lep, self.melyseg)
        if self.naplo is not None:
            self.naplo(f"   {len(self.gyujt)} állás tervezése az ütés után")
        self._szamol_gyujtottek()
        # a második helyen ülő kezünk lapja most dől el; a negyedik kéz a harmadik
        # (védői) lap láttán dönt: megfigyelésenként a legjobb politikája számít
        sor = a.sorrend()
        csoport: dict = defaultdict(list)
        for lep in jeloltek(a):
            csoport[lep[sor[1]]].append(lep)
        ki = []
        for l2, lepesek in csoport.items():
            per = []
            for lep in lepesek:
                ve: dict = {}
                v, cs = self._ertekel_utes(a.kezek, a.kint | {a.hivott}, a.cel, a.hatra, a.korlatok,
                                           a.hivo, vil, lambda w: a.hivott, lep, self.melyseg, ve)
                per.append((lep, ve, cs, v))
            # megfigyelés világonként: a harmadik helyen ülő védő lapja
            megf = defaultdict(list)
            for i, w in enumerate(vil):
                w2 = {u: set(x) - {a.hivott} for u, x in w.items()}
                utes, _ = self._utes(a.kezek, w2, sor, a.hivott, per[0][0])
                megf[utes[2][1]].append(i)
            ossz, politika = 0.0, {}
            for lap3, idx in megf.items():
                legjobb = max(per, key=lambda x: sum(x[1].get(i, 0.0) for i in idx))
                politika[lap3] = legjobb[0][sor[3]]
                ossz += sum(legjobb[1].get(i, 0.0) for i in idx)
            v = ossz / len(vil) if vil else 0.0
            pol = sorted(set(politika.values()), key=lambda x: x.szoveg())
            lep = {sor[1]: l2, sor[3]: pol[0] if len(pol) == 1 else Lepes("kicsi")}
            je = JeloltErtek(lep, v, max(per, key=lambda x: x[3])[2])
            je.politika = politika
            ki.append(je)
            if self.naplo is not None:
                p4 = (pol[0].szoveg() if len(pol) == 1 else
                      "; ".join(f"{l}-re {politika[l].szoveg()}" for l in sorted(politika, key=lambda l: -l.rang)))
                self.naplo(f"   jelölt {sor[1]}: {l2.szoveg()}  ({sor[3]}: {p4}): {v:.1%}")
        ki.sort(key=lambda x: -x.ertek)
        return ki


def _szalak(n: int) -> None:
    """A folyamaton belüli elemzések szálai: a gép szálai elosztva a párhuzamosan
    tervezett állások közt (4 állás 32 szálon: 8-8)."""
    import os
    os.environ["KIBIC_SZALAK"] = str(n)


def _allas_tervezese(f) -> tuple:
    """Egy ütés utáni állás értéke: a tervező legjobb terve (a drága tervek
    becsléssel)."""
    felvevo, adu, kulcs = f
    kezek, kint, cel, hatra, soron, hiany = kulcs
    from .tervezo import helyzetelemzes, tervez
    allas = Allas(felvevo, adu, {k: set(v) for k, v in kezek}, set(kint), cel, hatra, soron)
    korl = [Korlat(k, sz, 0, 0, "megfigyelt") for k, sz in hiany]
    _, ert = tervez(allas, korl, draga_pontos=False)
    if ert:
        return kulcs, max(e.kockazattal for e in ert)
    return kulcs, 1.0 if helyzetelemzes(allas).hiany == 0 else 0.0


def _alap_lepes(hely: int) -> Lepes:
    """A rögzített válasz (visszahívásnál): 2. helyen kicsi, 4. helyen üt, ha kell."""
    return Lepes("ut") if hely == 3 else Lepes("kicsi")
