"""
Lapértékelő-ÉRTELMEZŐ.

Ez a modul NEM tartalmaz konkrét metrikákat. Egy kis deklaratív nyelvet
értelmez, amelynek DEFINÍCIÓI ADATKÉNT élnek — az `ertekelo.definicio`
oszlopban. Új metrika felvétele vagy módosítása így NEM kódmódosítás,
hanem egy adatbázissor.

    ÉRTÉK = Σ (együttható × tag_értéke)

Ami a kódban marad, az nem metrika, hanem a NYELV SZÓKINCSE: nyolc
tagtípus, amelyekből mind a tizenöt jelenlegi metrika összerakható.

TAGTÍPUSOK
----------
LAP_SULY        laponkénti súlyozás
                {"tipus":"LAP_SULY","sulyok":{"A":4,"K":3,"Q":2,"J":1}}
                Szűkíthető: "szin":"S" vagy "szin_rang":1 (hossz szerinti),
                és "min_hossz"/"max_hossz" (csak az ilyen hosszú színek)
HOSSZ_SULY      színhossz szerinti súlyozás, színenként összegezve
                {"tipus":"HOSSZ_SULY","sulyok":{"0":3,"1":2,"2":1}}
HOSSZ_TOBBLET   a küszöb feletti lapok színenként
                {"tipus":"HOSSZ_TOBBLET","felett":4,"max":3}
RENDEZETT_HOSSZ a hossz szerinti n-edik szín lapszáma
                {"tipus":"RENDEZETT_HOSSZ","rang":1}
ERTEKELO        hivatkozás MÁSIK értékelőre (körfigyeléssel)
                {"tipus":"ERTEKELO","kod":"HCP"}
SZIN_MINTA      színenként az ELSŐ illeszkedő szabály értéke
                {"tipus":"SZIN_MINTA","szabalyok":[
                    {"tart":["A","K"],"ertek":2},{"tart":["A"],"ertek":1}]}
SZIN_HIANYZO    színenként hány hiányzik a felsoroltakból (vesztőütés)
                {"tipus":"SZIN_HIANYZO","kozul":["A","K","Q"],"max_lap":3}
FELTETEL        logikai tag: 1 vagy 0 (illetve megadott értékek)
                {"tipus":"FELTETEL","bal":{...},"op":">=","jobb":2}

A definíciók KANONIKUS helye az ADATBÁZIS. A csomagban lévő
`ertekelok.json` PILLANATKÉP, hogy adatbázis nélkül (tesztek, offline
munka) is működjön minden; a bázisból bármikor újragenerálható.
"""
from __future__ import annotations

import json
from pathlib import Path

from .kartya import ERTEKELOK, Kez, SZINEK

PILLANATKEP = Path(__file__).with_name("ertekelok.json")


class ErtekeloHiba(ValueError):
    pass


# --- Tagok kiértékelése ----------------------------------------------

def _rendezett_szinek(kez: Kez) -> list[str]:
    """A színek hossz szerint csökkenően; azonos hossznál a szín rangja dönt."""
    return sorted(SZINEK, key=lambda sz: (-kez.hossz(sz), SZINEK.index(sz)))


def _lapok(kez: Kez, szin: str) -> set[str]:
    return {l.ertek for l in kez.lapok if l.szin == szin}


def _tag(t: dict, kez: Kez, tar: "Ertekelotar", lanc: tuple[str, ...]) -> float:
    tipus = t.get("tipus")

    if tipus == "LAP_SULY":
        sulyok = t["sulyok"]
        if "szin" in t:
            szinek = {t["szin"]}
        elif "szin_rang" in t:
            szinek = {_rendezett_szinek(kez)[int(t["szin_rang"]) - 1]}
        else:
            szinek = set(SZINEK)
        # Hossz szerinti szűkítés: csak a min_hossz..max_hossz lapos színek
        # (pl. "figurapont a rövid színekben": max_hossz 3).
        if "min_hossz" in t:
            szinek = {sz for sz in szinek if kez.hossz(sz) >= int(t["min_hossz"])}
        if "max_hossz" in t:
            szinek = {sz for sz in szinek if kez.hossz(sz) <= int(t["max_hossz"])}
        return float(sum(sulyok.get(l.ertek, 0)
                         for l in kez.lapok if l.szin in szinek))

    if tipus == "HOSSZ_SULY":
        sulyok = t["sulyok"]
        return float(sum(sulyok.get(str(h), 0) for h in kez.hosszak))

    if tipus == "HOSSZ_TOBBLET":
        felett = int(t.get("felett", 4))
        felso = t.get("max")
        ossz = 0.0
        for h in kez.hosszak:
            tobblet = max(0, h - felett)
            if felso is not None:
                tobblet = min(tobblet, int(felso))
            ossz += tobblet
        return ossz

    if tipus == "RENDEZETT_HOSSZ":
        return float(sorted(kez.hosszak, reverse=True)[int(t["rang"]) - 1])

    if tipus == "ERTEKELO":
        return tar.ertek(t["kod"], kez, lanc)

    if tipus == "SZIN_MINTA":
        ossz = 0.0
        for szin in SZINEK:
            lapok = _lapok(kez, szin)
            hossz = len(lapok)
            for sz in t["szabalyok"]:
                if hossz < int(sz.get("min_hossz", 0)):
                    continue
                if "max_hossz" in sz and hossz > int(sz["max_hossz"]):
                    continue
                if not set(sz.get("tart", [])) <= lapok:
                    continue
                if set(sz.get("nincs", [])) & lapok:
                    continue
                ossz += float(sz["ertek"])
                break
        return ossz

    if tipus == "SZIN_HIANYZO":
        kozul = list(t.get("kozul", ["A", "K", "Q"]))
        max_lap = int(t.get("max_lap", 3))
        ossz = 0
        for szin in SZINEK:
            lapok = _lapok(kez, szin)
            vizsgalt = min(max_lap, len(lapok))
            ossz += sum(1 for e in kozul[:vizsgalt] if e not in lapok)
        return float(ossz)

    if tipus == "FELTETEL":
        bal = _tag(t["bal"], kez, tar, lanc)
        jobb = (_tag(t["jobb"], kez, tar, lanc)
                if isinstance(t.get("jobb"), dict) else float(t.get("jobb", 0)))
        op = t.get("op", ">=")
        ok = {">=": bal >= jobb, "<=": bal <= jobb, ">": bal > jobb,
              "<": bal < jobb, "=": bal == jobb}.get(op)
        if ok is None:
            raise ErtekeloHiba(f"Ismeretlen operátor: {op!r}")
        return float(t.get("akkor", 1) if ok else t.get("kulonben", 0))

    raise ErtekeloHiba(f"Ismeretlen tagtípus: {tipus!r}")


# --- Az értékelő-tár --------------------------------------------------

class Ertekelotar:
    """
    A definíciók tára. A `regisztral()` beteszi a függvényeket az
    ERTEKELOK szótárba, így a kritérium-motor és a kifejezésfa
    változtatás nélkül látja őket.
    """

    def __init__(self, definiciok: dict[str, dict] | None = None):
        self.definiciok: dict[str, dict] = dict(definiciok or {})

    def betolt_json(self, ut: Path | str) -> "Ertekelotar":
        self.definiciok.update(
            json.loads(Path(ut).read_text(encoding="utf-8")))
        return self

    def ertek(self, kod: str, kez: Kez, lanc: tuple[str, ...] = ()) -> float:
        if kod in lanc:
            raise ErtekeloHiba(
                f"Körkörös hivatkozás: {' -> '.join(lanc)} -> {kod}")
        d = self.definiciok.get(kod)
        if d is None:
            raise ErtekeloHiba(f"Nincs ilyen értékelő: {kod!r}")
        ossz = 0.0
        for t in d.get("tagok", []):
            ossz += float(t.get("egyutthato", 1)) * _tag(t, kez, self,
                                                         lanc + (kod,))
        if d.get("kerekites") is not None:
            ossz = round(ossz, int(d["kerekites"]))
        return ossz

    def fuggveny(self, kod: str):
        def f(kez: Kez, _kod=kod) -> float:
            return self.ertek(_kod, kez)
        f.__name__ = f"ert_{kod.lower()}"
        f.__doc__ = self.definiciok.get(kod, {}).get("leiras", "")
        return f

    def regisztral(self, kizarolagos: bool = True) -> int:
        """
        A definíciók bejegyzése az ERTEKELOK szótárba.
        `kizarolagos`: a szótárból eltávolítja azt, aminek nincs
        definíciója — így a definíciós tár az EGYETLEN igazságforrás.
        """
        for kod in self.definiciok:
            ERTEKELOK[kod] = self.fuggveny(kod)
        if kizarolagos:
            for kod in list(ERTEKELOK):
                if kod not in self.definiciok:
                    del ERTEKELOK[kod]
        return len(self.definiciok)

    def ellenoriz(self) -> list[str]:
        """Hibalista: hiányzó hivatkozások, körök, ismeretlen tagtípusok."""
        hibak: list[str] = []
        proba = Kez.pbn_bol("AKQ32.AK54.765.32")
        for kod in self.definiciok:
            try:
                self.ertek(kod, proba)
            except ErtekeloHiba as e:
                hibak.append(f"{kod}: {e}")
        return hibak


# --- Alapértelmezett betöltés ----------------------------------------

TAR = Ertekelotar()
if PILLANATKEP.is_file():
    TAR.betolt_json(PILLANATKEP).regisztral()


def betolt_adatbazisbol(conn, kizarolagos: bool = True) -> int:
    """
    A definíciók betöltése az `ertekelo` táblából — EZ A KANONIKUS FORRÁS.
    A JSON-pillanatkép csak akkor számít, ha nincs adatbázis.
    """
    cur = conn.cursor()
    cur.execute("SELECT kod, definicio FROM ertekelo"
                " WHERE aktiv=1 AND definicio IS NOT NULL")
    TAR.definiciok = {kod: (json.loads(d) if isinstance(d, str) else d)
                      for kod, d in cur.fetchall()}
    return TAR.regisztral(kizarolagos)


def export_json(ut: Path | str = PILLANATKEP) -> int:
    """A pillanatkép frissítése a jelenlegi definíciókból."""
    Path(ut).write_text(
        json.dumps(TAR.definiciok, ensure_ascii=False, indent=1,
                   sort_keys=True), encoding="utf-8")
    return len(TAR.definiciok)
