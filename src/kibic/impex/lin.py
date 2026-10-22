"""
LIN (BBO) jegyzőkönyv-olvasó.

A LIN a BBO belső formátuma: `|`-lel elválasztott kulcs-érték párok
egyetlen sorban partinként. Kimenete a PBN-olvasóéval AZONOS
(`PbnJatszma`), így az importáló változtatás nélkül kezeli mindkettőt.

A FORMÁTUM BUKTATÓI
-------------------
1. Az `md|` csak HÁROM kezet ad meg — a negyediket a hiányzó lapokból
   kell kiszámolni.
2. Az ülések sorrendje `S W N E` (a `pn|` névlistában is), nem az
   északtól induló óramutató szerinti.
3. Az `md|` első számjegye az OSZTÓ: 1=dél, 2=nyugat, 3=észak, 4=kelet.
4. Az alertek `an|` mezőkben állnak, és az ELŐZŐ licithez tartoznak.
   A licit maga `!`-lel végződhet (`2H!`), ez is alert-jelzés.
5. Az `mc|` a terítés (made claim): a felvevő által bemondott ütésszám.
6. A `sv|` a beliállás: o=senki, n=É-D, e=K-Ny, b=mindkettő.
"""
from __future__ import annotations

import re

from ..domain import Kez, Lap, LAPOK, Leosztas, SZINEK, ULESEK, kovetkezo_ules
from .pbn import PbnJatszma
from ..domain import Kontraktus

# A LIN ülés-sorrendje és az osztó kódja
LIN_ULESEK = ("S", "W", "N", "E")
OSZTO_KOD = {"1": "S", "2": "W", "3": "N", "4": "E"}
BELI_KOD = {"o": "NONE", "n": "NS", "e": "EW", "b": "ALL", "-": "NONE"}

KODOLASOK = ("utf-8-sig", "utf-8", "cp1250", "iso-8859-2", "cp852")


def _kez_parse(s: str) -> Kez:
    """'S8HAQ2DQ532CQT873' -> Kez"""
    lapok = set()
    szin = None
    for c in s.strip().upper():
        if c in SZINEK:
            szin = c
        elif szin and c in LAPOK:
            lapok.add(Lap(szin, c))
    return Kez(frozenset(lapok))


def _negyedik_kez(harom: list[Kez]) -> Kez:
    """A hiányzó kéz a maradék lapokból."""
    megvan = {l for k in harom for l in k.lapok}
    teljes = {Lap(sz, e) for sz in SZINEK for e in LAPOK}
    return Kez(frozenset(teljes - megvan))


def _mezok(sor: str) -> list[tuple[str, str]]:
    """A `kulcs|ertek|kulcs|ertek|...` felbontása párokra."""
    darabok = sor.split("|")
    ki = []
    for i in range(0, len(darabok) - 1, 2):
        ki.append((darabok[i].strip().lower(), darabok[i + 1]))
    return ki


def _licit_normalizal(s: str) -> tuple[str, bool]:
    """'2H!' -> ('2H', True);  'd' -> ('X', False);  'p' -> ('PASS', False)"""
    alert = s.endswith("!")
    t = s.rstrip("!").strip().upper()
    if t in ("P", "PASS"):
        return "PASS", alert
    if t in ("D", "X"):
        return "X", alert
    if t in ("R", "XX"):
        return "XX", alert
    if len(t) == 2 and t[1] == "N":
        t = t[0] + "NT"
    return t, alert


def _jatszma(sor: str) -> PbnJatszma | None:
    mezok = _mezok(sor)
    if not mezok:
        return None

    j = PbnJatszma()
    nevek: list[str] = []
    kezek: list[Kez] = []
    oszto = "N"
    beli = "NONE"
    licitek: list[dict] = []
    lapok: list[str] = []
    claim: int | None = None
    tabla: int | None = None

    for kulcs, ertek in mezok:
        if kulcs == "pn":
            nevek = [x.strip() for x in ertek.split(",")]
        elif kulcs == "md":
            e = ertek.strip()
            if e and e[0] in OSZTO_KOD:
                oszto, e = OSZTO_KOD[e[0]], e[1:]
            kezek = [_kez_parse(x) for x in e.split(",") if x.strip()]
        elif kulcs == "sv":
            beli = BELI_KOD.get(ertek.strip().lower(), "NONE")
        elif kulcs == "ah":
            m = re.search(r"(\d+)", ertek)
            if m:
                tabla = int(m.group(1))
        elif kulcs == "mb":
            licit, alert = _licit_normalizal(ertek)
            licitek.append({"licit": licit, **({"alert": True} if alert else {})})
        elif kulcs == "an":
            if licitek:                       # az ELŐZŐ licithez tartozik
                licitek[-1]["alert"] = True
                licitek[-1]["magyarazat"] = ertek.strip()
        elif kulcs == "pc":
            lapok.append(ertek.strip().upper())
        elif kulcs == "mc":
            try:
                claim = int(ertek.strip())
            except ValueError:
                pass

    if len(kezek) < 3:
        return None
    if len(kezek) == 3:
        kezek.append(_negyedik_kez(kezek))

    # A LIN sorrendje S W N E
    kez_szotar = dict(zip(LIN_ULESEK, kezek))
    try:
        j.leosztas = Leosztas(kez_szotar, oszto, beli, tabla)
        j.leosztas.ellenorizd()
    except ValueError as e:
        j.figyelmeztetesek.append(f"Kiosztás: {e}")
        j.leosztas = None

    if nevek:
        for ules, nev in zip(LIN_ULESEK, nevek):
            j.cimkek[{"N": "North", "E": "East",
                      "S": "South", "W": "West"}[ules]] = nev
    if tabla:
        j.cimkek["Board"] = str(tabla)

    # Ülések hozzárendelése a licitekhez
    u = oszto
    for b in licitek:
        b["ules"] = u
        u = kovetkezo_ules(u)
    j.licit = licitek

    # Kontraktus és felvevő a licitmenetből
    from ..motor.visszajatszo import licit_ellenoriz
    if licitek:
        k, felvevo, _, _ = licit_ellenoriz(licitek, oszto)
        if k:
            j.kontraktus, j.felvevo = k, felvevo
            j.cimkek["Contract"] = str(k)
            j.cimkek["Declarer"] = felvevo

    j.lapok = lapok
    if claim is not None:
        j.eredmeny_utes = claim
        j.cimkek["Result"] = str(claim)
        if len(lapok) < 52:
            j.claim_utes = len(lapok) // 4 + 1
            j.claim_utesszam = claim
    elif len(lapok) == 52 and j.kontraktus:
        from ..motor.visszajatszo import visszajatszik
        er = visszajatszik(j.leosztas, None, lapok,
                           jk_kontraktus=j.kontraktus, jk_felvevo=j.felvevo)
        if er.felvevo_utesek is not None:
            j.eredmeny_utes = er.felvevo_utesek
            j.cimkek["Result"] = str(er.felvevo_utesek)
    elif len(lapok) < 52 and lapok:
        j.claim_utes = len(lapok) // 4 + 1

    if j.kontraktus and j.eredmeny_utes is not None and j.leosztas:
        from ..domain import pontszam_ns
        j.pontszam_ns = pontszam_ns(j.kontraktus, j.eredmeny_utes, beli)
        j.cimkek["Score"] = (f"NS {j.pontszam_ns}" if j.pontszam_ns >= 0
                             else f"NS {j.pontszam_ns}")
    return j


def olvas(szoveg: str) -> list[PbnJatszma]:
    """Egy LIN-fájl tartalmának felolvasása."""
    ki: list[PbnJatszma] = []
    for sor in szoveg.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if "qx|" not in sor and "md|" not in sor:
            continue
        j = _jatszma(sor)
        if j:
            ki.append(j)
    return ki


def olvas_fajl(ut: str) -> list[PbnJatszma]:
    nyers = open(ut, "rb").read()
    for kod in KODOLASOK:
        try:
            return olvas(nyers.decode(kod))
        except UnicodeDecodeError:
            continue
    return olvas(nyers.decode("utf-8", errors="replace"))
