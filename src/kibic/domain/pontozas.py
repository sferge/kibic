"""
Eredménypontozás (scoring).

FONTOS fogalmi elhatárolás: ez NEM lapértékelés. Ez a bridzsszabályok
része, minden licitrendszerben azonos, és teljesen determinisztikus.
A lapértékelő metrikák (HCP, AP, Zar, LTC) a domain.py-ban élnek.

Ez a modul adja a 0. fázis kilépési feltételének felét: az importált
jegyzőkönyvek `Score` mezőjét ezzel ellenőrizzük.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .domain import beliben, vonal

# Ütésérték szintenként
UTESERTEK = {"C": 20, "D": 20, "H": 30, "S": 30, "NT": 30}

KONTRAKTUS_RE = re.compile(r"^([1-7])(NT|[SHDC])(XX|X)?$", re.IGNORECASE)


@dataclass(frozen=True)
class Kontraktus:
    szint: int          # 1-7
    szin: str           # S/H/D/C/NT
    kontra: str = ""    # "", "X", "XX"
    felvevo: str = "N"

    @classmethod
    def parse(cls, s: str, felvevo: str = "N") -> "Kontraktus | None":
        """'3CX', '4H', '6NTXX' -> Kontraktus. 'PASS'/'' -> None (kiosztott lap)."""
        s = (s or "").strip().upper().replace(" ", "")
        if s in ("", "PASS", "P", "PASSED", "AP"):
            return None
        m = KONTRAKTUS_RE.match(s)
        if not m:
            raise ValueError(f"Értelmezhetetlen kontraktus: {s!r}")
        szint, szin, kontra = m.groups()
        return cls(int(szint), szin.upper(), (kontra or "").upper(), felvevo)

    @property
    def kell_utes(self) -> int:
        return self.szint + 6

    @property
    def szorzo(self) -> int:
        return {"": 1, "X": 2, "XX": 4}[self.kontra]

    def __str__(self) -> str:
        return f"{self.szint}{self.szin}{self.kontra}"


def pontszam(kontraktus: Kontraktus | None, utesek: int, beliallas: str) -> int:
    """
    A felvevő vonalának pontszáma (előjelesen: negatív, ha bukott).
    `utesek`: a felvevő által ténylegesen megnyert ütések (0-13).
    """
    if kontraktus is None:
        return 0

    k = kontraktus
    beli = beliben(k.felvevo, beliallas)
    tobblet = utesek - k.kell_utes

    # --- Bukás ---
    if tobblet < 0:
        bukas = -tobblet
        if k.szorzo == 1:
            pont = bukas * (100 if beli else 50)
        else:
            if beli:
                # 200, majd 300-asával
                pont = 200 + (bukas - 1) * 300
            else:
                # 100, 200, 200, majd 300-asával
                pont = 100
                for i in range(2, bukas + 1):
                    pont += 300 if i >= 4 else 200
            if k.szorzo == 4:
                pont *= 2
        return -pont

    # --- Teljesítés ---
    if k.szin == "NT":
        alap = 40 + (k.szint - 1) * 30
    else:
        alap = k.szint * UTESERTEK[k.szin]
    alap *= k.szorzo

    pont = alap
    # Gém- vagy részjátszma-bónusz
    pont += (500 if beli else 300) if alap >= 100 else 50
    # Szlembónusz
    if k.szint == 6:
        pont += 750 if beli else 500
    elif k.szint == 7:
        pont += 1500 if beli else 1000
    # Kontra-bónusz ("insult")
    if k.szorzo == 2:
        pont += 50
    elif k.szorzo == 4:
        pont += 100
    # Többletütések
    if tobblet:
        if k.szorzo == 1:
            pont += tobblet * (30 if k.szin in ("H", "S", "NT") else 20)
        else:
            egyseg = (200 if beli else 100) * (k.szorzo // 2)
            pont += tobblet * egyseg
    return pont


def pontszam_ns(kontraktus: Kontraktus | None, utesek: int, beliallas: str) -> int:
    """Ugyanaz, de mindig É-D szemszögéből előjelezve (a jegyzőkönyvek így írják)."""
    p = pontszam(kontraktus, utesek, beliallas)
    if kontraktus is None:
        return 0
    return p if vonal(kontraktus.felvevo) == "NS" else -p


# --- IMP-átváltás -----------------------------------------------------

_IMP_HATAR = [20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600, 750,
              900, 1100, 1300, 1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000]


def imp(kulonbseg: int) -> int:
    """Pontkülönbség -> IMP (előjeltartó)."""
    elojel = 1 if kulonbseg >= 0 else -1
    k = abs(kulonbseg)
    n = 0
    for hatar in _IMP_HATAR:
        if k >= hatar:
            n += 1
        else:
            break
    return elojel * n
