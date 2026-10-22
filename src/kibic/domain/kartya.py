"""
Domain-mag: a bridzs alapfogalmai.

Ez a modul semmit nem tud az adatbázisról és a fájlformátumokról.
Minden más réteg (importáló, visszajátszó, motor, DDS-kötés) erre épül.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable, Iterable

# --- Alapkonstansok ---------------------------------------------------

SZINEK = ("S", "H", "D", "C")          # pikk, kőr, káró, treff (PBN-sorrend)
SZIN_NEV = {"S": "pikk", "H": "kőr", "D": "káró", "C": "treff"}
LAPOK = "AKQJT98765432"                 # csökkenő erősség
LAP_ERTEK = {c: 14 - i for i, c in enumerate(LAPOK)}   # A=14 ... 2=2
ULESEK = ("N", "E", "S", "W")           # óramutató járása szerint
ULES_NEV = {"N": "észak", "E": "kelet", "S": "dél", "W": "nyugat"}
BELIK = ("NONE", "NS", "EW", "ALL")

# A figurapont-súlyok NEM itt vannak: az ertekelo.definicio adatban.


def kovetkezo_ules(ules: str, lepes: int = 1) -> str:
    """Az `ules`-től `lepes` hellyel odébb ülő játékos (óramutató szerint)."""
    return ULESEK[(ULESEK.index(ules) + lepes) % 4]


def vonal(ules: str) -> str:
    """A játékos vonala: 'NS' vagy 'EW'."""
    return "NS" if ules in ("N", "S") else "EW"


def beliben(ules: str, beliallas: str) -> bool:
    """Beliben van-e az adott ülés vonala?"""
    if beliallas == "ALL":
        return True
    if beliallas == "NONE":
        return False
    return vonal(ules) == beliallas


# --- Lap --------------------------------------------------------------

@dataclass(frozen=True, order=False)
class Lap:
    szin: str   # S/H/D/C
    ertek: str  # A/K/Q/.../2

    def __post_init__(self):
        if self.szin not in SZINEK or self.ertek not in LAPOK:
            raise ValueError(f"Érvénytelen lap: {self.szin}{self.ertek}")

    @classmethod
    def parse(cls, s: str) -> "Lap":
        """'SA', 'HT', 'D4' -> Lap. Tűri a fordított sorrendet is ('AS')."""
        s = s.strip().upper()
        if len(s) != 2:
            raise ValueError(f"Érvénytelen lapjelölés: {s!r}")
        if s[0] in SZINEK:
            return cls(s[0], s[1])
        if s[1] in SZINEK:
            return cls(s[1], s[0])
        raise ValueError(f"Érvénytelen lapjelölés: {s!r}")

    @property
    def rang(self) -> int:
        return LAP_ERTEK[self.ertek]

    def __str__(self) -> str:
        return f"{self.szin}{self.ertek}"


# --- Kéz --------------------------------------------------------------

@dataclass
class Kez:
    """Egy játékos 13 lapja."""
    lapok: frozenset[Lap]

    @classmethod
    def pbn_bol(cls, s: str) -> "Kez":
        """'Q954.KT62.K965.4' -> Kez  (pikk.kőr.káró.treff)"""
        reszek = s.split(".")
        if len(reszek) != 4:
            raise ValueError(f"A kéznek 4 színre kell tagolódnia: {s!r}")
        lapok = set()
        for szin, betuk in zip(SZINEK, reszek):
            for b in betuk.strip().upper():
                lap = Lap(szin, b)
                if lap in lapok:
                    raise ValueError(f"Duplikált lap: {lap}")
                lapok.add(lap)
        return cls(frozenset(lapok))

    def pbn(self) -> str:
        reszek = []
        for szin in SZINEK:
            betuk = sorted((l.ertek for l in self.lapok if l.szin == szin),
                           key=lambda e: -LAP_ERTEK[e])
            reszek.append("".join(betuk))
        return ".".join(reszek)

    def szin_lapjai(self, szin: str) -> list[Lap]:
        return sorted((l for l in self.lapok if l.szin == szin),
                      key=lambda l: -l.rang)

    def hossz(self, szin: str) -> int:
        return sum(1 for l in self.lapok if l.szin == szin)

    @property
    def hosszak(self) -> tuple[int, int, int, int]:
        """Színhosszak PBN-sorrendben (pikk, kőr, káró, treff)."""
        return tuple(self.hossz(sz) for sz in SZINEK)  # type: ignore

    @property
    def alak(self) -> str:
        """'4-4-3-2' — színhosszak PBN-sorrendben (NEM rendezve!)."""
        return "-".join(str(h) for h in self.hosszak)

    @property
    def rendezett_alak(self) -> str:
        """'4-4-3-2' — csökkenő sorrendbe rendezve, szín-független."""
        return "-".join(str(h) for h in sorted(self.hosszak, reverse=True))

    @property
    def kiegyensulyozott(self) -> bool:
        """4333, 4432, 5332 — szingli és sikén nélkül, legfeljebb egy dubló."""
        return self.rendezett_alak in ("4-3-3-3", "4-4-3-2", "5-3-3-2")

    def __len__(self) -> int:
        return len(self.lapok)

    def __str__(self) -> str:
        return self.pbn()


# --- Értékelők ---------------------------------------------------------
#
# ITT NINCSENEK METRIKÁK. A lapértékelők DEFINÍCIÓI adatként élnek
# (ertekelo.definicio oszlop, pillanatkép: ertekelok.json), és a
# domain/ertekelo.py értelmezi őket. Ez a szótár futásidőben telik meg.
#
# Így egyetlen metrikának EGY forrása van: az adatbázis. Új értékelő
# felvétele vagy meglévő módosítása nem kódmódosítás.

ERTEKELOK: dict[str, "Callable[[Kez], float]"] = {}


def ertekeld(kez: "Kez", kodok: Iterable[str] | None = None) -> dict[str, float]:
    """A kért (vagy az összes regisztrált) metrika kiszámítása egy kézre."""
    kodok = kodok if kodok is not None else list(ERTEKELOK)
    return {k: ERTEKELOK[k](kez) for k in kodok}


# --- Leosztás ---------------------------------------------------------

@dataclass
class Leosztas:
    """Egy teljes leosztás: négy kéz + osztó + beliállás."""
    kezek: dict[str, Kez]          # ules -> Kez
    oszto: str = "N"
    beliallas: str = "NONE"
    tabla_szam: int | None = None

    def __post_init__(self):
        if set(self.kezek) != set(ULESEK):
            raise ValueError(f"Mind a négy ülés kell: {sorted(self.kezek)}")
        if self.oszto not in ULESEK:
            raise ValueError(f"Érvénytelen osztó: {self.oszto}")
        if self.beliallas not in BELIK:
            raise ValueError(f"Érvénytelen beliállás: {self.beliallas}")

    # -- PBN deal-string oda-vissza --

    @classmethod
    def pbn_bol(cls, deal: str, oszto: str = "N", beliallas: str = "NONE",
                tabla_szam: int | None = None) -> "Leosztas":
        """
        'W:Q954.KT62.K965.4 J3.9.AQT8.AQJ763 AT6.A754.42.KT85 K872.QJ83.J73.92'
        Az első kéz a prefixben megnevezett ülésé, onnan óramutató szerint.
        """
        deal = deal.strip()
        if len(deal) < 2 or deal[1] != ":":
            raise ValueError(f"Hiányzó ülés-prefix a deal-stringben: {deal[:20]!r}")
        elso = deal[0].upper()
        if elso not in ULESEK:
            raise ValueError(f"Érvénytelen ülés-prefix: {elso}")
        darabok = deal[2:].split()
        if len(darabok) != 4:
            raise ValueError(f"Négy kéz kell, {len(darabok)} van")
        kezek = {}
        u = elso
        for d in darabok:
            kezek[u] = Kez.pbn_bol(d)
            u = kovetkezo_ules(u)
        lo = cls(kezek, oszto, beliallas, tabla_szam)
        lo.ellenorizd()
        return lo

    def pbn(self, kezdo: str = "N") -> str:
        """Kanonikus alak. Alapértelmezésben mindig 'N:'-ről indul."""
        darabok, u = [], kezdo
        for _ in range(4):
            darabok.append(self.kezek[u].pbn())
            u = kovetkezo_ules(u)
        return f"{kezdo}:" + " ".join(darabok)

    # -- Integritás --

    def ellenorizd(self) -> None:
        """Pontosan 52 különböző lap, kezenként 13."""
        osszes = []
        for u in ULESEK:
            k = self.kezek[u]
            if len(k) != 13:
                raise ValueError(f"{ULES_NEV[u]} kezében {len(k)} lap van (13 kell)")
            osszes.extend(k.lapok)
        if len(set(osszes)) != 52:
            from collections import Counter
            dupla = [str(l) for l, n in Counter(osszes).items() if n > 1]
            raise ValueError(f"Nem 52 különböző lap. Duplikált: {dupla}")

    @property
    def hash(self) -> str:
        """SHA-256 a kanonikus alakon — ez a deduplikáció kulcsa."""
        return hashlib.sha256(self.pbn("N").encode()).hexdigest()

    def hcp(self, ules: str) -> int:
        """Figurapont. Az ERTEKELOK-ból, futásidőben — nincs beégetett képlet."""
        return int(ERTEKELOK["HCP"](self.kezek[ules]))

    def __str__(self) -> str:
        return (f"Leosztás(tábla={self.tabla_szam}, osztó={self.oszto}, "
                f"beli={self.beliallas}, {self.pbn('N')})")
