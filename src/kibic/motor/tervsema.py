"""
Tervsémák (2026-10-31, Felvevő tervjáték): a technika- és stratégiasémák
betöltése, a sémák kifejezéseinek értelmezése, és a technikák hozzárendelése
a látott lapokhoz.

A bridzstudás az adatban van (`rendszerek/tervek/sema/*.yaml`); ez a modul a
nyelv: a LÁTOTT fogalmak (a szerepek és az alkalmazhatóság számolásához) és a
REJTETT predikátumok (a `siker` feltételhez — ezeket csak a valószínűség-számoló
értékeli, egy elosztás-osztályon; lásd `tervszamolo.py`).

A kifejezésnyelv a Python kifejezések szűk részhalmaza (nevek, számok, listák,
függvényhívás, összehasonlítás, and/or/not, + és −). Nincs attribútum-elérés,
nincs indexelés, nincs lambda — csak a megnevezett fogalmak hívhatók.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass, field
from pathlib import Path

from ..domain import SZINEK, Lap, kovetkezo_ules, vonal

SEMA_KONYVTAR = Path(__file__).resolve().parents[3] / "rendszerek" / "tervek" / "sema"


# --- 1. A kifejezésnyelv ---------------------------------------------------------

class KifejezesHiba(ValueError):
    pass


_OSSZEHASONLITAS = {
    ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
}


def _ertekel(csomopont, kornyezet: dict):
    if isinstance(csomopont, ast.Expression):
        return _ertekel(csomopont.body, kornyezet)
    if isinstance(csomopont, ast.Constant):
        return csomopont.value
    if isinstance(csomopont, ast.Name):
        if csomopont.id not in kornyezet:
            raise KifejezesHiba(f"ismeretlen név: {csomopont.id}")
        return kornyezet[csomopont.id]
    if isinstance(csomopont, ast.List):
        return [_ertekel(e, kornyezet) for e in csomopont.elts]
    if isinstance(csomopont, ast.BoolOp):
        if isinstance(csomopont.op, ast.And):
            v = True
            for e in csomopont.values:
                v = _ertekel(e, kornyezet)
                if not v:
                    return v
            return v
        v = False
        for e in csomopont.values:
            v = _ertekel(e, kornyezet)
            if v:
                return v
        return v
    if isinstance(csomopont, ast.UnaryOp) and isinstance(csomopont.op, ast.Not):
        return not _ertekel(csomopont.operand, kornyezet)
    if isinstance(csomopont, ast.UnaryOp) and isinstance(csomopont.op, ast.USub):
        return -_ertekel(csomopont.operand, kornyezet)
    if isinstance(csomopont, ast.BinOp) and isinstance(csomopont.op, (ast.Add, ast.Sub)):
        a, b = _ertekel(csomopont.left, kornyezet), _ertekel(csomopont.right, kornyezet)
        return a + b if isinstance(csomopont.op, ast.Add) else a - b
    if isinstance(csomopont, ast.Compare):
        bal = _ertekel(csomopont.left, kornyezet)
        for op, jobb_ in zip(csomopont.ops, csomopont.comparators):
            jobb = _ertekel(jobb_, kornyezet)
            if bal is None or jobb is None:
                return False
            if not _OSSZEHASONLITAS[type(op)](bal, jobb):
                return False
            bal = jobb
        return True
    if isinstance(csomopont, ast.Call) and isinstance(csomopont.func, ast.Name):
        fv = kornyezet.get(csomopont.func.id)
        if not callable(fv):
            raise KifejezesHiba(f"ismeretlen fogalom: {csomopont.func.id}")
        return fv(*[_ertekel(a, kornyezet) for a in csomopont.args])
    raise KifejezesHiba(f"nem megengedett kifejezés: {ast.dump(csomopont)[:80]}")


_FORDITOTT: dict[str, ast.Expression] = {}


def kifejezes(szoveg, kornyezet: dict):
    """Egy séma-kifejezés értéke a környezetben (szerepek + fogalmak)."""
    if not isinstance(szoveg, str):
        return szoveg
    fa = _FORDITOTT.get(szoveg)
    if fa is None:
        try:
            fa = ast.parse(szoveg, mode="eval")
        except SyntaxError as e:
            raise KifejezesHiba(f"{szoveg!r}: {e}") from e
        _FORDITOTT[szoveg] = fa
    return _ertekel(fa, kornyezet)


# --- 2. A látott állás és a fogalmak ------------------------------------------------

@dataclass
class Allas:
    """Amit a felvevő lát: a két kéz mostani lapjai, a kint lévő (nem látott) lapok,
    a felvétel és a kívánt ütésszám."""
    felvevo: str
    adu: str | None
    kezek: dict[str, set[Lap]]           # a felvevő és az asztal mostani lapjai
    kint: set[Lap]                       # a védők még le nem játszott lapjai
    cel: int                             # a hátralévő ütésekből ennyi kell
    hatra: int                           # hátralévő ütések
    soron: str                           # ki hív most (a mi oldalunk)

    @property
    def asztal(self) -> str:
        return kovetkezo_ules(self.felvevo, 2)

    def szin(self, kez: str, sz: str) -> list[Lap]:
        return sorted((l for l in self.kezek[kez] if l.szin == sz), key=lambda l: -l.rang)

    def mi_szin(self, sz: str) -> list[Lap]:
        return sorted((l for k in self.kezek.values() for l in k if l.szin == sz), key=lambda l: -l.rang)

    def kint_szin(self, sz: str) -> list[Lap]:
        return sorted((l for l in self.kint if l.szin == sz), key=lambda l: -l.rang)

    def keze(self, lap: Lap) -> str | None:
        for k, lapok in self.kezek.items():
            if lap in lapok:
                return k
        return None

    def biztos_utesek(self, sz: str) -> int:
        """A felső lapokból biztos ütések egy színben: a kint lévő legnagyobbnál
        nagyobb lapjaink száma, legfeljebb a hosszabb kéz hossza."""
        kint = self.kint_szin(sz)
        felso = [l for l in self.mi_szin(sz) if not kint or l.rang > kint[0].rang]
        hosszabb = max(len(self.szin(k, sz)) for k in self.kezek)
        return min(len(felso), hosszabb)


def fogalmak(allas: Allas) -> dict:
    """A látott lapokból számolt fogalmak (a szerepek és az alkalmazhatóság nyelve)."""
    a = allas

    def legnagyobb_kint(sz):
        k = a.kint_szin(sz)
        return k[0] if k else None

    def felettunk(sz, f):
        if f is None:
            return []
        return [l for l in a.mi_szin(sz) if l.rang > f.rang]

    def felettunk_kezben(kez, sz, f):
        if f is None or kez is None:
            return []
        return [l for l in a.szin(kez, sz) if l.rang > f.rang]

    def kozvetlen_alatta(sz, f):
        """A lapunk közvetlenül F alatt (köztük nincs kint lévő lap)."""
        if f is None:
            return None
        alatta = [l for l in a.mi_szin(sz) if l.rang < f.rang]
        if not alatta:
            return None
        m = alatta[0]
        if any(m.rang < l.rang < f.rang for l in a.kint_szin(sz)):
            return None
        return m

    def legnagyobb_alatta_kezben(kez, sz, f):
        if f is None or kez is None:
            return None
        alatta = [l for l in a.szin(kez, sz) if l.rang < f.rang]
        if not alatta:
            return None
        m = alatta[0]
        if any(m.rang < l.rang < f.rang for l in a.kint_szin(sz)):
            return None
        return m

    def sorozat_lefele(v):
        """V és alatta ugyanabban a kézben a lapjaink, amíg nincs köztük kint lévő lap."""
        if v is None:
            return []
        sor = [v]
        for l in a.szin(a.keze(v), v.szin):
            if l.rang >= sor[-1].rang:
                continue
            if any(l.rang < x.rang < sor[-1].rang for x in a.kint_szin(v.szin)):
                break
            sor.append(l)
        return sor

    def rovidebb_adus_kez(sz):
        if not a.adu:
            return None
        jelolt = [k for k in a.kezek if a.szin(k, a.adu)]
        if len(jelolt) < 2:
            return jelolt[0] if jelolt else None
        k1, k2 = jelolt
        h1, h2 = len(a.szin(k1, sz)), len(a.szin(k2, sz))
        if h1 == h2:
            return None
        return k1 if h1 < h2 else k2

    return {
        "legnagyobb_kint": legnagyobb_kint,
        "felettunk": felettunk,
        "felettunk_kezben": felettunk_kezben,
        "kozvetlen_alatta": kozvetlen_alatta,
        "legnagyobb_alatta_kezben": legnagyobb_alatta_kezben,
        "sorozat_lefele": sorozat_lefele,
        "rovidebb_adus_kez": rovidebb_adus_kez,
        "keze": lambda l: a.keze(l) if l is not None else None,
        "partner": lambda k: kovetkezo_ules(k, 2) if k else None,
        "bal": lambda k: kovetkezo_ules(k, 1) if k else None,
        "jobb": lambda k: kovetkezo_ules(k, 3) if k else None,
        "hossz": lambda x: len(x) if x is not None else 0,
        "kezhossz": lambda k, sz: len(a.szin(k, sz)) if k else 0,
        "adu_kezben": lambda k: len(a.szin(k, a.adu)) if (k and a.adu) else 0,
        "nem_adu": lambda sz: sz != a.adu,
        "van": lambda x: x is not None and x != [],
        "elso": lambda xs: xs[:1],
        "tobbi": lambda xs: xs[1:],
    }


# --- 3. A sémák betöltése -------------------------------------------------------------

@dataclass
class TechnikaSema:
    azon: str
    nev: str
    szerepek: dict
    alkalmazhato: list
    korok: list
    siker: str
    kudarc_koltseg: int
    hozam: int
    hasznal: list
    elfogyaszt: list


def _yaml(ut: Path):
    import yaml
    return yaml.safe_load(ut.read_text(encoding="utf-8")) or []


def technikak_betoltese(konyvtar: Path = SEMA_KONYVTAR) -> dict[str, TechnikaSema]:
    """A technikasémák (öröklés: `valtozat` + `alap` + `felulir`)."""
    nyers: dict[str, dict] = {}
    for sor in _yaml(konyvtar / "technikak.yaml"):
        azon = sor.get("technika") or sor.get("valtozat")
        nyers[azon] = sor

    def kesz(azon: str) -> dict:
        s = nyers[azon]
        if "alap" not in s:
            return dict(s)
        d = copy.deepcopy(kesz(s["alap"]))
        for kulcs, ertek in s.items():
            if kulcs in ("alap", "valtozat", "felulir"):
                continue
            d[kulcs] = ertek
        d.update(copy.deepcopy(s.get("felulir") or {}))
        return d

    ki = {}
    for azon in nyers:
        d = kesz(azon)
        ki[azon] = TechnikaSema(azon, d.get("nev", azon), d.get("szerepek") or {},
                                d.get("alkalmazhato") or [], d.get("korok") or [],
                                d.get("siker") or "False", int(d.get("kudarc_koltseg", 0)),
                                int(d.get("hozam", 1)), d.get("hasznal") or [],
                                d.get("elfogyaszt") or [])
    return ki


def strategiak_betoltese(konyvtar: Path = SEMA_KONYVTAR) -> tuple[dict, list]:
    sorok = _yaml(konyvtar / "strategiak.yaml")
    strat, szab = {}, []
    if isinstance(sorok, dict):
        sorok = [sorok]
    for sor in sorok:
        if "strategia" in sor:
            strat[sor["strategia"]] = sor
        elif "szabalyok" in sor:
            szab += sor["szabalyok"]
    return strat, szab


# --- 4. Példányok: a technika a konkrét lapokon ---------------------------------------

@dataclass
class Kor:
    """A kotta egy köre, a konkrét lapokkal."""
    fajta: str                 # lehiv / impassz / lop
    szin: str
    lap: Lap | None = None     # lehiv / impassz: a mi lapunk
    hivo: str | None = None    # impassz / lop: a hívó kéz
    lopo: str | None = None    # lop: a lopó kéz
    csak_ha_siker: bool = False
    begyujtes: bool = False    # a biztos nyerők lehívása (halasztható)


@dataclass
class Peldany:
    sema: TechnikaSema
    szin: str
    szerepek: dict
    korok: list[Kor]
    hasznal: set[Lap]
    elfogyaszt: set[Lap]
    relevans: set[Lap] = field(default_factory=set)   # a `siker`-ben szereplő kint lévő lapok

    @property
    def nev(self) -> str:
        return f"{self.sema.azon} {self.szin}"

    @property
    def rovid(self) -> str:
        r = {"EJTES": "ejtés", "IMPASSZ_VILLA": "impassz", "IMPASSZ_ATENGEDES": "impassz",
             "IMPASSZ_ATENGEDES_FELSO_ELOBB": "impassz (felső előbb)",
             "LOPASOS_KIMAGASITAS": "lopásos kimagasítás"}.get(self.sema.azon, self.sema.azon)
        return f"{'♠♥♦♣'['SHDC'.index(self.szin)]} {r}"

    def siker_kornyezet(self) -> dict:
        return dict(self.szerepek)


def _lapok(ertek) -> list[Lap]:
    if ertek is None:
        return []
    if isinstance(ertek, Lap):
        return [ertek]
    return [l for l in ertek if isinstance(l, Lap)]


def peldanyok(allas: Allas, technikak: dict[str, TechnikaSema]) -> list[Peldany]:
    """Minden technika minden színre, ahol az alkalmazhatósága igaz."""
    fog = fogalmak(allas)
    ki = []
    for sema in technikak.values():
        for sz in SZINEK:
            kor = dict(fog, SZ=sz)
            try:
                for nev, kif in sema.szerepek.items():
                    kor[nev] = kifejezes(kif, kor)
                if not all(kifejezes(f, kor) for f in sema.alkalmazhato):
                    continue
                korok = []
                for k in sema.korok:
                    db = int(kifejezes(str(k.get("ismetles", 1)), kor))
                    lapok = _lapok(kifejezes(k.get("lap"), kor)) if k.get("lap") else []
                    if k["fajta"] == "lehiv" and len(lapok) > 1:
                        # a rövidebb kéz lapjai előbb (deblokkolás)
                        lapok.sort(key=lambda l: (len(allas.szin(allas.keze(l), sz)), -l.rang))
                    for i in range(db):
                        korok.append(Kor(k["fajta"], sz, lap=lapok[i] if i < len(lapok) else None,
                                         hivo=kifejezes(k.get("hivo"), kor) if k.get("hivo") else None,
                                         lopo=kifejezes(k.get("lopo"), kor) if k.get("lopo") else None,
                                         csak_ha_siker=k.get("csak_ha") == "siker",
                                         begyujtes=bool(k.get("begyujtes"))))
                hasznal = {l for x in sema.hasznal for l in _lapok(kifejezes(x, kor))}
                elfogy = {l for x in sema.elfogyaszt for l in _lapok(kifejezes(x, kor))}
            except KifejezesHiba:
                raise
            except (TypeError, AttributeError):
                continue                       # a szerep nem értelmezhető ebben a színben
            szerepek = {n: kor[n] for n in sema.szerepek}
            relevans = {l for v in szerepek.values() for l in _lapok(v if isinstance(v, list) else [v])
                        if l in allas.kint}
            ki.append(Peldany(sema, sz, szerepek, korok, hasznal, elfogy, relevans))
    return ki
