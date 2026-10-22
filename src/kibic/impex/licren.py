"""
A LICREN (.lr) licitrendszer-formátum értelmezője.

A LICREN egy 2013-as magyar bridzsprogram formális rendszerleíró nyelve.
Szerencsés felfedezés: a licithelyzet-jelölése KARAKTERRE AZONOS a kibic
mintanyelv pároslicit alakjával (`1C-1D-1H-1S`), a feltételei pedig
lefordíthatók a kritérium-motorra.

A nyelv (a licren.hez súgófájl szerint):

    S,H,D,C     az adott szín hossza
    F           figurapont (HCP)
    P           pont (figurapont + elosztási pontok)
    i           indulóerő (belső függvény)
    K           kontroll
    j           játékütések száma × 10
    t           gyorsütések száma × 10
    b           'egyenletes': legalább két lap minden színben
    L1..L4      a leghosszabb..legrövidebb szín hossza
    f1..f4      az annyiadik rangú színben lévő figurapontok
    exxxx       konkrét elosztás (S-H-D-C sorrendben)
    axxxx       elosztás csökkenő hosszsorrendben
    vXY         1, ha nála van az XY lap (pl. vSA = pikk ász)
    @M,@A,@S,@O szkórhelyzet (mindkettő / egyik sem / mi / ők beliben)
    &, o        logikai ÉS, VAGY
    n(..)       negáció
    [x,y]       intervallumba esés
    >, <, =, +  összehasonlítás és összeadás

Fájlszerkezet:
    START
    <indítólicitek>
    !!
    <licithelyzet>
    <licit>:<feltétel>
    ...
    !!
    ...
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SZINEK = ("S", "H", "D", "C")
KODOLASOK = ("cp852", "cp1250", "iso-8859-2", "utf-8")


# --- Adatszerkezetek --------------------------------------------------

@dataclass
class Szabaly:
    licit: str            # 1S, 2N, ...
    feltetel: str         # a nyers kifejezés
    sorszam: int          # a helyzeten belüli sorrend (a korábbi nyer)
    ast: "Csomopont | None" = None
    hiba: str | None = None


@dataclass
class Helyzet:
    minta: str                     # "1C-1D-1H" — a kibic mintanyelv alakja!
    szabalyok: list[Szabaly] = field(default_factory=list)


@dataclass
class Rendszer:
    nev: str
    inditasok: Helyzet = field(default_factory=lambda: Helyzet("START"))
    helyzetek: list[Helyzet] = field(default_factory=list)


# --- Kifejezés-AST ----------------------------------------------------

@dataclass
class Csomopont:
    fajta: str            # ES, VAGY, NEM, OSSZE (hasonlítás), INTERVALLUM,
                          # ELOSZTAS, RENDEZETT_ELOSZTAS, LAP, SZKOR, JELZO
    gyerekek: list["Csomopont"] = field(default_factory=list)
    ertek: object = None

    def __str__(self) -> str:
        if self.fajta == "ES":
            return "(" + " ÉS ".join(str(g) for g in self.gyerekek) + ")"
        if self.fajta == "VAGY":
            return "(" + " VAGY ".join(str(g) for g in self.gyerekek) + ")"
        if self.fajta == "NEM":
            return f"NEM {self.gyerekek[0]}"
        return str(self.ertek)


class NyelviHiba(ValueError):
    pass


# --- Tokenizáló és elemző (rekurzív leszállás) ------------------------

TOKEN_RE = re.compile(r"""
    (?P<elosztas>[ea]\d{4})            # e4432 / a5431
  | (?P<lap>v[SHDC][AKQJT2-9])         # vSA
  | (?P<szkor>@[MASO])                 # @M
  | (?P<jelzo>L[1-4]|f[1-4]|[SHDCFPKijtb])
  | (?P<szam>\d+)
  | (?P<interv>\[\s*\d+\s*,\s*\d+\s*\])
  | (?P<op>[&o()+\-=<>])
  | (?P<neg>n(?=\())
""", re.X)


def tokenizal(s: str) -> list[tuple[str, str]]:
    tokenek, poz = [], 0
    s = s.replace(" ", "")
    while poz < len(s):
        m = TOKEN_RE.match(s, poz)
        if not m:
            raise NyelviHiba(f"Ismeretlen jel a(z) {poz}. pozíción: {s[poz:poz+8]!r}")
        for nev, ertek in m.groupdict().items():
            if ertek is not None:
                tokenek.append((nev, ertek))
                break
        poz = m.end()
    return tokenek


class Elemzo:
    """Rekurzív leszálló elemző. Precedencia: o (VAGY) < & (ÉS) < atom."""

    def __init__(self, tokenek: list[tuple[str, str]]):
        self.t = tokenek
        self.i = 0

    def kovetkezo(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def elfogad(self, ertek: str) -> bool:
        if self.kovetkezo()[1] == ertek:
            self.i += 1
            return True
        return False

    def elemez(self) -> Csomopont:
        cs = self.vagy()
        if self.i < len(self.t):
            raise NyelviHiba(f"Feldolgozatlan maradék: {self.t[self.i:]}")
        return cs

    def vagy(self) -> Csomopont:
        tagok = [self.es()]
        while self.elfogad("o"):
            tagok.append(self.es())
        return tagok[0] if len(tagok) == 1 else Csomopont("VAGY", tagok)

    def es(self) -> Csomopont:
        tagok = [self.atom()]
        while self.elfogad("&"):
            tagok.append(self.atom())
        return tagok[0] if len(tagok) == 1 else Csomopont("ES", tagok)

    def atom(self) -> Csomopont:
        fajta, ertek = self.kovetkezo()
        if ertek == "n":
            self.i += 1
            if not self.elfogad("("):
                raise NyelviHiba("n után '(' kell")
            belso = self.vagy()
            if not self.elfogad(")"):
                raise NyelviHiba("Lezáratlan negáció")
            return Csomopont("NEM", [belso])
        if ertek == "(":
            self.i += 1
            belso = self.vagy()
            if not self.elfogad(")"):
                raise NyelviHiba("Lezáratlan zárójel")
            return belso
        if fajta == "elosztas":
            self.i += 1
            return Csomopont("RENDEZETT_ELOSZTAS" if ertek[0] == "a"
                             else "ELOSZTAS", ertek=ertek[1:])
        if fajta == "szkor":
            self.i += 1
            return Csomopont("SZKOR", ertek=ertek[1:])
        # Aritmetikai összehasonlítás: bal <op> jobb, esetleg [x,y]
        bal = self.kifejezes()
        fajta2, ertek2 = self.kovetkezo()
        if fajta2 == "interv":
            self.i += 1
            a, b = re.findall(r"\d+", ertek2)
            return Csomopont("INTERVALLUM", [bal], (int(a), int(b)))
        if ertek2 in (">", "<", "="):
            self.i += 1
            jobb = self.kifejezes()
            return Csomopont("OSSZE", [bal, jobb], ertek2)
        # Csupasz jelzők önálló állításként: `i` (indulóerő), `b` (egyenletes)
        if bal.fajta == "JELZO" and bal.ertek in ("i", "b"):
            return Csomopont("JELZO_ALLITAS", ertek=bal.ertek)
        raise NyelviHiba(f"Hiányzó összehasonlító operátor {bal} után")

    def kifejezes(self) -> Csomopont:
        """Összeadás és kivonás: S+f1, H-1, vHA+vHK+vHQ stb."""
        tagok = [self.ertek()]
        jelek = []
        while True:
            if self.elfogad("+"):
                jelek.append(1)
            elif self.elfogad("-"):
                jelek.append(-1)
            else:
                break
            tagok.append(self.ertek())
        if len(tagok) == 1:
            return tagok[0]
        return Csomopont("OSSZEG", tagok, jelek)

    def ertek(self) -> Csomopont:
        fajta, ertek = self.kovetkezo()
        if fajta == "szam":
            self.i += 1
            return Csomopont("SZAM", ertek=int(ertek))
        if fajta == "jelzo":
            self.i += 1
            return Csomopont("JELZO", ertek=ertek)
        if fajta == "lap":
            self.i += 1
            return Csomopont("LAP", ertek=ertek[1:])
        raise NyelviHiba(f"Értéket vártam, ez jött: {ertek!r}")


def feltetel_elemez(s: str) -> Csomopont:
    return Elemzo(tokenizal(s)).elemez()


# --- Fájlolvasás ------------------------------------------------------

def olvas(ut: str) -> Rendszer:
    nyers = open(ut, "rb").read()
    szoveg = None
    for kod in KODOLASOK:
        try:
            szoveg = nyers.decode(kod)
            break
        except UnicodeDecodeError:
            continue
    if szoveg is None:
        raise ValueError(f"Nem dekódolható: {ut}")
    szoveg = szoveg.replace("\r", "").replace("\x1a", "")

    r = Rendszer(nev=ut.rsplit("/", 1)[-1])
    blokkok = szoveg.split("!!")

    # Az első blokk: START + indítólicitek
    elso = [s for s in blokkok[0].split("\n") if s.strip()]
    if elso and elso[0].strip().upper() == "START":
        elso = elso[1:]
    r.inditasok.szabalyok = _szabalyok(elso)

    for b in blokkok[1:]:
        sorok = [s for s in b.split("\n") if s.strip()]
        if not sorok:
            continue
        h = Helyzet(minta=sorok[0].strip())
        h.szabalyok = _szabalyok(sorok[1:])
        r.helyzetek.append(h)
    return r


def _szabalyok(sorok: list[str]) -> list[Szabaly]:
    ki = []
    for i, s in enumerate(sorok):
        m = re.match(r"^\s*([1-7][SHDCN])\s*:\s*(.+?)\s*$", s)
        if not m:
            continue
        sz = Szabaly(licit=m.group(1), feltetel=m.group(2), sorszam=i)
        try:
            sz.ast = feltetel_elemez(sz.feltetel)
        except NyelviHiba as e:
            sz.hiba = str(e)
        ki.append(sz)
    return ki


# --- Statisztika ------------------------------------------------------

def statisztika(r: Rendszer) -> dict:
    minden = list(r.inditasok.szabalyok)
    for h in r.helyzetek:
        minden.extend(h.szabalyok)
    hibas = [s for s in minden if s.hiba]
    return {
        "helyzetek": len(r.helyzetek),
        "szabalyok": len(minden),
        "elemzett": len(minden) - len(hibas),
        "hibas": len(hibas),
        "hibapeldak": [(s.licit, s.feltetel[:60], s.hiba) for s in hibas[:8]],
    }


def main(argv: list[str] | None = None) -> int:
    """CLI: LICREN .lr fájlok elemzése és statisztika."""
    import argparse
    import glob as _glob

    ap = argparse.ArgumentParser(
        description="LICREN (.lr) licitrendszer-fájlok elemzése",
        epilog="Példa: python -m kibic.impex.licren 'rendszerek/**/*.lr' --hibak")
    ap.add_argument("utak", nargs="+", help=".lr fájlok (glob is)")
    ap.add_argument("--hibak", action="store_true",
                    help="Az elemzési hibák részletes kiírása")
    ap.add_argument("--helyzetek", action="store_true",
                    help="A licithelyzetek (minták) listázása")
    ap.add_argument("--szabalyok", metavar="MINTA",
                    help="Egy adott licithelyzet szabályainak kiírása, pl. 1C-1D")
    ap.add_argument("--fa", action="store_true",
                    help="Az elemzett feltételek fastruktúrája")
    a = ap.parse_args(argv)

    utak: list[str] = []
    for m in a.utak:
        utak.extend(sorted(_glob.glob(m, recursive=True)) or [m])
    if not utak:
        ap.error("Nem található fájl a megadott mintára")

    hibas_ossz = 0
    for ut in utak:
        r = olvas(ut)
        st = statisztika(r)
        hibas_ossz += st["hibas"]
        print(f"{r.nev}: {st['helyzetek']} helyzet, {st['szabalyok']} szabály, "
              f"elemzett {st['elemzett']}, hibás {st['hibas']}")

        if a.hibak:
            minden = list(r.inditasok.szabalyok)
            for h in r.helyzetek:
                minden.extend(h.szabalyok)
            for sz in (x for x in minden if x.hiba):
                print(f"   ! {sz.licit}: {sz.feltetel[:70]}")
                print(f"     -> {sz.hiba}")

        if a.helyzetek:
            for h in r.helyzetek:
                print(f"   {h.minta:<24} {len(h.szabalyok)} szabály")

        if a.szabalyok:
            for h in r.helyzetek:
                if h.minta.upper() == a.szabalyok.upper():
                    print(f"   === {h.minta} ===")
                    for sz in h.szabalyok:
                        print(f"   {sz.licit}: {sz.feltetel}")
                        if a.fa and sz.ast:
                            print(f"       -> {sz.ast}")
        elif a.fa:
            for sz in r.inditasok.szabalyok:
                print(f"   {sz.licit}: {sz.feltetel}")
                if sz.ast:
                    print(f"       -> {sz.ast}")

    # A maradék hibák a FORRÁSFÁJLOK elgépelései (felesleges záró zárójel,
    # hiányzó `v` a lapjelölés elől, befejezetlen `o` vagylagosság).
    # Ezeket szándékosan nem nyeljük le: a tudásbázisba hibás szabály
    # nem kerülhet be csendben.
    return 1 if hibas_ossz else 0


if __name__ == "__main__":
    raise SystemExit(main())


# =====================================================================
#  Fordítás a kibic kifejezésfájára (motor/kifejezes.py)
# =====================================================================

# A LICREN jelzők leképezése. Ami None, annak a KÉPLETE MÉG NEM TISZTÁZOTT:
# ezek ISMERETLEN csomópontot adnak, így a kiértékelés háromértékű lesz,
# és MEGSZÁMOLHATÓ, hány szabály hiúsul meg miattuk.
JELZO_TERKEP: dict[str, dict | None] = {
    "F": {"t": "ERT", "kod": "HCP"},
    "K": {"t": "ERT", "kod": "KONTROLL"},
    "b": {"t": "ERT", "kod": "EGYENLETES"},
    # A LICREN `t` a gyorsütések TÍZSZERESE
    "t": {"t": "ERT", "kod": "GYORSUTES", "szorzo": 10},
    "S": {"t": "SZIN", "szin": "S"},
    "H": {"t": "SZIN", "szin": "H"},
    "D": {"t": "SZIN", "szin": "D"},
    "C": {"t": "SZIN", "szin": "C"},
    "L1": {"t": "HOSSZ", "rang": 1}, "L2": {"t": "HOSSZ", "rang": 2},
    "L3": {"t": "HOSSZ", "rang": 3}, "L4": {"t": "HOSSZ", "rang": 4},
    "f1": {"t": "FIG", "rang": 1}, "f2": {"t": "FIG", "rang": 2},
    "f3": {"t": "FIG", "rang": 3}, "f4": {"t": "FIG", "rang": 4},
    # LOGIKAI hivatkozások: a képletük RENDSZERFÜGGŐ, és MÉRÉSSEL dől el.
    # A `@` prefix azt jelenti: "az a metrika, amit ez a rendszer így ért".
    # A feloldás a Kontextus.metrika szótárból jön (rendszer_parameter).
    "P": {"t": "ERT", "kod": "@PONT"},          # 396x a stand.lr-ben
    "j": {"t": "ERT", "kod": "@JATEKUTES"},     # játékütés * 10
}

# Az `i` (indulóerő) NEM szám, hanem LOGIKAI állítás — ezért a nevesített
# kritérium-készletre mutat. Így valósul meg, hogy az indulóerőt több
# értékelés együttese döntse el (LEGALABB-csomópont a készleten belül).
JELZO_ALLITAS_TERKEP: dict[str, dict] = {
    "i": {"t": "KESZLET", "kod": "@INDULOERO"},
    "b": {"t": "OSSZE", "op": "=",
          "bal": {"t": "ERT", "kod": "EGYENLETES"},
          "jobb": {"t": "SZAM", "v": 1}},
}


def _kif_fordit(cs: "Csomopont") -> dict:
    """Numerikus részkifejezés -> kibic JSON."""
    if cs.fajta == "SZAM":
        return {"t": "SZAM", "v": cs.ertek}
    if cs.fajta == "LAP":
        return {"t": "LAP", "lap": str(cs.ertek)}
    if cs.fajta == "JELZO":
        kod = str(cs.ertek)
        cel = JELZO_TERKEP.get(kod)
        if cel is None:
            return {"t": "ISMERETLEN", "kod": kod}
        return dict(cel)
    if cs.fajta == "OSSZEG":
        return {"t": "OSSZEG",
                "gy": [_kif_fordit(g) for g in cs.gyerekek],
                "jelek": list(cs.ertek) if cs.ertek else [1] * (len(cs.gyerekek) - 1)}
    raise NyelviHiba(f"Nem fordítható kifejezés: {cs.fajta}")


def fordit(cs: "Csomopont") -> dict:
    """
    Egy elemzett LICREN-feltétel átfordítása a kibic kifejezésfájára.
    A fa a `licitmenet.feltetel` JSON oszlopba kerül.
    """
    if cs.fajta == "ES":
        return {"t": "ES", "gy": [fordit(g) for g in cs.gyerekek]}
    if cs.fajta == "VAGY":
        return {"t": "VAGY", "gy": [fordit(g) for g in cs.gyerekek]}
    if cs.fajta == "NEM":
        return {"t": "NEM", "gy": [fordit(cs.gyerekek[0])]}
    if cs.fajta == "OSSZE":
        return {"t": "OSSZE", "op": str(cs.ertek),
                "bal": _kif_fordit(cs.gyerekek[0]),
                "jobb": _kif_fordit(cs.gyerekek[1])}
    if cs.fajta == "INTERVALLUM":
        also, felso = cs.ertek
        return {"t": "INTERV", "kif": _kif_fordit(cs.gyerekek[0]),
                "min": also, "max": felso}
    if cs.fajta == "ELOSZTAS":
        return {"t": "ELOSZTAS", "alak": str(cs.ertek), "rendezett": False}
    if cs.fajta == "RENDEZETT_ELOSZTAS":
        return {"t": "ELOSZTAS", "alak": str(cs.ertek), "rendezett": True}
    if cs.fajta == "SZKOR":
        return {"t": "SZKOR", "ertek": str(cs.ertek)}
    if cs.fajta == "JELZO_ALLITAS":
        kod = str(cs.ertek)
        cel = JELZO_ALLITAS_TERKEP.get(kod)
        return dict(cel) if cel else {"t": "ISMERETLEN", "kod": kod}
    if cs.fajta == "LAP":
        return {"t": "OSSZE", "op": "=",
                "bal": {"t": "LAP", "lap": str(cs.ertek)},
                "jobb": {"t": "SZAM", "v": 1}}
    raise NyelviHiba(f"Nem fordítható csomópont: {cs.fajta}")
