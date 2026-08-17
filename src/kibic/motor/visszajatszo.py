"""
Visszajátszó: egy rögzített parti végigfuttatása a szabálymotoron.

Két, egymástól független ellenőrzést végez:

1. LICIT — a licitmenet szabályossága (emelkedő licitek, kontra csak
   ellenfél felvételére, rekontra csak kontrára, helyes lezárás), és a
   menetből LEVEZETETT kontraktus + felvevő egyeztetése a jegyzőkönyv
   [Contract] és [Declarer] címkéivel. Ez a licitparser kereszt-ellenőrzése:
   ha a felvevő levezetése egyezik, akkor a licitmenet ülés-hozzárendelése
   biztosan helyes.

2. LEJÁTSZÁS — ütésről ütésre: a soron lévő játékos kezében van-e a lap,
   megvallotta-e a színt, ki viszi az ütést, hány ütés jön ki a végén.
   Az ütésszám egyeztetése a [Result] címkével.

A visszajátszó nem csak tesztkód: ugyanez az apparátus futtatja majd újra
a saját rendszerünk döntéseit hibakereséskor ("mit látott a kényszertár
a 8. ütésnél?"). Ezért kap részletes ütésnaplót.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..domain import Lap, Leosztas, SZINEK, ULESEK, kovetkezo_ules, vonal
from ..domain import Kontraktus

LICIT_RE = re.compile(r"^([1-7])(NT|[SHDC])$")


# --- Eredménytípusok --------------------------------------------------

@dataclass
class Utes:
    """Egy lejátszott ütés naplója."""
    sorszam: int                 # 1..13
    kezdo: str
    lapok: list[tuple[str, Lap]] # (ules, lap) időrendben
    gyoztes: str

    def __str__(self) -> str:
        s = " ".join(f"{u}:{l}" for u, l in self.lapok)
        return f"{self.sorszam:>2}. {s}  ->  {self.gyoztes}"


@dataclass
class Eredmeny:
    rendben: bool = True
    hibak: list[str] = field(default_factory=list)
    figyelmeztetesek: list[str] = field(default_factory=list)

    # licit
    licit_kontraktus: Kontraktus | None = None
    licit_felvevo: str | None = None
    licit_ellenorzott: bool = False

    # lejátszás
    utesek: list[Utes] = field(default_factory=list)
    felvevo_utesek: int | None = None
    lejatszas_teljes: bool = False
    claim_utes: int | None = None
    claim_utesszam: int | None = None

    def hiba(self, uzenet: str) -> None:
        self.hibak.append(uzenet)
        self.rendben = False


# --- Licitmenet -------------------------------------------------------

def licit_ellenoriz(licitek: list[dict], oszto: str) -> tuple[
        Kontraktus | None, str | None, list[str], list[str]]:
    """
    A licitmenet szabályossági ellenőrzése és a kontraktus levezetése.

    Visszaad: (kontraktus, felvevo, hibak, figyelmeztetesek).
    A kontraktus None, ha a licitmenet négy passzal zárult (kiosztott lap).
    """
    hibak: list[str] = []
    fig: list[str] = []

    utolso_szint = 0
    utolso_szin: str | None = None
    utolso_licitalo: str | None = None
    kontra = ""                 # "", "X", "XX"
    passzok = 0
    lezarva = False
    # ki nevezte meg ELŐSZÖR az adott színt vonalanként
    elso_nevezo: dict[tuple[str, str], str] = {}
    varhato = oszto

    for i, b in enumerate(licitek):
        ules = b.get("ules")
        licit = (b.get("licit") or "").upper()

        if ules != varhato:
            hibak.append(f"{i+1}. licit ({licit}): {varhato} következne, "
                         f"de {ules} licitál")
        if lezarva:
            hibak.append(f"{i+1}. licit ({licit}): a licitmenet már lezárult")
            break

        if licit == "PASS":
            passzok += 1
            if (utolso_szin and passzok >= 3) or (not utolso_szin and passzok >= 4):
                lezarva = True

        elif licit == "X":
            if utolso_szin is None:
                hibak.append(f"{i+1}. licit: kontra felvétel nélkül")
            elif utolso_licitalo and vonal(utolso_licitalo) == vonal(ules):
                hibak.append(f"{i+1}. licit: saját felvétel kontrázása")
            elif kontra:
                hibak.append(f"{i+1}. licit: már kontrázott felvétel kontrázása")
            else:
                kontra = "X"
            passzok = 0

        elif licit == "XX":
            if kontra != "X":
                hibak.append(f"{i+1}. licit: rekontra kontra nélkül")
            elif utolso_licitalo and vonal(utolso_licitalo) != vonal(ules):
                hibak.append(f"{i+1}. licit: ellenfél kontrájának rekontrázása "
                             f"rossz vonalról")
            else:
                kontra = "XX"
            passzok = 0

        else:
            m = LICIT_RE.match(licit)
            if not m:
                hibak.append(f"{i+1}. licit: értelmezhetetlen ({licit!r})")
                passzok = 0
                varhato = kovetkezo_ules(ules or varhato)
                continue
            szint, szin = int(m.group(1)), m.group(2)
            rang = (szint, ["C", "D", "H", "S", "NT"].index(szin))
            utolso_rang = (utolso_szint,
                           ["C", "D", "H", "S", "NT"].index(utolso_szin)
                           if utolso_szin else -1)
            if utolso_szin and rang <= utolso_rang:
                hibak.append(f"{i+1}. licit ({licit}): nem magasabb az előzőnél "
                             f"({utolso_szint}{utolso_szin})")
            utolso_szint, utolso_szin, utolso_licitalo = szint, szin, ules
            kontra = ""
            passzok = 0
            kulcs = (vonal(ules), szin)
            elso_nevezo.setdefault(kulcs, ules)

        varhato = kovetkezo_ules(ules or varhato)

    if not lezarva and licitek:
        fig.append("A licitmenet nem zárult le szabályosan (hiányzó passzok)")

    if utolso_szin is None:
        return None, None, hibak, fig

    felvevo = elso_nevezo.get((vonal(utolso_licitalo), utolso_szin))
    if felvevo is None:
        hibak.append("A felvevő nem vezethető le a licitmenetből")
        return None, None, hibak, fig

    return (Kontraktus(utolso_szint, utolso_szin, kontra, felvevo),
            felvevo, hibak, fig)


# --- Lejátszás --------------------------------------------------------

def _utes_gyoztes(lapok: list[tuple[str, Lap]], adu: str | None) -> str:
    szin = lapok[0][1].szin
    gyoztes, legjobb = lapok[0]
    for ules, lap in lapok[1:]:
        if lap.szin == legjobb.szin:
            if lap.rang > legjobb.rang:
                gyoztes, legjobb = ules, lap
        elif adu and lap.szin == adu and legjobb.szin != adu:
            gyoztes, legjobb = ules, lap
    return gyoztes


def lejatszas_ellenoriz(leosztas: Leosztas, lapok: list[str],
                        kontraktus: Kontraktus, er: Eredmeny) -> None:
    """
    A lejátszás végigfuttatása. A `lapok` IDŐRENDBEN, az első kijátszástól.
    Az eredményt közvetlenül az `er` objektumba írja.
    """
    adu = None if kontraktus.szin == "NT" else kontraktus.szin
    kezek: dict[str, set[Lap]] = {u: set(leosztas.kezek[u].lapok) for u in ULESEK}

    soron = kovetkezo_ules(kontraktus.felvevo)   # a felvevőtől balra ül a kijátszó
    utes_kezdo = soron
    aktualis: list[tuple[str, Lap]] = []
    felvevo_utesek = 0
    utes_szam = 0

    for idx, jeloles in enumerate(lapok):
        try:
            lap = Lap.parse(jeloles)
        except ValueError as e:
            er.hiba(f"{idx+1}. lap: {e}")
            return

        if lap not in kezek[soron]:
            er.hiba(f"{utes_szam+1}. ütés: {soron} kijátszotta a(z) {lap} lapot, "
                    f"de az nincs a kezében")
            return

        # Színkötelezettség
        if aktualis:
            hivott = aktualis[0][1].szin
            if lap.szin != hivott:
                van_meg = any(l.szin == hivott for l in kezek[soron])
                if van_meg:
                    er.hiba(f"{utes_szam+1}. ütés: {soron} nem vallotta meg a(z) "
                            f"{hivott} színt ({lap} lapot tett)")
                    return

        kezek[soron].discard(lap)
        aktualis.append((soron, lap))
        soron = kovetkezo_ules(soron)

        if len(aktualis) == 4:
            utes_szam += 1
            gyoztes = _utes_gyoztes(aktualis, adu)
            er.utesek.append(Utes(utes_szam, utes_kezdo, list(aktualis), gyoztes))
            if vonal(gyoztes) == vonal(kontraktus.felvevo):
                felvevo_utesek += 1
            utes_kezdo = soron = gyoztes
            aktualis = []

    if aktualis:
        er.figyelmeztetesek.append(
            f"A(z) {utes_szam+1}. ütés befejezetlen ({len(aktualis)} lap)")

    er.felvevo_utesek = felvevo_utesek
    er.lejatszas_teljes = (utes_szam == 13)


# --- Teljes parti -----------------------------------------------------

def visszajatszik(leosztas: Leosztas, licitek: list[dict] | None,
                  lapok: list[str] | None,
                  jk_kontraktus: Kontraktus | None = None,
                  jk_felvevo: str | None = None,
                  jk_utesek: int | None = None,
                  claim_utes: int | None = None) -> Eredmeny:
    """
    Egy parti teljes visszajátszása és egyeztetése a jegyzőkönyvvel.
    A `jk_*` paraméterek a jegyzőkönyv állításai (opcionálisak).
    """
    er = Eredmeny(claim_utes=claim_utes)

    try:
        leosztas.ellenorizd()
    except ValueError as e:
        er.hiba(f"Kiosztás: {e}")
        return er

    # --- Licit ---
    kontraktus = jk_kontraktus
    if licitek:
        lk, lf, hibak, fig = licit_ellenoriz(licitek, leosztas.oszto)
        er.licit_kontraktus, er.licit_felvevo = lk, lf
        for h in hibak:
            er.hiba(f"Licit: {h}")
        er.figyelmeztetesek.extend(f"Licit: {f}" for f in fig)

        if jk_kontraktus is not None and lk is not None:
            er.licit_ellenorzott = True
            if (lk.szint, lk.szin, lk.kontra) != (jk_kontraktus.szint,
                                                  jk_kontraktus.szin,
                                                  jk_kontraktus.kontra):
                er.hiba(f"Kontraktus eltér: licitből {lk}, "
                        f"jegyzőkönyv {jk_kontraktus}")
            if jk_felvevo and lf != jk_felvevo:
                er.hiba(f"Felvevő eltér: licitből {lf}, jegyzőkönyv {jk_felvevo}")
        if lk is not None:
            kontraktus = lk if jk_kontraktus is None else jk_kontraktus

    # --- Lejátszás ---
    if lapok and kontraktus is not None:
        if jk_felvevo:
            kontraktus = Kontraktus(kontraktus.szint, kontraktus.szin,
                                    kontraktus.kontra, jk_felvevo)
        lejatszas_ellenoriz(leosztas, lapok, kontraktus, er)

        if jk_utesek is not None and er.felvevo_utesek is not None:
            if er.lejatszas_teljes:
                if er.felvevo_utesek != jk_utesek:
                    er.hiba(f"Ütésszám eltér: visszajátszva "
                            f"{er.felvevo_utesek}, jegyzőkönyv {jk_utesek}")
            else:
                # Claim: a bemondott ütésszám nem lehet kevesebb a már
                # megnyerteknél, és nem több a még lehetségesnél.
                jatszott = len(er.utesek)
                maradek = 13 - jatszott
                if not (er.felvevo_utesek <= jk_utesek <=
                        er.felvevo_utesek + maradek):
                    er.hiba(f"Terítés ellentmondásos: {jatszott} ütés után "
                            f"{er.felvevo_utesek} megvan, a jegyzőkönyv "
                            f"{jk_utesek} ütést állít (max "
                            f"{er.felvevo_utesek + maradek})")
                else:
                    er.claim_utesszam = jk_utesek
    return er
