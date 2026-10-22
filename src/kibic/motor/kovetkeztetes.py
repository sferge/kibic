"""
KIZÁRÁSOS KÖVETKEZTETÉS (2026-10-02): mit NEM mondott a licitáló?

A kényszertár (propagal.py) azt tudja, amit a licit szabálya kimond. A jó
játékos ennél többet olvas ki: azt is, amit a licitáló NEM licitált, pedig
a megállapodás szerint licitálta volna. „A partner kontrázott, nem mondott
2♦-t — tehát nincs 11 pontja ötös káróval.” „Az ellenfél passzolt — tehát
nincs nyitóereje.” Ez az indirekt információ.

A MÓDSZER: a licitáló SZIMULÁLÁSA. A licit előtti tudásunk szerint lehetséges
kezeket sorsolunk neki, mindegyikkel lefuttatjuk az Ő rendszerét (a
licitmotort, ugyanazzal a menettel), és megnézzük, melyik kézzel mondta
volna ugyanazt, amit mondott. A többit a licitje KIZÁRTA. A megmaradt
kezekből olvassuk ki a pontsávot és a színhosszakat.

Így a megállapodás minden része dolgozik: a prioritások, a „minden más”
sorok, a passz — anélkül, hogy a tagadásokat kézzel le kellene írni.

FENNTARTÁS: ez VALÓSZÍNŰ tudás, nem biztos — mintán alapul, és a licitáló
is hibázhat. Ezért külön rétegben él (`Eredmeny.kovetkeztetett`), nem a
kényszertárban: a mintavétel és a gémesély használja, a biztos feltételek
(`ha: {partner_szin}` …) nem. A határt csak ott húzzuk meg, ahol a minta
BIZONYÍTJA: a határon túl elég kéz volt, és egyik sem licitált volna így.
"""
from __future__ import annotations

import os
import random
import time
from copy import deepcopy

from ..domain import ERTEKELOK, LAPOK, SZINEK, Kez, Lap
from .helyzet import Allas, Igeret

MIN_KIVUL = 10         # ennyi összeférhetetlen kéz kell a határon túl a vágáshoz
MINTA_DB = int(os.environ.get("KIBIC_KOVETKEZTETES_MINTA", "120"))
_PAKLI = [Lap(sz, e) for sz in SZINEK for e in LAPOK]
_GYORSITOTAR: dict = {}
_GY_MAX = 2000


def _hcp(kez: Kez) -> int:
    return int(round(float(ERTEKELOK["HCP"](kez))))


def kez_minta(ig: Igeret, db: int, rnd: random.Random,
              max_proba: int = 4000) -> list[Kez]:
    """`db` véletlen kéz, amely kielégíti az ígéretet (elutasításos mintavétel)."""
    ki: list[Kez] = []
    pakli = list(_PAKLI)
    for _ in range(max_proba):
        if len(ki) >= db:
            break
        rnd.shuffle(pakli)
        kez = Kez(frozenset(pakli[:13]))
        if not ig.pont_min <= _hcp(kez) <= ig.pont_max:
            continue
        if all(ig.hossz(sz)[0] <= kez.hossz(sz) <= ig.hossz(sz)[1] for sz in SZINEK):
            ki.append(kez)
    return ki


def szabalyos_hivasok(licitek: list[dict], ules: str) -> list[str]:
    from ..domain import vonal
    rang = {"C": 0, "D": 1, "H": 2, "S": 3, "NT": 4}
    legm, utolso = (0, -1), None
    for e in licitek:
        h = str(e.get("licit", "")).upper()
        if h in ("P", "PASS", ""):
            continue
        utolso = (e.get("ules"), h)
        if h not in ("X", "XX"):
            legm = (int(h[0]), rang[h[1:]])
    ki = ["P"]
    if utolso and vonal(utolso[0]) != vonal(ules):
        ki += ["X"] if utolso[1] not in ("X", "XX") else (["XX"] if utolso[1] == "X" else [])
    ki += [f"{sz}{s}" for sz in range(1, 8) for s in ("C", "D", "H", "S", "NT")
           if (sz, rang[s]) > legm]
    return ki


def _hatar(ertekek: list[tuple[int, bool, int]], lo: int, hi: int,
           pont_sav: tuple[int, int] | None = None) -> tuple[int, int]:
    """
    A licittel ÖSSZEFÉRŐ kezek tartománya ([(érték, ugyanígy licitált-e,
    figurapont)]). Egy oldalt csak akkor vágunk, ha azon túl legalább
    MIN_KIVUL kéz volt, és EGYIK sem licitált volna így (bizonyíték, nem
    csak hiányzó minta). A határ a legközelebbi összeférhetetlen érték előtt
    van (a kevés elfogadott kéz szélső értéke alábecsülné).

    Hossznál (`pont_sav` megadva) csak azok a kezek bizonyítanak, amelyek
    pontja az összeférő kezek pontsávjában van: különben a hossz és a pont
    együttmozgása hamis következtetést adna („4 kőrrel nem passzol” — pedig
    gyengével igen, csak az ritkább).
    """
    elf = [v for v, ok, _ in ertekek if ok]
    if not elf:
        return lo, hi
    a, f = min(elf), max(elf)
    szamit = [(v, ok) for v, ok, p in ertekek
              if pont_sav is None or pont_sav[0] <= p <= pont_sav[1]]
    felul = sorted(v for v, ok in szamit if v > f)
    alul = sorted(v for v, ok in szamit if v < a)
    uj_hi = felul[0] - 1 if len(felul) >= MIN_KIVUL else hi
    uj_lo = alul[-1] + 1 if len(alul) >= MIN_KIVUL else lo
    return max(lo, uj_lo), min(hi, uj_hi)


def kovetkeztet(sorok, paramtar, elozo: list[dict], ules: str, licit: str,
                tar: dict[str, Igeret], ig_utana: Igeret, oszto: str | None,
                beliallas: str = "NONE", csaladok: dict | None = None,
                mag: int = 1) -> tuple[Igeret | None, dict]:
    """
    A licitáló szimulálása. Visszaad: (a kikövetkeztetett ígéret vagy None,
    statisztika). `ig_utana`: amit a licit kimond (a kényszertár a licit után).
    """
    kulcs = (id(sorok), tuple((e.get("ules"), e.get("licit")) for e in elozo),
             ules, licit, beliallas, MINTA_DB)
    if kulcs in _GYORSITOTAR:
        return _GYORSITOTAR[kulcs]

    from .kifejezes import rendszer_kontextus
    from .licital import Licitmotor
    rnd = random.Random(mag)
    kezek = kez_minta(ig_utana, MINTA_DB, rnd)
    stat = {"samples": len(kezek)}
    if len(kezek) < 20:
        _GYORSITOTAR[kulcs] = (None, stat)
        return None, stat

    motor = Licitmotor(sorok, rendszer_kontextus(paramtar), mod="SPECIFIKUSSAG")
    allas = Allas(ules=ules, beliallas=beliallas, licitek=list(elozo), oszto=oszto,
                  kenyszertar=deepcopy(tar), csaladok=dict(csaladok or {}))
    legalis = szabalyos_hivasok(elozo, ules)
    nyito_helyzet = all(str(e.get("licit", "")).upper() in ("P", "PASS") for e in elozo)
    eredmeny: list[tuple[Kez, bool]] = []
    for kez in kezek:
        try:
            d = motor.licital(elozo, ules, kez, beliallas=beliallas,
                              engedelyezett=legalis, allas=allas, oszto=oszto)
        except Exception:          # noqa: BLE001 — egy kéz hibája ne állítsa meg
            continue
        valasztott = d.licit
        if valasztott is None:
            # a rendszer erre a kézre nem mond semmit. Nyitó helyzetben ez
            # passz (nincs nyitóerő); máshol nem bizonyíték.
            if not nyito_helyzet:
                continue
            valasztott = "P"
        eredmeny.append((kez, valasztott == licit))
    elfogadott = sum(1 for _, ok in eredmeny if ok)
    stat.update(evaluated=len(eredmeny), consistent=elfogadott)
    if not eredmeny or elfogadott == 0:
        # a rendszer szerint ez a licit EGYIK lehetséges kézzel sem jönne:
        # vagy a menet ismeretlen ága, vagy hibázott — nem következtetünk
        _GYORSITOTAR[kulcs] = (None, stat)
        return None, stat

    ki = deepcopy(ig_utana)            # a biztos tudás + amit a következtetés hozzátesz
    ki.nyilatkozott = True
    p_lo, p_hi = int(ig_utana.pont_min), int(min(ig_utana.pont_max, 37))
    lo, hi = _hatar([(_hcp(k), ok, 0) for k, ok in eredmeny], p_lo, p_hi)
    # a vágott oldalon egy pont ráhagyás: a határon a minta ritka
    ki.szukit_pont(lo - 1 if lo > p_lo + 1 else None, hi + 1 if hi < p_hi - 1 else None)
    elf_pont = [_hcp(k) for k, ok in eredmeny if ok]
    sav = (min(elf_pont), max(elf_pont))
    for sz in SZINEK:
        a, f = ig_utana.hossz(sz)
        lo, hi = _hatar([(k.hossz(sz), ok, _hcp(k)) for k, ok in eredmeny], a, f, sav)
        if lo > a:
            ki.hossz_min[sz] = lo
        if hi < f:
            ki.hossz_max[sz] = hi
    valtozott = (ki.pont_min > ig_utana.pont_min or ki.pont_max < ig_utana.pont_max
                 or any(ki.hossz(sz) != ig_utana.hossz(sz) for sz in SZINEK))
    res = (ki if valtozott else None, stat)
    if len(_GYORSITOTAR) > _GY_MAX:
        _GYORSITOTAR.clear()
    _GYORSITOTAR[kulcs] = res
    return res


def kulonbseg_szoveg(elotte: Igeret, utana: Igeret) -> str:
    """Csak ami a következtetéssel szűkült: „8-13 pont; kőr: legfeljebb 2”."""
    nev = {"S": "pikk", "H": "kőr", "D": "káró", "C": "treff"}
    reszek = []
    if utana.pont_min > elotte.pont_min or utana.pont_max < elotte.pont_max:
        hi = "" if utana.pont_max >= 40 else f"{utana.pont_max:g}"
        reszek.append(f"{utana.pont_min:g}-{hi} pont" if hi else f"{utana.pont_min:g}+ pont")
    for sz in ("S", "H", "D", "C"):
        a0, f0 = elotte.hossz(sz)
        a, f = utana.hossz(sz)
        if a > a0 and f < f0:
            reszek.append(f"{nev[sz]}: {a}-{f}")
        elif a > a0:
            reszek.append(f"{nev[sz]}: legalább {a}")
        elif f < f0:
            reszek.append(f"{nev[sz]}: legfeljebb {f}")
    return "; ".join(reszek)


def egyesit_valoszinu(cel: Igeret | None, uj: Igeret) -> Igeret:
    """Két következtetés metszete (ugyanarról az ülésről, egymás után)."""
    if cel is None:
        return deepcopy(uj)
    cel.szukit_pont(uj.pont_min, uj.pont_max)
    for sz, v in uj.hossz_min.items():
        cel.hossz_min[sz] = max(cel.hossz_min.get(sz, 0), v)
    for sz, v in uj.hossz_max.items():
        cel.hossz_max[sz] = min(cel.hossz_max.get(sz, 13), v)
    return cel


def szukitett_tar(tar: dict[str, Igeret], valoszinu: dict[str, Igeret]) -> dict[str, Igeret]:
    """A kényszertár, a következtetéssel szűkítve (a mintavételhez)."""
    ki = deepcopy(tar)
    for u, v in (valoszinu or {}).items():
        ig = ki.get(u)
        if ig is None:
            continue
        lo = max(ig.pont_min, v.pont_min)
        hi = min(ig.pont_max, v.pont_max)
        if lo <= hi:
            ig.pont_min, ig.pont_max = lo, hi
        for sz in SZINEK:
            a = max(ig.hossz(sz)[0], v.hossz(sz)[0])
            f = min(ig.hossz(sz)[1], v.hossz(sz)[1])
            if a <= f:
                ig.hossz_min[sz], ig.hossz_max[sz] = a, f
    return ki


def kovetkeztetes_futtat(prop, licitek: list[dict], snapshots: dict,
                         ulesek: set[str], oszto: str | None, beliallas: str,
                         ido_ms: int) -> tuple[dict[str, Igeret], dict[int, dict]]:
    """
    A kenyszertar() után: a menet licitjein VISSZAFELÉ (a legfrissebb a
    legfontosabb), időkeretben. `snapshots[i]` = (tar a licit előtt, ígéret
    a licit után). Visszaad: ({ülés: valószínű ígéret}, {index: info}).
    """
    hatarido = time.monotonic() + ido_ms / 1000.0
    valoszinu: dict[str, Igeret] = {}
    licitenkent: dict[int, dict] = {}
    for i in sorted(snapshots, reverse=True):
        if time.monotonic() > hatarido:
            break
        u, licit = licitek[i]["ules"], licitek[i]["licit"]
        if u not in ulesek:
            continue
        motor = prop.motor_ules(u)
        sorok = getattr(motor, "sorok", None)
        if sorok is None:
            continue
        tar_elotte, ig_utana = snapshots[i]
        ki, stat = kovetkeztet(sorok, motor.paramtar, licitek[:i], u, licit,
                               tar_elotte, ig_utana, oszto, beliallas,
                               prop.csaladok)
        if ki is not None:
            valoszinu[u] = egyesit_valoszinu(valoszinu.get(u), ki)
            licitenkent[i] = {"inferred": ki, "stat": stat,
                              "text": kulonbseg_szoveg(ig_utana, ki)}
    return valoszinu, licitenkent
