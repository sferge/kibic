"""
PBN (Portable Bridge Notation) olvasó.

A formátum két buktatóját külön kezeljük:

1. A [Play] szakasz sorai NEM időrendben tartalmazzák a lapokat, hanem
   rögzített ülés-rotációban: minden sor első oszlopa a [Play "X"]-ben
   megnevezett üléshez tartozik, akkor is, ha az adott ütést nem ő
   kezdte. A naiv "balról jobbra = időrend" olvasat csendben rossz
   lejátszást rekonstruál. Itt ütésenként visszafejtjük a valódi sorrendet.

2. A lejátszás megszakadhat (claim / bemondás): ilyenkor a szakasz
   egyszerűen véget ér, vagy '-' jelöli a hiányzó lapokat.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..domain import Lap, Leosztas, ULESEK, kovetkezo_ules
from ..domain import Kontraktus

TAG_RE = re.compile(r'^\s*\[\s*(\w+)\s+"(.*)"\s*\]\s*$')

# Címkék, amelyek egy rekordon belül TÖBBSZÖR is előfordulhatnak.
# A [Note] a licitmagyarázatokat (alert-szövegeket) hordozza, rekordonként
# akárhányat. Ha ezeket rekordhatárnak vennénk, minden alertes parti
# szétesne — ez volt a "Hiányzó [Deal] címke" figyelmeztetések forrása.
ISMETELHETO_CIMKEK = {"Note"}
NOTE_RE = re.compile(r'^\s*(\d+)\s*:\s*(.*)$', re.DOTALL)

BELI_TERKEP = {
    "NONE": "NONE", "LOVE": "NONE", "-": "NONE", "": "NONE", "?": "NONE",
    "NS": "NS", "N-S": "NS",
    "EW": "EW", "E-W": "EW",
    "ALL": "ALL", "BOTH": "ALL",
}


@dataclass
class PbnJatszma:
    """Egy PBN-rekord kiolvasott tartalma."""
    cimkek: dict[str, str] = field(default_factory=dict)
    leosztas: Leosztas | None = None
    licit: list[dict] = field(default_factory=list)
    lapok: list[str] = field(default_factory=list)   # IDŐRENDBEN
    claim_utes: int | None = None
    claim_utesszam: int | None = None
    jegyzetek: dict[str, str] = field(default_factory=dict)
    kontraktus: Kontraktus | None = None
    felvevo: str | None = None
    eredmeny_utes: int | None = None
    pontszam_ns: int | None = None
    figyelmeztetesek: list[str] = field(default_factory=list)

    @property
    def tabla_szam(self) -> int | None:
        v = self.cimkek.get("Board")
        return int(v) if v and v.isdigit() else None

    def jatekosok(self) -> dict[str, str]:
        return {u: self.cimkek.get({"N": "North", "E": "East",
                                    "S": "South", "W": "West"}[u], "").strip()
                for u in ULESEK}


def utes_gyoztese(lapok: list[Lap], kezdo: str, aduszin: str | None) -> str:
    """Egy négylapos ütés győztese. `lapok` a kezdőtől időrendben."""
    szin = lapok[0].szin
    legjobb, gyoztes = lapok[0], kezdo
    u = kezdo
    for lap in lapok[1:]:
        u = kovetkezo_ules(u)
        if lap.szin == legjobb.szin:
            if lap.rang > legjobb.rang:
                legjobb, gyoztes = lap, u
        elif aduszin and lap.szin == aduszin and legjobb.szin != aduszin:
            legjobb, gyoztes = lap, u
    return gyoztes


def _licit_parse(sorok: list[str], kezdo: str,
                 jegyzetek: dict[str, str] | None = None) -> list[dict]:
    """
    A licitmenet felolvasása. A tokenek balról jobbra, soronként,
    a kezdőtől óramutató szerint.

    A '=N=' jelölők az előző licithez tartozó magyarázatra (alertre)
    hivatkoznak a [Note] címkék közül. Ezeket NEM dobjuk el: ez a
    licitrendszer-tudásbázis és az ágensprofil legértékesebb nyersanyaga.
    """
    jegyzetek = jegyzetek or {}
    jegyzet_re = re.compile(r"^=(\d+)=$")
    tokenek: list[str] = []
    jegyzet_a_tokenhez: dict[int, list[str]] = {}
    for sor in sorok:
        for t in sor.split():
            m = jegyzet_re.match(t)
            if m:
                # az ELŐZŐ tokenhez tartozik
                if tokenek:
                    jegyzet_a_tokenhez.setdefault(len(tokenek) - 1, []).append(m.group(1))
                continue
            if t == "*":
                continue
            tokenek.append(t)

    licit, u = [], kezdo
    for t in tokenek:
        tf = t.upper()
        if tf in ("AP",):                    # all pass
            while len(licit) % 4 or True:
                licit.append({"ules": u, "licit": "PASS"})
                u = kovetkezo_ules(u)
                if len(licit) >= 4 and all(b["licit"] == "PASS" for b in licit[-3:]):
                    break
            break
        if tf in ("PASS", "P", "-"):
            norm = "PASS"
        elif tf in ("X", "D", "DBL"):
            norm = "X"
        elif tf in ("XX", "R", "RDBL"):
            norm = "XX"
        else:
            norm = tf
        elem = {"ules": u, "licit": norm}
        for szam in jegyzet_a_tokenhez.get(len(licit), []):
            if szam in jegyzetek:
                elem["alert"] = True
                elem["magyarazat"] = jegyzetek[szam]
        licit.append(elem)
        u = kovetkezo_ules(u)
    return licit


def _lejatszas_parse(sorok: list[str], kezdo: str, aduszin: str | None,
                     fig: list[str]) -> tuple[list[str], int | None]:
    """
    A [Play] szakasz visszafejtése IDŐRENDBE.

    A sorok oszlopai fix ülés-rotációban állnak (`kezdo`-től), az ütésen
    belüli valódi sorrend viszont az előző ütés győztesétől indul.
    Visszaad: (lapok időrendben, a megszakadás ütésindexe vagy None).
    """
    rotacio = [kovetkezo_ules(kezdo, i) for i in range(4)]
    idorend: list[str] = []
    utes_kezdo = kezdo
    megszakadt: int | None = None

    for utes_idx, sor in enumerate(sorok):
        tokenek = [t for t in sor.split() if t != "*"]
        if not tokenek:
            continue
        # ülés -> lap az adott ütésben
        ules_lap: dict[str, Lap] = {}
        for oszlop, t in enumerate(tokenek[:4]):
            if t == "-" or t == "--":
                continue
            try:
                ules_lap[rotacio[oszlop]] = Lap.parse(t)
            except ValueError as e:
                fig.append(f"{utes_idx+1}. ütés: {e}")
        if len(ules_lap) < 4:
            megszakadt = utes_idx
            # a részleges ütés lapjait még sorrendbe tesszük, amennyi van
            u = utes_kezdo
            for _ in range(4):
                if u in ules_lap:
                    idorend.append(str(ules_lap[u]))
                u = kovetkezo_ules(u)
            break
        # időrend: az ütés kezdőjétől
        sorrend, u = [], utes_kezdo
        for _ in range(4):
            sorrend.append(ules_lap[u])
            u = kovetkezo_ules(u)
        idorend.extend(str(l) for l in sorrend)
        utes_kezdo = utes_gyoztese(sorrend, utes_kezdo, aduszin)

    return idorend, megszakadt


def _rekord_feldolgoz(cimkek: dict[str, str], szakaszok: dict[str, tuple[str, list[str]]],
                      jegyzetek: dict[str, str] | None = None) -> PbnJatszma:
    j = PbnJatszma(cimkek=dict(cimkek), jegyzetek=dict(jegyzetek or {}))
    fig = j.figyelmeztetesek

    oszto = (cimkek.get("Dealer") or "N").strip().upper()[:1] or "N"
    beli = BELI_TERKEP.get((cimkek.get("Vulnerable") or "NONE").strip().upper(), "NONE")

    # -- Kiosztás --
    deal = cimkek.get("Deal", "").strip()
    if deal:
        try:
            j.leosztas = Leosztas.pbn_bol(deal, oszto, beli,
                                          j.tabla_szam)
        except ValueError as e:
            fig.append(f"Kiosztás: {e}")
    else:
        fig.append("Hiányzó [Deal] címke")

    # -- Felvevő / kontraktus / eredmény --
    j.felvevo = (cimkek.get("Declarer") or "").strip().upper()[:1] or None
    try:
        j.kontraktus = Kontraktus.parse(cimkek.get("Contract", ""),
                                        j.felvevo or "N")
    except ValueError as e:
        fig.append(f"Kontraktus: {e}")

    r = (cimkek.get("Result") or "").strip()
    if r.isdigit():
        j.eredmeny_utes = int(r)

    sc = (cimkek.get("Score") or "").strip()
    if sc:
        m = re.match(r"^(NS|EW)\s*([+-]?\d+)$", sc, re.IGNORECASE)
        if m:
            ertek = int(m.group(2))
            j.pontszam_ns = ertek if m.group(1).upper() == "NS" else -ertek
        elif re.match(r"^[+-]?\d+$", sc):
            j.pontszam_ns = int(sc)

    # -- Licit --
    if "Auction" in szakaszok:
        kezdo, sorok = szakaszok["Auction"]
        j.licit = _licit_parse(sorok, (kezdo or oszto).upper()[:1], j.jegyzetek)

    # -- Lejátszás --
    if "Play" in szakaszok:
        kezdo, sorok = szakaszok["Play"]
        adu = None
        if j.kontraktus and j.kontraktus.szin != "NT":
            adu = j.kontraktus.szin
        lapok, megszakadt = _lejatszas_parse(
            sorok, (kezdo or "W").upper()[:1], adu, fig)
        j.lapok = lapok
        # Claim = a lejátszás nem ér el 52 lapig. Két esete van: részleges
        # ütésnél szakad meg, vagy teljes ütés után egyszerűen véget ér.
        if len(lapok) < 52:
            j.claim_utes = (megszakadt + 1 if megszakadt is not None
                            else len(lapok) // 4 + 1)
            j.claim_utesszam = j.eredmeny_utes
    return j


def olvas(szoveg: str) -> list[PbnJatszma]:
    """Egy PBN-fájl tartalmának felolvasása játszmákra."""
    jatszmak: list[PbnJatszma] = []
    cimkek: dict[str, str] = {}
    szakaszok: dict[str, tuple[str, list[str]]] = {}
    jegyzetek: dict[str, str] = {}
    akt_szakasz: str | None = None
    van_tartalom = False

    def zar():
        nonlocal cimkek, szakaszok, jegyzetek, akt_szakasz, van_tartalom
        if van_tartalom and cimkek:
            jatszmak.append(_rekord_feldolgoz(cimkek, szakaszok, jegyzetek))
        cimkek, szakaszok, jegyzetek = {}, {}, {}
        akt_szakasz, van_tartalom = None, False

    for nyers in szoveg.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        sor = nyers.rstrip()
        if not sor.strip():
            akt_szakasz = None          # üres sor: szakasz vége
            continue
        if sor.lstrip().startswith("%"):
            continue                     # megjegyzés
        m = TAG_RE.match(sor)
        if m:
            kulcs, ertek = m.group(1), m.group(2)
            # A [Note] címkék rekordon belül ismétlődhetnek: gyűjtjük őket,
            # és NEM tekintjük rekordhatárnak.
            if kulcs in ISMETELHETO_CIMKEK:
                if kulcs == "Note":
                    mn = NOTE_RE.match(ertek)
                    if mn:
                        jegyzetek[mn.group(1)] = mn.group(2).strip()
                van_tartalom = True
                akt_szakasz = None
                continue
            # Új rekord kezdete: egy már látott kulcs ismétlődése.
            if kulcs in cimkek and van_tartalom:
                zar()
            cimkek[kulcs] = ertek
            van_tartalom = True
            if kulcs in ("Auction", "Play"):
                akt_szakasz = kulcs
                szakaszok[kulcs] = (ertek, [])
            else:
                akt_szakasz = None
            continue
        if akt_szakasz:
            szakaszok[akt_szakasz][1].append(sor)
    zar()
    return jatszmak
