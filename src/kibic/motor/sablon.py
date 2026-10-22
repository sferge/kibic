"""
ELV-SABLON PÉLDÁNYOSÍTÁSA (a terv 3. lépése, doc/terv-elvsablonok-2026-10-04.md).

Egy ELV-sablon (fajta: ELV_SABLON) olyan konvenció, amelynek a szabályai
ÁLTALÁNOS mintájúak (`.. +A`, `.. 3NT`), a feltételeiben pedig
helyőrzők állnak a paraméterei helyén (`{sablon: FIT_MIN}`). Egy rendszer
úgy játssza, hogy hivatkozik rá — és a hivatkozás mondja meg, HOL él
(`ervenyes`: minták, amelyek után) és MILYEN paraméterekkel:

    hivatkozasok:
      - {kod: FOGASMUTATAS, ervenyes: ["1M-2m-2M"], parameterek: {FIT_MIN: 8}}

A feloldáskor (motor/feloldas.py) a sablon sorai így másolódnak a
rendszerbe:
  * a helyőrzők helyére a paraméter értéke kerül (a hivatkozás felülírása,
    különben a sablon alapértéke);
  * a helyzeti feltétel kiegészül az érvényességi helyzettel
    (ELV_KONTEXTUS: a vonal licitmenete ezek valamelyikével kezdődik).

Ugyanaz a sablon több helyen, más-más paraméterrel is példányosítható —
nem kell szabálykészletet másolni.
"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace


def ertekek(sablon_def: dict | None, beallitas: dict | None) -> dict:
    """A paraméterek tényleges értékei: az alapérték, a hivatkozás felülírásával."""
    ki = {k: v.get("alap") for k, v in ((sablon_def or {}).get("parameterek") or {}).items()}
    ki.update((beallitas or {}).get("parameterek") or {})
    return ki


def behelyettesit(x, ert: dict):
    """A `{"sablon": KOD}` helyőrzők cseréje az értékre (mélyen, másolatban)."""
    if isinstance(x, dict):
        if set(x) == {"sablon"}:
            kod = str(x["sablon"])
            if kod not in ert:
                raise KeyError(f"ismeretlen sablon-paraméter: {kod}")
            return deepcopy(ert[kod])
        return {k: behelyettesit(v, ert) for k, v in x.items()}
    if isinstance(x, list):
        return [behelyettesit(v, ert) for v in x]
    return x


def _szovegben(v) -> str:
    if v is True:
        return "igen"
    if v is False:
        return "nem"
    return str(v)


def _es(a: dict | None, b: dict) -> dict:
    if a is None:
        return b
    if a.get("t") == "ES":
        return {"t": "ES", "gy": list(a["gy"]) + [b]}
    return {"t": "ES", "gy": [a, b]}


def peldanyosit(sorok: list, sablon_def: dict | None, beallitas: dict | None) -> list:
    """A sablon sorainak példánya (új Sor-objektumok; az eredetiek érintetlenek)."""
    ert = ertekek(sablon_def, beallitas)
    ervenyes = list((beallitas or {}).get("ervenyes") or [])
    ki = []
    for s in sorok:
        uj = replace(s)
        uj.feltetel = behelyettesit(s.feltetel, ert)
        if getattr(s, "feltetel_szoveg", None):
            szoveg = s.feltetel_szoveg
            for k, v in ert.items():
                szoveg = szoveg.replace("{" + k + "}", _szovegben(v))
            uj.feltetel_szoveg = szoveg
        uj.jelentes = behelyettesit(s.jelentes, ert)
        ha = behelyettesit(s.ha_feltetel, ert)
        if ervenyes:
            ha = _es(ha, {"t": "ELV_KONTEXTUS", "mintak": ervenyes})
            hol = " / ".join(ervenyes) + " után"
            uj.ha_feltetel_szoveg = (f"{s.ha_feltetel_szoveg} és {hol}"
                                     if getattr(s, "ha_feltetel_szoveg", None) else hol)
        uj.ha_feltetel = ha
        ki.append(uj)
    return ki


def terulet(sablon_def: dict | None, beallitas: dict | None) -> dict | None:
    """
    A példány TERÜLETE (helyzeti fa), ha az elv kiváltja a kártyán mögötte
    álló sorokat: a sablon `terulet`-e a paraméterekkel, az érvényességi
    helyzettel kiegészítve. None, ha nincs területe, vagy a hivatkozás
    `kivalt: false`.
    """
    t = (sablon_def or {}).get("terulet")
    if not t or (beallitas or {}).get("kivalt") is False:
        return None
    t = behelyettesit(t, ertekek(sablon_def, beallitas))
    ervenyes = list((beallitas or {}).get("ervenyes") or [])
    if ervenyes:
        t = _es(t, {"t": "ELV_KONTEXTUS", "mintak": ervenyes})
    return t


def beallitas_kulcs(beallitas: dict | None) -> str:
    """Egy példány azonosítója a bejáráshoz (ugyanaz a sablon, más helyen)."""
    return json.dumps(beallitas or {}, sort_keys=True, ensure_ascii=False)
