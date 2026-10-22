"""
Kritérium-kiértékelő.

Ez a modul alakítja a tudásbázis ADATAIT döntéssé. Semmit nem tud az
adatbázisról: kész objektumokat kap (a db/tudastar.py tölti be őket),
és egy Kez-re megmondja, teljesül-e a kritérium.

Két fogalom:

* PARAMÉTER — egy megnevezett szám, amit a bejegyzések NÉVVEL hivatkoznak
  ("NYITAS_MIN"), nem beégetve. Feloldása háromszintű:
  alapérték -> rendszerszintű felülbírálat -> pár-szintű felülbírálat.
  A pár-szintű lehet DEKLARALT (konvenciókártya) vagy MERT (a megfigyelt
  licitekből származtatott) — az utóbbi az ágensprofil belépési pontja.

* KRITÉRIUM-KÉSZLET — összetett feltétel. Nem AND/OR fát tárolunk, hanem
  SZÁMOSSÁGOT: a kötelező kritériumoknak mindig teljesülniük kell, a nem
  kötelezőkből pedig `min_teljesul` darabnak. Így az OR (min=1) és az AND
  (min=N) ugyanannak a mechanizmusnak a két széle, közte pedig a
  "legalább M az N-ből" eset is kifejezhető.

Példa (a nyitási erő, ahogy a valódi rendszerek megfogalmazzák):
    HCP >= 11        kötelező
    ZAR >= 26        nem kötelező  |  ezekből legalább 1
    LTC <= 7         nem kötelező  |
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..domain import ERTEKELOK, Kez


class ParameterHiba(ValueError):
    """Ismeretlen paraméter vagy értékelő a tudásbázisban."""


# --- Paraméterek ------------------------------------------------------

@dataclass(frozen=True)
class Parameter:
    """
    Egy megnevezett érték a tudásbázisból.

    Az `alapertek` SZÁM VAGY SZÖVEG lehet. A szöveges eset ritka, de
    szükséges: az `INFO_KONTRA_HATAR` értéke "4H", mert LICITMAGASSÁGOT
    jelöl, nem számot. A számot váró hívók úgyis `float()`-olnak.
    """
    kod: str
    nev: str
    alapertek: float | str
    ertekelo_kod: str | None = None   # melyik metrikában értendő
    min_ertek: float | None = None    # értelmes tartomány (söpréshez)
    max_ertek: float | None = None
    csoport: str | None = None        # együtt mozgó paraméterek


@dataclass
class Parametertar:
    """
    Feloldott paraméterértékek. A háromszintű feloldás eredménye:
    alapérték -> rendszer -> pár. A `honnan` a naplózáshoz kell.
    """
    parameterek: dict[str, Parameter] = field(default_factory=dict)
    rendszer_ertek: dict[str, float | str] = field(default_factory=dict)
    par_ertek: dict[str, float | str] = field(default_factory=dict)
    honnan: dict[str, str] = field(default_factory=dict)
    # A nevesített kritérium-készletek KIFEJEZÉSFA alakban (kod -> fa),
    # ahogy a `Kontextus.keszletek` várja. A `parametertar_betolt` tölti.
    keszletfak: dict[str, dict] = field(default_factory=dict)

    def metrika_terkep(self) -> dict[str, str]:
        """
        A LOGIKAI hivatkozások (@PONT, @JATEKUTES, @INDULOERO) feloldása
        a rendszer paramétereiből. Ez eddig csak a CLI-mérésekben volt
        kézzel megadva; a szolgáltatás üres szótárral futott, ezért
        MINDEN @PONT-os szabály eldönthetetlen lett.
        """
        ki: dict[str, str] = {}
        for logikai, param in (("PONT", "PONT_METRIKA"),
                               ("JATEKUTES", "JATEKUTES_METRIKA"),
                               ("INDULOERO", "INDULOERO_KESZLET")):
            try:
                v = self.ertek(param)
            except ParameterHiba:
                continue
            if isinstance(v, str) and v:
                ki[logikai] = v
        return ki

    def ertek(self, kod: str) -> float | str:
        if kod in self.par_ertek:
            self.honnan[kod] = "PAR"
            return self.par_ertek[kod]
        if kod in self.rendszer_ertek:
            self.honnan[kod] = "RENDSZER"
            return self.rendszer_ertek[kod]
        p = self.parameterek.get(kod)
        if p is None:
            raise ParameterHiba(f"Ismeretlen paraméter: {kod!r}")
        self.honnan[kod] = "ALAP"
        return p.alapertek

    def tartomany(self, kod: str) -> tuple[float, float] | None:
        """A söpréshez: milyen tartományban érdemes ezt a paramétert mozgatni."""
        p = self.parameterek.get(kod)
        if p is None or p.min_ertek is None or p.max_ertek is None:
            return None
        return (p.min_ertek, p.max_ertek)

    def masolat_felulirassal(self, **felulirasok: float) -> "Parametertar":
        """Paramétersöpréshez: ugyanaz a tár, néhány érték felülírva."""
        uj = Parametertar(dict(self.parameterek), dict(self.rendszer_ertek),
                          dict(self.par_ertek))
        uj.par_ertek.update(felulirasok)
        return uj


def _szam_vagy_szoveg(v):
    """A tárolt érték VARCHAR; ami számnak látszik, az szám legyen."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def parametertar_betolt(conn, rendszer_kod: str | None = None,
                        par_nev: str | None = None) -> Parametertar:
    """
    A háromszintű feloldás betöltése: alapérték -> rendszer -> pár.

    Ez eddig hiányzott: a `Parametertar` megvolt, de senki nem töltötte
    fel az adatbázisból, úgyhogy minden CLI paraméterek nélkül futott —
    és a paraméterre hivatkozó szabályok csendben ELDÖNTHETETLENEK
    lettek. Pont az a fajta néma hiba, amit a háromértékű logikával
    láthatóvá akartunk tenni.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT p.kod, p.nev, p.alapertek, e.kod, p.min_ertek, p.max_ertek,"
        "       p.csoport"
        "  FROM parameter p LEFT JOIN ertekelo e ON e.id = p.ertekelo_id")
    parameterek = {
        kod: Parameter(kod, nev, _szam_vagy_szoveg(alap), ekod,
                       float(mn) if mn is not None else None,
                       float(mx) if mx is not None else None, csop)
        for kod, nev, alap, ekod, mn, mx, csop in cur.fetchall()}

    tar = Parametertar(parameterek=parameterek)

    if rendszer_kod:
        cur.execute(
            "SELECT p.kod, rp.ertek FROM rendszer_parameter rp"
            "  JOIN parameter p ON p.id = rp.parameter_id"
            "  JOIN rendszer r  ON r.id = rp.rendszer_id"
            " WHERE r.kod = %s", (rendszer_kod,))
        tar.rendszer_ertek = {k: _szam_vagy_szoveg(v)
                              for k, v in cur.fetchall()}

    if par_nev:
        # A DEKLARÁLT megelőzi a MÉRT-et: amit a pár magáról mond, az
        # erősebb, mint amit a statisztika kiolvasott belőle.
        cur.execute(
            "SELECT p.kod, pp.ertek, pp.forras FROM par_parameter pp"
            "  JOIN parameter p ON p.id = pp.parameter_id"
            "  JOIN par pr      ON pr.id = pp.par_id"
            " WHERE pr.nev = %s ORDER BY FIELD(pp.forras,'MERT','DEKLARALT')",
            (par_nev,))
        tar.par_ertek = {k: _szam_vagy_szoveg(v) for k, v, _ in cur.fetchall()}

    try:
        tar.keszletfak = keszletfak_betolt(conn)
    except Exception:              # noqa: BLE001 — régi séma: nincs készlet
        tar.keszletfak = {}
    return tar


def keszlet_fa(kriteriumok: list[tuple], min_teljesul: int) -> dict:
    """
    Egy kritérium-készlet KIFEJEZÉSFA alakban:

        ES[ kötelezők..., LEGALABB(m)[ választhatók... ] ]

    `kriteriumok`: (ertekelo_kod, operator, param_kod, ertek, ertek2,
    param_kod2, kotelezo) sorok. A küszöb paraméterként megy a fába,
    hogy a feloldás (alap -> rendszer -> pár) futásidőben történjen.
    """
    def hatar(param, ertek):
        if param:
            return {"t": "PARAM", "kod": param}
        return {"t": "SZAM", "v": float(ertek)}

    def csomopont(ekod, op, p1, e1, e2, p2):
        bal = {"t": "ERT", "kod": ekod}
        if op == "KOZOTT":
            return {"t": "INTERV", "kif": bal, "min": hatar(p1, e1),
                    "max": hatar(p2, e2)}
        return {"t": "OSSZE", "op": op, "bal": bal, "jobb": hatar(p1, e1)}

    kotelezo, valaszthato = [], []
    for ekod, op, p1, e1, e2, p2, kot in kriteriumok:
        (kotelezo if kot else valaszthato).append(
            csomopont(ekod, op, p1, e1, e2, p2))
    m = min(int(min_teljesul or 0), len(valaszthato))
    gy = list(kotelezo)
    if valaszthato and m > 0:
        gy.append({"t": "LEGALABB", "m": m, "gy": valaszthato})
    return {"t": "ES", "gy": gy} if gy else {"t": "IGAZ"}


def keszletfak_betolt(conn) -> dict[str, dict]:
    """A `kriterium_keszlet` + `kriterium` táblák -> {kod: kifejezésfa}."""
    cur = conn.cursor()
    cur.execute("SELECT id, kod, min_teljesul FROM kriterium_keszlet")
    keszletek = {kid: (kod, mt) for kid, kod, mt in cur.fetchall()}
    cur.execute(
        "SELECT k.keszlet_id, e.kod, k.operator, p1.kod, k.ertek, k.ertek2,"
        "       p2.kod, k.kotelezo"
        "  FROM kriterium k"
        "  JOIN ertekelo e ON e.id = k.ertekelo_id"
        "  LEFT JOIN parameter p1 ON p1.id = k.param_id"
        "  LEFT JOIN parameter p2 ON p2.id = k.param_id2"
        " ORDER BY k.keszlet_id, k.sorrend")
    sorok: dict[int, list[tuple]] = {}
    for kid, ekod, op, p1, e1, e2, p2, kot in cur.fetchall():
        sorok.setdefault(kid, []).append((ekod, op, p1, e1, e2, p2, kot))
    return {kod: keszlet_fa(sorok.get(kid, []), mt)
            for kid, (kod, mt) in keszletek.items()}


# --- Kritériumok ------------------------------------------------------

OPERATOROK = (">=", "<=", "=", "KOZOTT")


@dataclass(frozen=True)
class Kriterium:
    """Egyetlen feltétel egy kézre: <értékelő> <operátor> <érték>."""
    ertekelo_kod: str
    operator: str
    param_kod: str | None = None    # paraméterre hivatkozik...
    ertek: float | None = None      # ...vagy fix érték
    ertek2: float | None = None     # KOZOTT felső határa
    param_kod2: str | None = None   # KOZOTT felső határa paraméterként
    kotelezo: bool = False
    leiras: str = ""

    def _hatarok(self, pt: Parametertar) -> tuple[float, float | None]:
        also = pt.ertek(self.param_kod) if self.param_kod else self.ertek
        if also is None:
            raise ParameterHiba(f"A kritériumnak nincs értéke: {self}")
        felso = None
        if self.operator == "KOZOTT":
            felso = (pt.ertek(self.param_kod2) if self.param_kod2
                     else self.ertek2)
            if felso is None:
                raise ParameterHiba(f"A KOZOTT kritériumnak nincs "
                                    f"felső határa: {self}")
        return float(also), (float(felso) if felso is not None else None)

    def kiertekel(self, kez: Kez, pt: Parametertar) -> tuple[bool, str]:
        """Visszaad: (teljesül-e, emberi nyelvű indoklás)."""
        fv = ERTEKELOK.get(self.ertekelo_kod)
        if fv is None:
            raise ParameterHiba(f"Ismeretlen értékelő: {self.ertekelo_kod!r}")
        kapott = fv(kez)
        also, felso = self._hatarok(pt)

        if self.operator == ">=":
            ok = kapott >= also
            szoveg = f"{self.ertekelo_kod}={kapott:g} >= {also:g}"
        elif self.operator == "<=":
            ok = kapott <= also
            szoveg = f"{self.ertekelo_kod}={kapott:g} <= {also:g}"
        elif self.operator == "=":
            ok = kapott == also
            szoveg = f"{self.ertekelo_kod}={kapott:g} = {also:g}"
        elif self.operator == "KOZOTT":
            ok = also <= kapott <= felso  # type: ignore[operator]
            szoveg = f"{also:g} <= {self.ertekelo_kod}={kapott:g} <= {felso:g}"
        else:
            raise ParameterHiba(f"Ismeretlen operátor: {self.operator!r}")
        return ok, ("✓ " if ok else "✗ ") + szoveg


@dataclass
class Eredmeny:
    teljesul: bool
    indoklasok: list[str] = field(default_factory=list)
    kotelezo_bukott: list[str] = field(default_factory=list)
    valaszthato_teljesult: int = 0
    valaszthato_kell: int = 0

    def magyarazat(self) -> str:
        """Emberi nyelvű összefoglaló — ez megy majd a promptba is."""
        sorok = list(self.indoklasok)
        if self.valaszthato_kell:
            sorok.append(f"(a választható feltételekből "
                         f"{self.valaszthato_teljesult}/{self.valaszthato_kell} "
                         f"teljesült)")
        return "; ".join(sorok)


@dataclass
class KriteriumKeszlet:
    """
    Összetett feltétel. A kötelező kritériumoknak MIND teljesülniük kell;
    a nem kötelezőkből `min_teljesul` darabnak.
        min_teljesul = 0  ->  a választhatók nem számítanak
        min_teljesul = 1  ->  VAGY-kapcsolat
        min_teljesul = N  ->  ÉS-kapcsolat (N = a választhatók száma)
    """
    kod: str
    nev: str
    kriteriumok: list[Kriterium] = field(default_factory=list)
    min_teljesul: int = 1

    def kiertekel(self, kez: Kez, pt: Parametertar) -> Eredmeny:
        er = Eredmeny(teljesul=True)
        valaszthato_db = 0
        for k in self.kriteriumok:
            ok, szoveg = k.kiertekel(kez, pt)
            er.indoklasok.append(szoveg)
            if k.kotelezo:
                if not ok:
                    er.teljesul = False
                    er.kotelezo_bukott.append(szoveg)
            else:
                valaszthato_db += 1
                if ok:
                    er.valaszthato_teljesult += 1

        er.valaszthato_kell = min(self.min_teljesul, valaszthato_db)
        if er.valaszthato_teljesult < er.valaszthato_kell:
            er.teljesul = False
        return er


# --- Önteszt ----------------------------------------------------------

def onteszt() -> int:
    hibak = 0

    def allit(nev: str, kapott, vart):
        nonlocal hibak
        ok = kapott == vart
        hibak += 0 if ok else 1
        print(f"  [{'OK  ' if ok else 'HIBA'}] {nev}: "
              f"kapott={kapott}, várt={vart}")

    pt = Parametertar(parameterek={
        "NYITAS_MIN": Parameter("NYITAS_MIN", "Nyitási minimum", 12, "HCP",
                                10, 14, "nyitas"),
        "NYITAS_ZAR": Parameter("NYITAS_ZAR", "Nyitási Zar-küszöb", 26, "ZAR",
                                24, 30, "nyitas"),
        "NYITAS_LTC": Parameter("NYITAS_LTC", "Nyitási LTC-küszöb", 7, "LTC",
                                6, 8, "nyitas"),
        "1NT_MIN": Parameter("1NT_MIN", "1 szan minimum", 15, "HCP", 12, 16),
        "1NT_MAX": Parameter("1NT_MAX", "1 szan maximum", 17, "HCP", 14, 19),
    })

    # A felhasználó ötlete: HCP kötelező, a Zar és az LTC közül legalább egy.
    nyitas = KriteriumKeszlet(
        "NYITAS_ERO", "Nyitási erő",
        [Kriterium("HCP", ">=", "NYITAS_MIN", kotelezo=True),
         Kriterium("ZAR", ">=", "NYITAS_ZAR"),
         Kriterium("LTC", "<=", "NYITAS_LTC")],
        min_teljesul=1)

    print("=== 1. Paraméter-feloldás három szinten ===")
    allit("alapérték", pt.ertek("NYITAS_MIN"), 12)
    pt.rendszer_ertek["NYITAS_MIN"] = 13          # Precision-szerű rendszer
    allit("rendszerszintű felülbírálat", pt.ertek("NYITAS_MIN"), 13)
    pt.par_ertek["NYITAS_MIN"] = 11               # "mi 11-gyel nyitunk"
    allit("pár-szintű felülbírálat", pt.ertek("NYITAS_MIN"), 11)
    allit("a forrás naplózva", pt.honnan["NYITAS_MIN"], "PAR")
    pt.par_ertek.clear()
    pt.rendszer_ertek.clear()

    print("\n=== 2. Egyszerű, kiegyensúlyozott 12 pontos kéz ===")
    # 4-3-3-3, 12 HCP: klasszikus nyitás, de LTC=8 és Zar alacsony
    k1 = Kez.pbn_bol("AQ32.K54.Q76.J32")
    e = nyitas.kiertekel(k1, pt)
    print("   ", e.magyarazat())
    allit("HCP teljesül, de a választhatók nem -> nem nyitás",
          e.teljesul, False)

    print("\n=== 3. Ugyanez, ha csak a HCP számít (min_teljesul=0) ===")
    csak_hcp = KriteriumKeszlet("X", "Csak HCP",
                                [Kriterium("HCP", ">=", "NYITAS_MIN",
                                           kotelezo=True)], min_teljesul=0)
    allit("nyitás", csak_hcp.kiertekel(k1, pt).teljesul, True)

    print("\n=== 4. Elosztásos 11 pontos kéz (a paraméter lejjebb véve) ===")
    # 6-5-1-1: gyenge HCP-ben, de erős elosztásban
    k2 = Kez.pbn_bol("AQ9765.KQ854.3.2")
    pt2 = pt.masolat_felulirassal(NYITAS_MIN=11)
    e2 = nyitas.kiertekel(k2, pt2)
    print("   ", e2.magyarazat())
    allit("11-es küszöbbel nyitás", e2.teljesul, True)
    e3 = nyitas.kiertekel(k2, pt)          # 12-es küszöbnél elbukik a kötelező
    allit("12-es küszöbbel nem", e3.teljesul, False)

    print("\n=== 5. KOZOTT operátor (1 szan tartomány) ===")
    szan = KriteriumKeszlet(
        "1NT", "1 szan nyitás",
        [Kriterium("HCP", "KOZOTT", "1NT_MIN", param_kod2="1NT_MAX",
                   kotelezo=True)], min_teljesul=0)
    allit("16 HCP a 15-17 tartományban",
          szan.kiertekel(Kez.pbn_bol("AQ32.KJ4.Q76.KJ3"), pt).teljesul, True)
    allit("12 HCP nem",
          szan.kiertekel(k1, pt).teljesul, False)

    print("\n=== 6. Söprés: hány kéz nyitna küszöbönként? ===")
    kezek = [k1, k2, Kez.pbn_bol("AKQ2.KQ4.A76.KJ3"),
             Kez.pbn_bol("8532.964.J73.842")]
    for kuszob in (10, 11, 12, 13, 14):
        p = pt.masolat_felulirassal(NYITAS_MIN=kuszob)
        db = sum(1 for k in kezek if nyitas.kiertekel(k, p).teljesul)
        print(f"    NYITAS_MIN={kuszob}: {db}/{len(kezek)} kéz nyitna")

    print(f"\n{'MINDEN TESZT RENDBEN' if not hibak else f'{hibak} HIBA'}")
    return hibak


if __name__ == "__main__":
    raise SystemExit(onteszt())
