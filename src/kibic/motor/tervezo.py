"""
A felvevő tervezője (2026-10-31, Felvevő tervjáték) — a sémákból.

    helyzetelemzés → stratégiák → technikák példányai a lapokon → kombinációk a
    stratégia szabályai szerint → értékelés (pontos valószínűség, kockázattal)
    → választás → a következő technika

Az adatok: `rendszerek/tervek/sema/*.yaml` (technikák, stratégiák, általános
szabályok). Ez a modul a sémák általános értelmezője: a technika köreit
(kotta) lejátssza minden elosztás-osztályon, és közben alkalmazza az általános
szabályokat (ELLOPÁS, KIADUZÁS, ÁTMENET). A döntés a terv ágain (folytatás vagy
váltás a következő technikára) a megfigyelésen múlik: ugyanazon megfigyelés
mellett ugyanaz a döntés (információs halmaz), és a tervező a jobbikat
választja.

Egyszerűsítések (dokumentálva, hogy a mérés tudja, mit mér):
  - a védők lapjai közül csak a hossz és a releváns figurák helye számít;
  - a védő akkor lop, ha színhiányos és van adója (az addig lehúzott adukörök
    után); felüllopni a mi kezünk csak akkor tudja, ha minden kint lévő adunál
    nagyobb adója van;
  - a kiaduzás egy kőre a kiaduzó kéz legnagyobb aduja; a kiaduzás után a
    védőknél maradt adu: max(0, hossz − körök);
  - egy elvesztett ütés után (ha a tartalék engedi) ugyanonnan folytatjuk.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace

from ..domain import SZINEK, Lap, kovetkezo_ules
from .tervsema import (Allas, Kor, Peldany, kifejezes, peldanyok, strategiak_betoltese,
                       technikak_betoltese)
from .tervszamolo import Korlat, Osztaly, osztalyok, rejtett_fogalmak


SZK_TAR: dict = {}            # az egyszínű elemző futásai (a lapok és a cél szerint)


# --- 1. Helyzetelemzés ---------------------------------------------------------------

@dataclass
class Helyzet:
    allas: Allas
    biztos: dict[str, int]
    hiany: int
    tartalek: int

    def szoveg(self) -> str:
        b = ", ".join(f"{'♠♥♦♣'['SHDC'.index(s)]} {n}" for s, n in self.biztos.items() if n)
        return (f"cél {self.allas.cel} a hátralévő {self.allas.hatra}-ból; biztos {sum(self.biztos.values())} "
                f"({b}); hiány {self.hiany}; tartalék {self.tartalek}")


def helyzetelemzes(allas: Allas) -> Helyzet:
    biztos = {sz: allas.biztos_utesek(sz) for sz in SZINEK}
    return Helyzet(allas, biztos, max(0, allas.cel - sum(biztos.values())),
                   allas.hatra - allas.cel)


# --- 2. Terv és jelöltek -----------------------------------------------------------------

@dataclass
class Terv:
    strategia: str
    lepesek: list[Peldany]
    kiaduzas: int                      # ennyi adukör a technikák előtt

    @property
    def nev(self) -> str:
        return " → ".join(p.rovid for p in self.lepesek)


def jeloltek(helyzet: Helyzet, pld: list[Peldany], strategiak: dict) -> list[tuple[str, list[Peldany]]]:
    """A stratégiák technikasorai (a kombinálás szabályai szerint)."""
    ki = []
    for nev, s in strategiak.items():
        kor = {"hiany": helyzet.hiany, "tartalek": helyzet.tartalek}
        if not all(kifejezes(f, kor) for f in s.get("alkalmazhato", [])):
            continue
        tk = s.get("technikak", {})
        for n in range(int(tk.get("min", 1)), int(tk.get("max", 1)) + 1):
            for sor in itertools.permutations(pld, n):
                if len({(p.sema.azon.split("_FELSO")[0], p.szin) for p in sor}) < n:
                    continue
                if not _kombinalhato(sor, s, helyzet):
                    continue
                ki.append((nev, list(sor)))
    return ki


def _kombinalhato(sor, s: dict, helyzet: Helyzet) -> bool:
    szabalyok = s.get("kombinalas", [])
    if "elozok_probak" in szabalyok:
        kif = (s.get("minosites") or {}).get("proba", "kudarc_koltseg <= tartalek")
        for p in sor[:-1]:
            if not kifejezes(kif, {"kudarc_koltseg": p.sema.kudarc_koltseg,
                                   "tartalek": helyzet.tartalek}):
                return False
    if "nincs_elfogyasztas" in szabalyok:
        for i, p in enumerate(sor):
            for q in sor[i + 1:]:
                if p.elfogyaszt & q.hasznal:
                    return False
    return True


# --- 3. Az értékelő: a kotta lejátszása az osztályokon -----------------------------------

@dataclass(frozen=True)
class Allapot:
    """A determinisztikus rész (a mi lapjaink, a körök, ki van hívásban)."""
    kezek: tuple                 # ((kéz, frozenset lapok), …)
    korok: tuple                 # ((szín, körök száma), …)
    soron: str
    kiaduzva: bool = False       # a kiaduzás végig megy (amíg a védőknél adu van)

    def kez(self, k: str) -> frozenset:
        return dict(self.kezek)[k]

    def kor(self, sz: str) -> int:
        return dict(self.korok).get(sz, 0)


@dataclass
class Eset:
    o: Osztaly
    w: float
    tartalek: int
    hiany: int
    megfigyelt: tuple = ()        # az elemzős technikák látott kimenetei (a döntésekhez)


class Ertekelo:
    def __init__(self, helyzet: Helyzet, terv: Terv, kockazat: bool = True,
                 naplo: list | None = None):
        self.h = helyzet
        self.a = helyzet.allas
        self.terv = terv
        self.kockazat = kockazat
        self.naplo = naplo
        self._siker: dict = {}
        kint_adu = self.a.kint_szin(self.a.adu) if self.a.adu else []
        self.kint_adu_max = kint_adu[0].rang if kint_adu else 0
        self.kint_adu_db = len(kint_adu)
        self.vedok = self.a.vedok
        self._szk_cache: dict = {}
        self.politika: dict = {}              # (technika, kör, állapot, megfigyelés) → tovabb / valt
        self.politika_rogzitett: dict | None = None
        self.ut: list | None = None           # egyetlen eset útja (a végrehajtás-ellenőrzéshez)

    # -- a rejtett feltétel (csak itt, a számolásban) --
    def siker(self, p: Peldany, o: Osztaly) -> bool:
        kulcs = (id(p), o.azon)
        if kulcs not in self._siker:
            env = dict(rejtett_fogalmak(o))
            env.update(p.siker_kornyezet())
            self._siker[kulcs] = bool(kifejezes(p.sema.siker, env))
        return self._siker[kulcs]

    def adu_maradek(self, o: Osztaly, k: str, st: Allapot) -> int:
        if not self.a.adu:
            return 0
        t = o.kezhossz(k, self.a.adu)
        if st.kiaduzva:
            # végig kiaduzva: csak akkor marad adu, ha több van nála, mint a biztos aduütésünk
            return max(0, t - self.h.biztos.get(self.a.adu, 0))
        return max(0, t - st.kor(self.a.adu))

    # -- a lapjaink --
    def _foglalt(self, ti: int, ri: int) -> set[Lap]:
        f = set()
        for j, p in enumerate(self.terv.lepesek):
            if j > ti:
                f |= p.hasznal
            elif j == ti:
                for k in p.korok[ri:]:
                    if k.lap is not None:
                        f.add(k.lap)
        return f

    def _kicsi(self, st: Allapot, k: str, sz: str, foglalt: set[Lap]) -> Lap | None:
        lapok = sorted((l for l in st.kez(k) if l.szin == sz), key=lambda l: l.rang)
        szabad = [l for l in lapok if l not in foglalt]
        return (szabad or lapok or [None])[0]

    def _dobas(self, st: Allapot, k: str, foglalt: set[Lap]) -> Lap:
        lapok = list(st.kez(k))
        szabad = [l for l in lapok if l not in foglalt and l.szin != self.a.adu]
        jelolt = szabad or [l for l in lapok if l not in foglalt] or lapok
        hossz = {sz: sum(1 for l in jelolt if l.szin == sz) for sz in SZINEK}
        return min(jelolt, key=lambda l: (l.szin == self.a.adu, -hossz[l.szin], l.rang))

    def _tesz(self, st: Allapot, lapok: dict[str, Lap], szin: str, nyero: str) -> Allapot:
        kezek = tuple((k, frozenset(v - {lapok[k]}) if k in lapok else v) for k, v in st.kezek)
        korok = dict(st.korok)
        korok[szin] = korok.get(szin, 0) + 1
        return Allapot(kezek, tuple(sorted(korok.items())), nyero, st.kiaduzva)

    def _kovet(self, st: Allapot, k: str, sz: str, foglalt: set[Lap], lop: bool = False) -> Lap:
        van = [l for l in st.kez(k) if l.szin == sz]
        if van:
            return self._kicsi(st, k, sz, foglalt)
        if lop and self.a.adu:
            adu = sorted((l for l in st.kez(k) if l.szin == self.a.adu), key=lambda l: l.rang)
            if adu:
                fole = [l for l in adu if l.rang > self.kint_adu_max]
                return (fole or adu)[0]
        return self._dobas(st, k, foglalt)

    # -- egy kör a védők szemszögéből: ellopják-e? --
    def _ellopjak(self, e: Eset, st: Allapot, sz: str, hivo: str, lapok: dict[str, Lap],
                  lopo: str | None) -> bool:
        """ELLOPÁS: a kört ellopja-e egy védő (és nem tudjuk felüllopni)?"""
        if not self.kockazat or not self.a.adu or sz == self.a.adu:
            return False
        r = st.kor(sz) + 1
        sorrend = [kovetkezo_ules(hivo, i) for i in range(4)]
        for i, x in enumerate(sorrend):
            if x not in self.vedok:
                continue
            if e.o.kezhossz(x, sz) >= r or self.adu_maradek(e.o, x, st) <= 0:
                continue
            if lopo is not None:
                l = lapok.get(lopo)
                if l is not None and l.szin == self.a.adu and l.rang > self.kint_adu_max:
                    continue                    # a lopásunk elég magas: sem előtte, sem utána nem üt
                return True
            utana = sorrend[i + 1:]
            ment = any(m not in self.vedok and lapok.get(m) is not None
                       and lapok[m].szin == self.a.adu and lapok[m].rang > self.kint_adu_max
                       for m in utana)
            if not ment:
                return True
        return False

    # -- a kiaduzás és az átmenet --
    def kiaduzas(self, st: Allapot, korok: int | str) -> Allapot:
        """Adukörök a technikák előtt: a hosszabb adus kéz a legnagyobb aduját hívja,
        a partnere a legkisebbet teszi (vagy dob). „mind”: amíg a védőknél adu van —
        a lapjaink fogyását a legvalószínűbb körszámmal (a kint lévő aduk fele,
        felfelé kerekítve) vesszük; a védőknél maradó adu ilyenkor 0 (ha a biztos
        aduütésünk elég)."""
        if not self.a.adu:
            return st
        mind = korok == "mind"
        n = -(-self.kint_adu_db // 2) if mind else min(int(korok), self.kint_adu_db)
        adu = self.a.adu
        for _ in range(n):
            T = max(dict(st.kezek), key=lambda k: sum(1 for l in st.kez(k) if l.szin == adu))
            P = kovetkezo_ules(T, 2)
            t_adu = sorted((l for l in st.kez(T) if l.szin == adu), key=lambda l: l.rang)
            p_adu = sorted((l for l in st.kez(P) if l.szin == adu), key=lambda l: l.rang)
            if not t_adu:
                break
            hivo = st.soron
            if mind and hivo == T and p_adu and p_adu[-1].rang > self.kint_adu_max \
                    and t_adu[0].rang < self.kint_adu_max:
                # deblokkolás: a rövid kéz nagy aduja előbb (kicsit alá)
                lapok, nyero = {T: t_adu[0], P: p_adu[-1]}, P
            elif hivo == P and p_adu:
                lapok, nyero = {P: p_adu[0], T: t_adu[-1]}, T     # vissza a hosszú kézbe
            elif hivo == T:
                lapok, nyero = {T: t_adu[-1], P: self._kovet(st, P, adu, self._foglalt(-1, 0))}, T
            else:
                break
            if self.ut is not None:
                self.ut.append(("adu", hivo, dict(lapok)))
            st = self._tesz(st, lapok, adu, nyero)
        if mind:
            if self.ut is not None:
                self.ut.append(("adu_vegig", hivo if n else None))
            st = replace(st, kiaduzva=True)
        return st

    def _atmenet(self, st: Allapot, cel: str, foglalt: set[Lap]) -> tuple | None:
        """Átmenet a `cel` kézbe: (szín, a hívó lapja, a cél lapja) vagy None."""
        jelolt = []
        for sz in SZINEK:
            kint = self.a.kint_szin(sz)
            kint_max = kint[0].rang if kint else 0
            hivo_lapok = sorted((l for l in st.kez(st.soron) if l.szin == sz), key=lambda l: l.rang)
            if not hivo_lapok:
                continue
            for c in sorted((l for l in st.kez(cel) if l.szin == sz), key=lambda l: l.rang):
                if c in foglalt or c.rang < kint_max or c.rang < hivo_lapok[0].rang:
                    continue
                jelolt.append(((sz == self.a.adu, c.rang), sz, hivo_lapok[0], c))
                break
        if not jelolt:
            return None
        _, sz, h, c = min(jelolt, key=lambda x: x[0])
        return sz, h, c

    def _alairas(self, e: Eset, st: Allapot) -> tuple:
        """A megfigyelés: színenként a védők látott hossza (min(hossz, körök)),
        a releváns figurák közül a már leesettek helye, és a tartalék."""
        ki = []
        for sz, r in st.korok:
            if r <= 0:
                continue
            ki.append((sz,) + tuple(min(e.o.kezhossz(v, sz), r) for v in self.vedok))
        les = tuple(sorted((str(l), k) for l, k in e.o.birtokos.items()
                           if e.o.kezhossz(k, l.szin) <= st.kor(l.szin)))
        return tuple(ki), les, e.tartalek, e.megfigyelt

    # -- a rekurzió --
    def futtat(self, esetek: list[Eset], ti: int, ri: int, st: Allapot) -> float:
        if not esetek:
            return 0.0
        lepesek = self.terv.lepesek
        if ti >= len(lepesek):
            if self.ut is not None:
                self.ut.append(("kudarc",))
            return 0.0
        p = lepesek[ti]
        if p.sema.fajta == "elemzo":
            return self._elemzos(esetek, ti, st)
        if ri >= len(p.korok):
            ok, tovabb = 0.0, []
            for e in esetek:
                if self.siker(p, e.o):
                    h = e.hiany - p.sema.hozam
                    if h <= 0 and not self._lezaras(e, st):
                        if self.ut is not None:
                            self.ut.append(("kudarc",))
                        continue                  # a maradék begyűjtése közben ellopnak
                    if h <= 0:
                        ok += e.w
                        if self.ut is not None:
                            self.ut.append(("siker", p.rovid))
                        continue
                    tovabb.append(replace(e, hiany=h))
                else:
                    tovabb.append(e)
            return ok + self.futtat(tovabb, ti + 1, 0, st)
        kor = p.korok[ri]
        extra = 0.0
        if kor.csak_ha_siker:
            nem = [e for e in esetek if not self.siker(p, e.o)]
            esetek = [e for e in esetek if self.siker(p, e.o)]
            extra = self.futtat(nem, ti + 1, 0, st)
            if not esetek:
                return extra
        if all(k.begyujtes for k in p.korok[ri:]):
            h = self._halaszt(st, ti, ri)
            if h is not None:                 # BEGYUJTES: a kiaduzás utánra
                st_h, kapacitas = h
                # csak ott, ahol a kiaduzó kéz aduja elég a védőknél maradt adukhoz
                jo = [e for e in esetek if max(self.adu_maradek(e.o, x, st) for x in self.vedok) <= kapacitas]
                rossz = [e for e in esetek if e not in jo]
                if self.naplo is not None:
                    self.naplo.append(f"begyűjtés halasztva ({p.rovid})")
                if self.ut is not None and jo:
                    self.ut.append(("halaszt",))
                ertek = self.futtat(jo, ti, len(p.korok), st_h)
                if not rossz:
                    return extra + ertek
                extra += ertek
                esetek = rossz
        van_kovetkezo = ti + 1 < len(lepesek)
        elo = self._elokeszit(esetek, ti, ri, st)
        if elo is None:                       # a kör nem játszható (nincs átmenet)
            return extra + (self.futtat(esetek, ti + 1, 0, st) if van_kovetkezo else 0.0)
        esetek, st, hivo, nyero = elo
        if (ri > 0 or kor.csak_ha_siker) and van_kovetkezo:
            # E5: megfigyelésenként folytatás vagy váltás a következő technikára
            csoport: dict = {}
            for e in esetek:
                csoport.setdefault(self._alairas(e, st), []).append(e)
            ossz = 0.0
            for alairas, cs in csoport.items():
                kulcs = (ti, ri, st, alairas)
                if self.politika_rogzitett is not None:
                    d = self.politika_rogzitett.get(kulcs, "tovabb")
                    ossz += (self.kor(cs, ti, ri, st, hivo, nyero) if d == "tovabb"
                             else self.futtat(cs, ti + 1, 0, st))
                    continue
                tovabb = self.kor(cs, ti, ri, st, hivo, nyero)
                valt = self.futtat(cs, ti + 1, 0, st)
                self.politika[kulcs] = "valt" if valt > tovabb else "tovabb"
                ossz += max(tovabb, valt)
            return extra + ossz
        return extra + self.kor(esetek, ti, ri, st, hivo, nyero)

    # -- az elemzős technika (SZINKEZELES): az egyszínű elemző kezelése --
    def _szk_futas(self, p: Peldany, st: Allapot):
        """Az elemző a mostani lapjainkkal, átmenetekkel és hívással; gyorsítótárral."""
        from .tervszinkezeles import Elemzo, Feladat, RANG
        sz = p.szin
        X, Y = self.a.felvevo, self.a.asztal
        rang = lambda ls: frozenset(l.rang for l in ls)
        xr = rang(l for l in st.kez(X) if l.szin == sz)
        yr = rang(l for l in st.kez(Y) if l.szin == sz)
        kint = rang(l for l in self.a.kint if l.szin == sz)
        foglalt = self._foglalt(self.terv.lepesek.index(p), 0) - p.hasznal
        bx = self._atmenetek(st, X, sz, foglalt)
        by = self._atmenetek(st, Y, sz, foglalt)
        kulcs = (sz, xr, yr, p.szerepek["k"], p.szerepek["m"], p.szerepek.get("lop_x", 0),
                 p.szerepek.get("lop_y", 0), bx, by, "X" if st.soron == X else "Y")
        tar = SZK_TAR.get(kulcs)
        if tar is None:
            f = Feladat(xr, yr, kint, self.a.hatra, self.a.hatra,
                        p.szerepek.get("lop_x", 0), p.szerepek.get("lop_y", 0), bx, by,
                        "X" if st.soron == X else "Y", sz == self.a.adu)
            e = Elemzo(f)
            kim = e.kimenetek(p.szerepek["k"], p.szerepek["m"])
            tar = (e.tart, kim)
            SZK_TAR[kulcs] = tar
        return tar

    def _atmenetek(self, st: Allapot, kez: str, sz: str, foglalt: set) -> int:
        """Átmenetek a kézbe más színben: a nyerő lapjai (a kint lévő legnagyobbnál
        nagyobb), amelyek alá a partner hívni tud; a terv más lapjai nem."""
        p = kovetkezo_ules(kez, 2)
        db = 0
        for l in st.kez(kez):
            if l.szin == sz or l in foglalt:
                continue
            kint = self.a.kint_szin(l.szin)
            if kint and l.rang < kint[0].rang:
                continue
            if any(x.szin == l.szin and x.rang < l.rang for x in st.kez(p)):
                db += 1
        return db

    def _szk_eloszlas(self, p: Peldany, o: Osztaly, tart, kim) -> dict:
        """Az osztályra: (hozam, költség, lopás, átm. X, átm. Y) → arány. Az
        osztályon belül a szín tartásai egyformán valószínűek (rögzített hossz)."""
        kulcs = (id(kim), o.azon)
        if kulcs in self._szk_cache:
            return self._szk_cache[kulcs]
        sz = p.szin
        v1 = self.vedok[0]
        hossz = o.kezhossz(v1, sz)
        rel = {l.rang: o.birtokos[l] for l in o.birtokos if l.szin == sz}
        biztos = self.h.biztos.get(sz, 0)
        db: dict = {}
        n = 0
        for i, (t1, t2, _) in enumerate(tart):
            if len(t1) != hossz:
                continue
            if any((r in t1) != (k == v1) for r, k in rel.items()):
                continue
            km = kim[i]
            kul = (max(0, km.utes - biztos), km.vesztes, km.lopas, km.atm_x, km.atm_y)
            db[kul] = db.get(kul, 0) + 1
            n += 1
        ki = {k: v / n for k, v in db.items()} if n else {}
        self._szk_cache[kulcs] = ki
        return ki

    def _elemzos(self, esetek: list[Eset], ti: int, st: Allapot) -> float:
        p = self.terv.lepesek[ti]
        tart, kim = self._szk_futas(p, st)
        sz = p.szin
        # az állapot utána: a szín lapjaink elfogynak; a lopások és az átmenetek
        # (a legrosszabb tartás szerint) a legkisebb adut / a legolcsóbb nyerőt viszik
        kezek = {k: set(v) for k, v in st.kezek}
        max_lop = max((k.lopas for k in kim.values()), default=0)
        max_ax = max((k.atm_x for k in kim.values()), default=0)
        max_ay = max((k.atm_y for k in kim.values()), default=0)
        for k in kezek:
            kezek[k] = {l for l in kezek[k] if l.szin != sz}
        if max_lop and self.a.adu:
            lopo = self.a.felvevo if p.szerepek.get("lop_x") else self.a.asztal
            adu = sorted((l for l in kezek[lopo] if l.szin == self.a.adu), key=lambda l: l.rang)
            kezek[lopo] -= set(adu[:max_lop])
        foglalt = self._foglalt(ti, 0) - p.hasznal
        for kez, db in ((self.a.felvevo, max_ax), (self.a.asztal, max_ay)):
            jelolt = sorted((l for l in kezek[kez] if l.szin != sz and l not in foglalt),
                            key=lambda l: (l.szin == self.a.adu, l.rang))
            nyerok = [l for l in jelolt if not self.a.kint_szin(l.szin)
                      or l.rang > self.a.kint_szin(l.szin)[0].rang]
            kezek[kez] -= set(nyerok[:db])
        korok = dict(st.korok)
        korok[sz] = korok.get(sz, 0) + max((k.utes + k.vesztes + k.lopas for k in kim.values()), default=0)
        st2 = Allapot(tuple(sorted((k, frozenset(v)) for k, v in kezek.items())),
                      tuple(sorted(korok.items())), self.a.felvevo,
                      st.kiaduzva or sz == self.a.adu)
        ok, tovabb = 0.0, []
        for e in esetek:
            for (hozam, koltseg, lop, ax, ay), arany in self._szk_eloszlas(p, e.o, tart, kim).items():
                # ELLOPÁS a mellékszín köreire, amíg a védőknél adu van (durva közelítés:
                # ha egy védő a kör előtt színhiányos és van adója, a hozam elvész)
                if self.kockazat and self.a.adu and sz != self.a.adu and not st.kiaduzva:
                    korszam = hozam + self.h.biztos.get(sz, 0) + koltseg + lop
                    if any(e.o.kezhossz(x, sz) < korszam and self.adu_maradek(e.o, x, st) > 0
                           for x in self.vedok):
                        hozam, koltseg = 0, koltseg + 1
                if koltseg > e.tartalek:
                    if self.ut is not None:
                        self.ut.append(("kudarc",))
                    continue
                uj = Eset(e.o, e.w * arany, e.tartalek - koltseg, e.hiany - hozam,
                          e.megfigyelt + ((ti, hozam, koltseg),))
                if uj.hiany <= 0:
                    if self._lezaras(uj, st2):
                        ok += uj.w
                        if self.ut is not None:
                            self.ut.append(("siker", p.rovid))
                    continue
                tovabb.append(uj)
        if self.naplo is not None:
            self.naplo.append(f"színkezelés {p.rovid}")
        return ok + self.futtat(tovabb, ti + 1, 0, st2)

    def _lezaras(self, e: Eset, st: Allapot) -> bool:
        """A cél megvan; a maradék (biztos ütések) begyűjthető-e úgy, hogy a védők
        maradék aduját előbb lehúzzuk? A kiaduzó kézbe vissza kell jutni: ha hívásban
        van, vagy lopással jut be, rendben; ha csak egy nyerő színnel, arra az
        ELLOPÁS vonatkozik. Végül a kiaduzó kéz nagy adói elegendők-e."""
        adu = self.a.adu
        if not adu or st.kiaduzva or not self.kockazat:
            return True
        marad = max(self.adu_maradek(e.o, x, st) for x in self.vedok)
        if marad <= 0:
            return True
        T = max(dict(st.kezek), key=lambda k: sum(1 for l in st.kez(k) if l.szin == adu))
        magas = sum(1 for l in st.kez(T) if l.szin == adu and l.rang > self.kint_adu_max)
        if st.soron == T:
            return magas >= marad
        if any(sz != adu and any(l.szin == sz for l in st.kez(st.soron))
               and not any(l.szin == sz for l in st.kez(T)) for sz in SZINEK):
            return magas - 1 >= marad              # lopással jut be (magasan)
        for sz in SZINEK:
            if sz == adu or not any(l.szin == sz for l in st.kez(st.soron)):
                continue
            kint = self.a.kint_szin(sz)
            if not any(l.szin == sz and (not kint or l.rang > kint[0].rang) for l in st.kez(T)):
                continue
            r = st.kor(sz) + 1
            if all(e.o.kezhossz(x, sz) >= r or self.adu_maradek(e.o, x, st) <= 0 for x in self.vedok):
                return magas >= marad
        return False

    def _halaszt(self, st: Allapot, ti: int, ri: int) -> tuple[Allapot, int] | None:
        """BEGYUJTES: a technika hátralévő (begyűjtő) köreit a kiaduzás utánra
        halaszthatjuk-e? Vissza: az állapot a kiaduzás után (a begyűjtés ezután
        kockázat nélkül) és a kiaduzó kéz adóinak száma (ennyi kört bír), vagy None
        (most kell játszani, a kockázatával)."""
        p = self.terv.lepesek[ti]
        adu = self.a.adu
        foglalt = self._foglalt(ti, ri)
        kapacitas = 99
        if adu and not st.kiaduzva:
            T = max(dict(st.kezek), key=lambda k: sum(1 for l in st.kez(k) if l.szin == adu))
            if not any(l.szin == adu for l in st.kez(T)):
                return None
            if st.soron != T:
                # átmenet a kiaduzó kézbe lopással: a hívó kéz színéből T színhiányos
                lopas = next((sz for sz in SZINEK if sz != adu
                              and any(l.szin == sz for l in st.kez(st.soron))
                              and not any(l.szin == sz for l in st.kez(T))), None)
                if lopas is None:
                    return None
                adui = sorted((l for l in st.kez(T) if l.szin == adu), key=lambda l: l.rang)
                magas = [l for l in adui if l.rang > self.kint_adu_max]
                lapok = {st.soron: self._kicsi(st, st.soron, lopas, foglalt),
                         T: (magas or adui)[0]}          # magasan lop, hogy ne lophassák felül
                st = self._tesz(st, lapok, lopas, T)
            # ennyi adukört bír: a kiaduzó kéz minden kint lévőnél nagyobb adói
            kapacitas = sum(1 for l in st.kez(T) if l.szin == adu and l.rang > self.kint_adu_max)
            # a hátralévő adukörök (a lapjaink fogyása: a legvalószínűbb körszámig)
            for _ in range(max(0, -(-self.kint_adu_db // 2) - st.kor(adu))):
                sajat = sorted((l for l in st.kez(T) if l.szin == adu), key=lambda l: -l.rang)
                if not sajat:
                    return None
                pt = kovetkezo_ules(T, 2)
                st = self._tesz(st, {T: sajat[0], pt: self._kovet(st, pt, adu, foglalt)}, adu, T)
            st = replace(st, kiaduzva=True)
        # a begyűjtő lapok keze elérhető-e?
        for k in p.korok[ri:]:
            if k.lap is None:
                continue
            X = self.a.keze(k.lap)
            if X == st.soron or any(l.szin == k.lap.szin for l in st.kez(st.soron)):
                continue
            if self._atmenet(st, X, foglalt - {k.lap}) is None:
                return None
        return st, kapacitas

    def _elokeszit(self, esetek: list[Eset], ti: int, ri: int, st: Allapot):
        """Ki hívja a kört, ki üt; ha a hívó kéz nincs hívásban: átmenet (ELLOPÁS-sal).
        Vissza: (esetek, állapot, hívó, nyerő) vagy None."""
        p = self.terv.lepesek[ti]
        k: Kor = p.korok[ri]
        sz = k.szin
        foglalt = self._foglalt(ti, ri)
        if k.fajta == "lehiv":
            gazda = self.a.keze(k.lap) if k.lap is not None else None
            if gazda is None or k.lap not in st.kez(gazda):
                return None
            if st.soron == gazda or any(l.szin == sz for l in st.kez(st.soron)):
                hivo = st.soron
            else:
                hivo = gazda
            nyero = gazda
        elif k.fajta == "impassz":
            hivo, nyero = k.hivo, self.a.keze(k.lap)
        elif k.fajta == "lop":
            hivo, nyero = k.hivo, k.lopo
        else:
            return None
        if st.soron != hivo:
            atm = self._atmenet(st, hivo, foglalt)
            if atm is None:
                return None
            asz, hl, cl = atm
            lapok = {st.soron: hl, hivo: cl}
            tovabb = []
            for e in esetek:
                if self._ellopjak(e, st, asz, st.soron, lapok, None):
                    if e.tartalek <= 0:
                        continue
                    e = replace(e, tartalek=e.tartalek - 1)
                tovabb.append(e)
            if self.ut is not None:
                self.ut.append(("kor", st.soron, dict(lapok)))
            st = self._tesz(st, lapok, asz, hivo)
            esetek = tovabb
            if self.naplo is not None:
                self.naplo.append(f"átmenet: {hl}→{cl}")
        return esetek, st, hivo, nyero

    def kor(self, esetek: list[Eset], ti: int, ri: int, st: Allapot, hivo: str, nyero: str) -> float:
        p = self.terv.lepesek[ti]
        k: Kor = p.korok[ri]
        sz = k.szin
        foglalt = self._foglalt(ti, ri)
        # a kör lapjai
        partner = kovetkezo_ules(hivo, 2)
        if k.fajta == "lehiv":
            if hivo == nyero:
                lapok = {hivo: k.lap, partner: self._kovet(st, partner, sz, foglalt - {k.lap})}
            else:
                lapok = {hivo: self._kicsi(st, hivo, sz, foglalt), nyero: k.lap}
        elif k.fajta == "impassz":
            if hivo == nyero:                     # átengedés: a sorozat lapját hívjuk
                lapok = {hivo: k.lap, partner: self._kovet(st, partner, sz, foglalt)}
            else:                                 # villa felé: kicsi, a villa alsó lapja
                lapok = {hivo: self._kicsi(st, hivo, sz, foglalt), nyero: k.lap}
        else:                                     # lop
            lapok = {hivo: self._kicsi(st, hivo, sz, foglalt),
                     k.lopo: self._kovet(st, k.lopo, sz, foglalt, lop=True)}
        if any(v is None for v in lapok.values()):
            return 0.0
        tovabb = []
        for e in esetek:
            vesztett = 0
            if self._ellopjak(e, st, sz, hivo, lapok, k.lopo if k.fajta == "lop" else None):
                vesztett = 1
            elif k.fajta == "impassz" and not self.siker(p, e.o):
                vesztett = p.sema.kudarc_koltseg
            if vesztett:
                if e.tartalek < vesztett:
                    continue
                e = replace(e, tartalek=e.tartalek - vesztett)
            tovabb.append(e)
        if self.ut is not None:
            self.ut.append(("kor", hivo, dict(lapok)))
            if not tovabb:
                self.ut.append(("kudarc",))
        st2 = self._tesz(st, lapok, sz, nyero)
        if self.naplo is not None:
            self.naplo.append(f"{k.fajta} {sz}: " + " ".join(f"{u}:{l}" for u, l in lapok.items()))
        return self.futtat(tovabb, ti, ri + 1, st2)


def szinkezeles_peldanyok(allas: Allas, helyzet: Helyzet, sema) -> list[Peldany]:
    """A SZINKEZELES (elemzős) technika példányai: színenként a célok (k ütés,
    legfeljebb m vesztés, lopással), amelyeknek van esélye; az azonos kimenetet
    adó célok közül csak az első."""
    from .tervszinkezeles import Elemzo, Feladat
    from collections import Counter
    ki = []
    X, Y = allas.felvevo, allas.asztal
    for sz in SZINEK:
        xs = [l for l in allas.kezek[X] if l.szin == sz]
        ys = [l for l in allas.kezek[Y] if l.szin == sz]
        if not xs and not ys:
            continue
        b = helyzet.biztos.get(sz, 0)
        kmax = min(max(len(xs), len(ys)), b + helyzet.hiany)
        if kmax <= b:
            continue
        valt = [(0, 0)]
        if allas.adu and sz != allas.adu:
            for kez, sajat, masik, hely in ((X, xs, ys, 0), (Y, ys, xs, 1)):
                adu = sum(1 for l in allas.kezek[kez] if l.szin == allas.adu)
                if len(sajat) < len(masik) and adu:
                    r = min(adu, len(masik) - len(sajat))
                    valt.append((r, 0) if hely == 0 else (0, r))
        kint = frozenset(l.rang for l in allas.kint if l.szin == sz)
        latott = set()
        for lx, ly in valt:
            e = Elemzo(Feladat(frozenset(l.rang for l in xs), frozenset(l.rang for l in ys), kint,
                               allas.hatra, allas.hatra, lx, ly, adu=(sz == allas.adu)))
            for k in range(b + 1, kmax + 1):
                for m in range(0, helyzet.tartalek + 1):
                    if e.megold(k, m)[0] <= 0:
                        continue
                    kim = e.kimenetek(k, m)
                    elo = tuple(sorted(Counter((km.utes, km.vesztes, km.lopas) for km in kim.values()).items()))
                    if elo in latott:
                        continue
                    latott.add(elo)
                    lapok = set(xs) | set(ys)
                    ki.append(Peldany(sema, sz, {"k": k, "m": m, "lop_x": lx, "lop_y": ly},
                                      [], lapok, lapok, set()))
    return ki


# --- 4. A tervező ---------------------------------------------------------------------------

@dataclass
class TervErtek:
    terv: Terv                 # a kockázattal legjobb kiaduzással
    elvi: float                # csak a sikerfeltétel (a legjobb kiaduzással)
    kockazattal: float         # az általános szabályokkal (ELLOPÁS, ÁTMENET, BEGYŰJTÉS)
    elvi_kiaduzas: int = 0
    politika: dict = field(default_factory=dict)   # a megfigyelésen múló döntések


def kezdo_allapot(allas: Allas) -> Allapot:
    return Allapot(tuple(sorted((k, frozenset(v)) for k, v in allas.kezek.items())), (), allas.soron)


def tervez(allas: Allas, korlatok: list[Korlat] = (), kiaduzas_valasztek=None,
           feltevesbol: bool = False) -> tuple[Helyzet, list[TervErtek]]:
    helyzet = helyzetelemzes(allas)
    technikak = technikak_betoltese()
    strategiak, szabalyok = strategiak_betoltese()
    if kiaduzas_valasztek is None:
        kiaduzas_valasztek = next((s.get("valasztek") for s in szabalyok if s.get("szabaly") == "KIADUZAS"),
                                  ["mind", 0])
    pld = peldanyok(allas, technikak)
    if "SZINKEZELES" in technikak:
        pld += szinkezeles_peldanyok(allas, helyzet, technikak["SZINKEZELES"])
    relevans = {l for p in pld for l in p.relevans}
    ures = {}
    kint_db = len(allas.kint)
    # a védők kint lévő lapjainak száma: a hátralévő ütések (ütés elején)
    ures = {v: allas.hatra for v in allas.vedok}
    assert kint_db == 2 * allas.hatra, "a tervező ütés elején dolgozik"
    # SZABAD_HELYEK: a hosszakból következő súlyozás (pl. az impassz esélye) csak
    # ismert (megfigyelt vagy bizonyított) hosszkülönbségből; a feltételezett hossz
    # (a licitből) a szabály engedélyével
    szh = next((s for s in szabalyok if s.get("szabaly") == "SZABAD_HELYEK"), {})
    engedett = set(szh.get("tudas", ["megfigyelt", "bizonyitott"]))
    if feltevesbol:
        engedett.add("feltetelezett")
    korlatok = [k for k in korlatok if k.tudas in engedett]
    oszt = osztalyok(allas.kint, ures, relevans, list(korlatok))
    W = sum(o.suly for o in oszt)
    kezdo = kezdo_allapot(allas)
    ki = []
    for strat, sor in jeloltek(helyzet, pld, strategiak):
        # minden kiaduzás-változat; a terv „szándék szerinti” változatai azok, amelyekben
        # az elvi esélye a legnagyobb (pl. a lopásos kimagasításhoz meg kell őrizni az
        # átmenetet) — ezek közül a kockázattal legjobb a terv értéke
        valtozatok = []
        adu_szk = any(p.sema.fajta == "elemzo" and p.szin == allas.adu for p in sor)
        for kd in ([0] if adu_szk else kiaduzas_valasztek):     # az adu kezelése maga a technika
            n = "mind" if kd == "mind" else int(kd)
            terv = Terv(strat, sor, 13 if n == "mind" else n)
            ertekek, pol = [], {}
            for kock in (False, True):
                ert = Ertekelo(helyzet, terv, kockazat=kock)
                st = ert.kiaduzas(kezdo, n)
                esetek = [Eset(o, o.suly, helyzet.tartalek, helyzet.hiany) for o in oszt]
                ertekek.append(ert.futtat(esetek, 0, 0, st) / W)
                pol = ert.politika
            valtozatok.append((terv, *ertekek, pol))
        elvi = max(v[1] for v in valtozatok)
        terv, e_, k_, pol = max((v for v in valtozatok if v[1] >= elvi - 1e-9), key=lambda v: v[2])
        ki.append(TervErtek(terv, elvi, k_, terv.kiaduzas, pol))
    ki.sort(key=lambda x: (-x.kockazattal, -x.elvi))
    return helyzet, ki
