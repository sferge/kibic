"""
Leosztás-elemzés: DD-tábla, vonalankénti maximum, par, eltérés a partól.

Míg a `/v1/kibic/dd` egy JÁTÉKÁLLÁST elemez (melyik lapot kellett volna
hívni), ez az egész LEOSZTÁST: mit tud a két vonal, mi lett volna az
optimum, és a ténylegesen játszott kontraktus mennyire tért el tőle.
Leosztásonként elég egyszer hívni. Végpont: `POST /v1/kibic/dd-tabla`.

BEMENET — ugyanaz a kéréstest, mint a `/v1/kibic/dd`-nél, így a hívó
újrahasznosíthatja. Minden a kezeken és a beliálláson kívül OPCIONÁLIS:

    {
      "request_id": "...",
      "hands": {...},                  # teljes 52 lap, vagy a még kézben
                                       #   lévők + `play` (mint a /dd-nél)
      "vulnerability": "ns",
      "dealer": "E",                   # ÚJ — a parhoz kell (lásd lent)
      "contract": "4S" | {...} | "P",  # a játszott kontraktus ("P" = passz)
      "declarer": "S",
      "play": [...],                   # ha 52 lap, ebből jön a tényleges ütésszám
      "declarer_tricks": 9             # ÚJ — a tényleges ütésszám közvetlenül
    }

A PAR ÉRTELMEZÉSE (a szokásos konvenció, a DDS is így számol):
mindkét vonal nyílt lapokkal, tökéletesen licitál; a bukó kontraktust
az ellenfél mindig megkontrázza, a teljesülőt soha; rekontra nincs.
Az eredmény egy licitjáték minimax-értéke — ebben a feláldozás és a
feláldozás elleni túllicitálás magától benne van. Az osztó azért
számít, mert ha mindkét vonal ugyanazt tudja, az nyer, aki előbb szól.

A par itt TISZTA PYTHON a DD-táblából és a saját pontozóból — így
endplay nélkül tesztelhető, és a par-kontraktusok szerkezetten jönnek
vissza. Az endplay par-jával a `python -m kibic.cli.ddtabla --osszevet`
veti össze.
"""
from __future__ import annotations

from functools import lru_cache

from ..domain import (Kontraktus, Lap, ULESEK, imp, kovetkezo_ules,
                      pontszam_ns, vonal)
from .dd import (BELI_TERKEP, DdHiba, _kontraktus, _lejatszas, _leosztas,
                 _utes_gyoztes)

FIGYELMEZTETES = (
    "Double dummy elemzés: nyílt lapokkal számol. A tábla azt mutatja, hány "
    "ütést visz a felvevő tökéletes játékkal, a par pedig azt, mi lenne az "
    "eredmény, ha mindkét vonal mindent látna és tökéletesen licitálna. "
    "Valódi játékban egyik sem elvárható mérce, csak viszonyítási pont."
)

# Szín-kódok a VÁLASZBAN: a protokoll jelölése (szan = "N").
# A domain belül "NT"-t használ; a kontraktus-SZÖVEG a /dd-vel egyezően
# "4NT" / "5HX" alakú marad.
SZINEK_KI = ("C", "D", "H", "S", "N")
_DOMAIN = {"C": "C", "D": "D", "H": "H", "S": "S", "N": "NT"}
_VONAL_ULESEI = {"NS": ("N", "S"), "EW": ("E", "W")}
_PASSZ = {"P", "PASS", "PASSED", "AP", "-"}


# --- Kontraktus-index a licitlétrán -----------------------------------
# 0 = 1C, 1 = 1D, ..., 4 = 1N, 5 = 2C, ..., 34 = 7N

def _szint_szin(i: int) -> tuple[int, str]:
    return i // 5 + 1, SZINEK_KI[i % 5]


# --- A DD-tábla feldolgozása ------------------------------------------

def tabla_normalizal(nyers: dict) -> dict[str, dict[str, int]]:
    """A solver kimenete ({ules: {'S','H','D','C','NT'}}) -> protokoll-kulcsok."""
    ki: dict[str, dict[str, int]] = {}
    for u in ULESEK:
        sor = nyers[u]
        ki[u] = {sz: int(sor[_DOMAIN[sz]] if _DOMAIN[sz] in sor else sor[sz])
                 for sz in SZINEK_KI}
    return ki


def vonal_max(tabla: dict[str, dict[str, int]]) -> dict[str, dict]:
    """Vonalanként és színenként a jobbik felvevő ütésszáma."""
    ki: dict[str, dict] = {}
    for v, ulesek in _VONAL_ULESEI.items():
        ki[v] = {}
        for sz in SZINEK_KI:
            legtobb = max(tabla[u][sz] for u in ulesek)
            ki[v][sz] = {
                "tricks": legtobb,
                "declarers": [u for u in ulesek if tabla[u][sz] == legtobb],
                "max_level": legtobb - 6 if legtobb >= 7 else None,
            }
    return ki


def _pont(i: int, v: str, utesek: int, beli: str) -> int:
    """A kontraktus É-D szemszögű pontszáma; a bukót az ellenfél kontrázza."""
    szint, sz = _szint_szin(i)
    kontra = "" if utesek >= szint + 6 else "X"
    k = Kontraktus(szint, _DOMAIN[sz], kontra, _VONAL_ULESEI[v][0])
    return pontszam_ns(k, utesek, beli)


def _kontraktus_leiras(i: int, v: str, maxok: dict, beli: str) -> dict:
    szint, sz = _szint_szin(i)
    m = maxok[v][sz]
    kell = szint + 6
    bukik = m["tricks"] < kell
    kulonbseg = m["tricks"] - kell
    return {
        "contract": f"{szint}{_DOMAIN[sz]}{'X' if bukik else ''}",
        "level": szint,
        "strain": sz,
        "doubled": bukik,
        "side": v,
        "declarers": list(m["declarers"]),
        "tricks": m["tricks"],
        "result": "=" if kulonbseg == 0 else f"{kulonbseg:+d}",
        "score_ns": _pont(i, v, m["tricks"], beli),
    }


def legjobb_kontraktus(maxok: dict, v: str, beli: str) -> dict | None:
    """
    Egy vonal legjobb TELJESÍTHETŐ kontraktusa, az ellenfelet figyelmen
    kívül hagyva ("mit tudunk mi"). Azonos pontszámnál a legalacsonyabb
    szint; ha több szín is ugyanannyit ér, mind.
    """
    elojel = 1 if v == "NS" else -1
    jeloltek = []
    for i in range(35):
        szint, sz = _szint_szin(i)
        if maxok[v][sz]["tricks"] >= szint + 6:
            jeloltek.append((elojel * _pont(i, v, maxok[v][sz]["tricks"], beli), i))
    if not jeloltek:
        return None
    legjobb = max(p for p, _ in jeloltek)
    indexek = _legalacsonyabb([i for p, i in jeloltek if p == legjobb])
    lista = [_kontraktus_leiras(i, v, maxok, beli) for i in indexek]
    return {"score": legjobb, "contracts": lista}


def _legalacsonyabb(indexek) -> list[int]:
    """Ugyanabban a színben csak a legalacsonyabb szint marad."""
    szinenkent: dict[str, int] = {}
    for i in sorted(indexek):
        szinenkent.setdefault(_szint_szin(i)[1], i)
    return sorted(szinenkent.values())


# --- Par: a licitjáték minimax-értéke ---------------------------------

def par(maxok: dict, beli: str, oszto: str) -> dict:
    """
    A par kiszámítása a vonalankénti maximumokból.

    A licit mint kétszemélyes játék (a vonalon belül tökéletes az
    együttműködés): a soron lévő vonal licitálhat magasabbat, vagy
    passzol. Egy licit után az ellenfél, majd a licitáló partnere, majd
    megint az ellenfél következik — ha mind passzol, vége. A nyitás előtt
    négy passz dobja be a lapot. É-D maximalizál, K-Ny minimalizál.

    Visszaad: {"score_ns", "contracts": [...], "passed_out": bool}
    """
    utes = {v: [maxok[v][SZINEK_KI[i % 5]]["tricks"] for i in range(35)]
            for v in ("NS", "EW")}
    vegso = {v: [_pont(i, v, utes[v][i], beli) for i in range(35)]
             for v in ("NS", "EW")}
    masik = {"NS": "EW", "EW": "NS"}
    elojel = {"NS": 1, "EW": -1}

    def valaszt(v: str, opciok: list[tuple[int, frozenset]],
                passz: tuple[int, frozenset] | None = None,
                licitet_elonyben: bool = False):
        """
        `opciok`: a licitek, `passz`: a passz kimenete. Döntetlennél az
        ELLENFÉL kontraktusával szemben ülő vonal licitál, nem büntet: a
        par-konvenció szerint a teljesíthető kontraktus bemondása és az
        arra adott feláldozás a par, nem egy alacsonyabb kontrázott lap,
        amit a másik oldal "ugyanannyiért" hagyna állni.
        """
        mind = opciok + ([passz] if passz else [])
        legjobb = max(elojel[v] * p for p, _ in mind)
        nyero = [x for x in opciok if elojel[v] * x[0] == legjobb]
        if passz and elojel[v] * passz[0] == legjobb and \
                not (licitet_elonyben and nyero):
            nyero.append(passz)
        kesz = frozenset().union(*(s for _, s in nyero))
        return elojel[v] * legjobb, kesz

    @lru_cache(maxsize=None)
    def lep(i: int, tulaj: str, fazis: int):
        """
        `i` kontraktus a `tulaj` vonalé.
        fazis 0: az ellenfél jön; 1: a tulaj partnere; 2: az ellenfél
        utolsó esélye (utána vége).
        """
        soron = tulaj if fazis == 1 else masik[tulaj]
        opciok = [lep(j, soron, 0) for j in range(i + 1, 35)]
        if fazis == 2:
            passz = (vegso[tulaj][i], frozenset({(i, tulaj)}))
        else:
            passz = lep(i, tulaj, fazis + 1)
        return valaszt(soron, opciok, passz, licitet_elonyben=soron != tulaj)

    @lru_cache(maxsize=None)
    def nyitas(passzok: int, soron: str):
        opciok = [lep(j, soron, 0) for j in range(35)]
        passz = ((0, frozenset({None})) if passzok == 3
                 else nyitas(passzok + 1, masik[soron]))
        return valaszt(soron, opciok, passz)

    pont, vegek = nyitas(0, vonal(oszto))

    kontraktusok = []
    for v in ("NS", "EW"):
        indexek = _legalacsonyabb(x[0] for x in vegek if x and x[1] == v)
        kontraktusok += [_kontraktus_leiras(i, v, maxok, beli) for i in indexek]
    return {"score_ns": pont, "contracts": kontraktusok,
            "passed_out": None in vegek and not kontraktusok}


# --- A ténylegesen játszott kontraktus --------------------------------

def _tenyleges_utesek(lejatszas, kontraktus: Kontraktus) -> int:
    """A felvevő ütései egy TELJES (52 lapos) lejátszásból."""
    adu = None if kontraktus.szin == "NT" else kontraktus.szin
    soron = kovetkezo_ules(kontraktus.felvevo)
    aktualis: list[tuple[str, Lap]] = []
    felvevoe = 0
    for n, (ules, lap) in enumerate(lejatszas):
        if ules and ules != soron:
            raise DdHiba(f"A {n+1}. lapnál {soron} következne, a kérés "
                         f"szerint {ules}. Ellenőrizd a kijátszás sorrendjét.")
        aktualis.append((soron, lap))
        soron = kovetkezo_ules(soron)
        if len(aktualis) == 4:
            soron = _utes_gyoztes(aktualis, adu)
            felvevoe += vonal(soron) == vonal(kontraktus.felvevo)
            aktualis = []
    return felvevoe


def _elteres(kulonbseg: int) -> dict:
    return {"score_diff_ns": kulonbseg, "imp_ns": imp(kulonbseg)}


def _jatszott(keres: dict, tabla, par_pont: int, beli: str,
              lejatszas) -> dict | None:
    """A `contract_analysis` blokk — csak ha a kérés hozott kontraktust."""
    ertek = keres.get("contract")
    if ertek in (None, ""):
        return None

    if isinstance(ertek, str) and ertek.strip().upper() in _PASSZ:
        return {"contract": "P", "passed_out": True, "score_ns": 0,
                "vs_par": {"total": _elteres(0 - par_pont)}}

    felvevo = str(keres.get("declarer", "")).upper()[:1]
    if felvevo not in ULESEK:
        raise DdHiba("A `contract` mellé `declarer` is kell (N/E/S/W)")
    k = _kontraktus(ertek, felvevo)
    kell = k.kell_utes
    dd_utes = tabla[felvevo]["N" if k.szin == "NT" else k.szin]
    dd_pont = pontszam_ns(k, dd_utes, beli)

    tenyleges = keres.get("declarer_tricks")
    forras = "declarer_tricks"
    if tenyleges is not None:
        if isinstance(tenyleges, bool) or not isinstance(tenyleges, int) \
                or not 0 <= tenyleges <= 13:
            raise DdHiba("A `declarer_tricks` 0 és 13 közötti egész szám legyen")
    elif len(lejatszas) == 52:
        tenyleges, forras = _tenyleges_utesek(lejatszas, k), "play"
    else:
        forras = None

    def jel(u: int) -> str:
        return "=" if u == kell else f"{u - kell:+d}"

    ki = {
        "contract": str(k),
        "declarer": felvevo,
        "side": vonal(felvevo),
        "needed_tricks": kell,
        "dd_tricks": dd_utes,
        "dd_result": jel(dd_utes),
        "dd_score_ns": dd_pont,
        "actual_tricks": tenyleges,
        "actual_result": jel(tenyleges) if tenyleges is not None else None,
        "actual_score_ns": (pontszam_ns(k, tenyleges, beli)
                            if tenyleges is not None else None),
        "actual_source": forras,
        "vs_par": {
            # a licit: a kontraktus DD-értéke a parhoz képest
            "bidding": _elteres(dd_pont - par_pont),
            # a játék: a tényleges ütésszám a DD-hez képest (felvevő szemszög)
            "play_tricks_diff": (tenyleges - dd_utes
                                 if tenyleges is not None else None),
            # a kettő együtt: a tényleges pontszám a parhoz képest
            "total": (_elteres(pontszam_ns(k, tenyleges, beli) - par_pont)
                      if tenyleges is not None else None),
        },
    }
    return ki


# --- A szolgáltatás ---------------------------------------------------

def ddtabla_elemzes(keres: dict, tabla_fv=None) -> dict:
    """
    Egy leosztás teljes DD-elemzése.

    `tabla_fv`: a DD-tábla forrása (Leosztas -> {ules: {szin: ütés}}).
    Alapból a `solver.dds.dd_tabla`; a tesztek ezen keresztül álcáznak.
    """
    if not isinstance(keres, dict):
        raise DdHiba("A kérés JSON-objektum legyen")
    if tabla_fv is None:
        from ..solver.dds import dd_tabla as tabla_fv   # endplay kell hozzá

    beli = BELI_TERKEP.get(str(keres.get("vulnerability", "none")).upper())
    if beli is None:
        raise DdHiba("A `vulnerability` none / ns / ew / both lehet")

    oszto = keres.get("dealer")
    oszto_feltetelezett = oszto in (None, "")
    if oszto_feltetelezett:
        felv = str(keres.get("declarer", "")).upper()[:1]
        oszto = felv if felv in ULESEK else "N"
    oszto = str(oszto).upper()[:1]
    if oszto not in ULESEK:
        raise DdHiba("A `dealer` N / E / S / W lehet")

    lejatszas = _lejatszas(keres.get("play"))
    if len(lejatszas) > 52:
        raise DdHiba("A `play` legfeljebb 52 lapot tartalmazhat")
    leosztas = _leosztas(keres.get("hands"), lejatszas, oszto, beli)

    tabla = tabla_normalizal(tabla_fv(leosztas))
    maxok = vonal_max(tabla)
    p = par(maxok, beli, oszto)
    if oszto_feltetelezett:
        # Ha nem tudjuk az osztót: számít-e egyáltalán?
        masik = par(maxok, beli, kovetkezo_ules(oszto))
        p["dealer_sensitive"] = masik["score_ns"] != p["score_ns"]
    else:
        p["dealer_sensitive"] = None
    p["dealer"] = oszto
    p["dealer_assumed"] = oszto_feltetelezett

    return {
        "request_id": keres.get("request_id"),
        "vulnerability": keres.get("vulnerability", "none"),
        "dealer": oszto,
        "dd_table": tabla,
        "side_max": maxok,
        "best_contract": {v: legjobb_kontraktus(maxok, v, beli)
                          for v in ("NS", "EW")},
        "par": p,
        "contract_analysis": _jatszott(keres, tabla, p["score_ns"], beli,
                                       lejatszas),
        "warning": FIGYELMEZTETES,
    }
