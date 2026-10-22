"""
ARANYKÉSZLET — a kibic döntéseinek rögzítése és összevetése (a terv 0. fázisa,
doc/terv-elvsablonok-2026-10-04.md).

MIÉRT: ha a kibic belsejét átépítjük (elvek adattá tétele, paraméterek), a
licitjének NEM szabad észrevétlenül megváltoznia. Ehhez egy rögzített
döntéskészlet kell: kéz + menet-előtag → licit. Minden változtatás után
ugyanezeket a helyzeteket újra lefuttatjuk, és tételesen kiírjuk, hol
licitál mást — ami eltér, az vagy szándékos (és jóváhagyjuk), vagy hiba.

A döntéspontokat EGYENKÉNT vetjük össze, a rögzített előtagon: ha egy korai
licit megváltozik, az nem görgeti tovább a különbséget a menet végéig — a
későbbi pontok a régi menetben maradnak, így egy hiba egy sor a jelentésben.

    # az alap rögzítése (300 generált leosztás, rögzített maggal)
    python -m kibic.cli.aranykeszlet rogzit --rendszer KIBIC_STAND \
        --leosztas 300 --mag 1 --ki adat/arany/KIBIC_STAND.jsonl

    # egy változtatás után: hol licitál mást?
    python -m kibic.cli.aranykeszlet osszevet --be adat/arany/KIBIC_STAND.jsonl

DETERMINIZMUS: a kizárásos következtetés időkeretben fut (a gép terhelésétől
függ, meddig jut), ezért az aranykészlet alapból NÉLKÜLE fut; a
`--kovetkeztetes` kapcsolóval bekapcsolható (bőséges időkerettel). A
szimuláció (DD) itt nem fut.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ULESEK = "NESW"
SZINEK = "SHDC"
RANGOK = "AKQJT98765432"
# a szokásos zóna-ciklus (1-16. leosztás)
ZONAK = ["none", "ns", "ew", "both", "ns", "ew", "both", "none",
         "ew", "both", "none", "ns", "both", "none", "ns", "ew"]


# --- leosztás és menet ----------------------------------------------------

def leosztas(mag: int, sorszam: int) -> dict[str, list[str]]:
    """Egy rögzített magú véletlen leosztás: {ülés: ["SA", "HK", …]}."""
    lapok = [sz + r for sz in SZINEK for r in RANGOK]
    random.Random(mag * 1_000_003 + sorszam).shuffle(lapok)
    return {u: lapok[13 * i:13 * (i + 1)] for i, u in enumerate(ULESEK)}


def pbn(kez: list[str]) -> str:
    return ".".join("".join(r for r in RANGOK if sz + r in kez) for sz in SZINEK)


def kez_pbnbol(s: str) -> list[str]:
    return [sz + r for sz, lapok in zip(SZINEK, s.split(".")) for r in lapok]


def vege(menet: list[str]) -> bool:
    """Vége a licitnek: négy passz, vagy egy licit után három."""
    if len(menet) == 4 and all(h == "P" for h in menet):
        return True
    return len(menet) >= 4 and any(h != "P" for h in menet) and \
        all(h == "P" for h in menet[-3:])


def _keres(kez, ules, oszto, zona, menet, rendszer, kovetkeztetes: bool,
           arnyek: list[str] | None = None) -> dict:
    k = {"hand": kez, "seat": ules, "dealer": oszto, "vulnerability": zona,
         "auction": list(menet), "system": rendszer, "test_mode": True,
         "shadow": list(arnyek or [])}
    if not kovetkeztetes:
        k["inference"] = False
    else:
        k["inference_ms"] = 60000
    return k


def dontes(betolto, kez, ules, oszto, zona, menet, rendszer,
           kovetkeztetes: bool = False, arnyek: str | None = None) -> dict:
    """
    Egy döntés: {call, source, explanation} — a hiba is döntés (rögzítjük).
    `arnyek`: egy árnyék-döntéshozó neve — ilyenkor AZ adja a hívást (ha
    illetékes; különben a régi), hogy az aranykészleten mérhető legyen.
    """
    from ..szolgaltatas.licit import LicitHiba, licit_elemzes, szabalyos_hivasok, _menet
    try:
        v = licit_elemzes(_keres(kez, ules, oszto, zona, menet, rendszer, kovetkeztetes,
                                 [arnyek] if arnyek else None),
                          betolto)
    except LicitHiba as e:
        return {"call": "P", "source": "HIBA", "explanation": str(e)}
    except Exception as e:                       # noqa: BLE001 — az eszköz ne álljon meg
        return {"call": "P", "source": "HIBA", "explanation": f"{type(e).__name__}: {e}"}
    hivas = v.get("call") or "P"
    if arnyek:
        for a in v.get("shadow") or []:
            if a.get("name") == arnyek and a.get("call"):
                hivas = a["call"]
                v = dict(v, source=f"ARNYEK:{arnyek}")
    legalis = szabalyos_hivasok(_menet(menet, oszto), ules)
    if hivas not in legalis:
        hivas = "P"
    return {"call": hivas, "source": v.get("source"),
            "explanation": (v.get("explanation") or "")[:200]}


# --- betöltés ---------------------------------------------------------------

def yaml_betolto(utak: list[str]):
    """A rendszerek a YAML-forrásból (adatbázis nélkül), gyorsítótárazva."""
    from ..impex.rendszer_yaml import betolt
    from ..motor.kriterium import Parametertar
    from ..motor.rendszercheck import feloldas_forrasokbol
    g = betolt([Path(u) for u in utak])
    tar: dict = {}

    def b(kod, par=None, teszt=None):
        if kod not in tar:
            tar[kod] = feloldas_forrasokbol(g, kod)[0].sorok
        return tar[kod], Parametertar()
    return b


# --- rögzítés és összevetés --------------------------------------------------

def _hcp(kez: list[str]) -> int:
    return sum({"A": 4, "K": 3, "Q": 2, "J": 1}.get(l[1], 0) for l in kez)


def elotag_parse(s: str | None) -> list[set[str]] | None:
    """"1H|1S,P,2C|2D,P" -> pozíciónként a megengedett hívások."""
    if not s:
        return None
    return [set(x.strip().upper().split("|")) for x in s.split(",") if x.strip()]


def rogzit(betolto, rendszer: str, db: int, mag: int, kovetkeztetes: bool = False,
           max_licit: int = 40, elotag: list[set[str]] | None = None,
           min_hcp: dict[str, int] | None = None, egyezo: str | None = None):
    """
    Generátor: a döntéspontok sorban (dict-ek).

    CÉLZOTT KÉSZLET (2026-10-05): `elotag` — pozíciónként a megengedett
    hívások (az osztó ilyenkor mindig É); csak azok a leosztások kerülnek
    be, amelyeknek a licitmenete így kezdődik (a menet közben, ahogy
    eltér, abbamarad). `min_hcp` ({"N": 11, "S": 11}): olcsó előszűrés.
    `egyezo` (pl. "0,4"): ezeken a pozíciókon ugyanaz a szín (1M … 2M).
    """
    for i in range(db):
        kezek = leosztas(mag, i)
        if min_hcp and any(_hcp(kezek[u]) < n for u, n in min_hcp.items()):
            continue
        oszto = "N" if elotag else ULESEK[i % 4]
        zona = ZONAK[i % 16]
        menet: list[str] = []
        sorok: list[dict] = []
        ules = oszto
        jo = True
        while not vege(menet) and len(menet) < max_licit:
            d = dontes(betolto, kezek[ules], ules, oszto, zona, menet, rendszer,
                       kovetkeztetes)
            sor = {"deal": i, "dealer": oszto, "vul": zona, "seat": ules,
                   "hand": pbn(kezek[ules]), "auction": list(menet), **d}
            if elotag:
                k = len(menet)
                if k < len(elotag) and d["call"] not in elotag[k]:
                    jo = False
                    break
                sorok.append(sor)
            else:
                yield sor
            menet.append(d["call"])
            ules = ULESEK[(ULESEK.index(ules) + 1) % 4]
        if elotag and jo and len(menet) >= len(elotag):
            if egyezo:
                poz = [int(x) for x in egyezo.split(",")]
                if len({menet[p_][1:] for p_ in poz}) != 1:
                    continue
            yield from sorok


def osszevet(betolto, sorok, rendszer: str, kovetkeztetes: bool = False,
             arnyek: str | None = None):
    """Generátor: minden döntéspont újra; (régi sor, új döntés, egyezik-e)."""
    for s in sorok:
        uj = dontes(betolto, kez_pbnbol(s["hand"]), s["seat"], s["dealer"], s["vul"],
                    s["auction"], rendszer, kovetkeztetes, arnyek)
        yield s, uj, uj["call"] == s["call"]


def jatszma(betolto, kezek: dict, oszto: str, zona: str, rendszer: str,
            kovetkeztetes: bool = False, max_licit: int = 40) -> list[str]:
    """Egy leosztás teljes licitmenete a megadott rendszerrel."""
    menet: list[str] = []
    ules = oszto
    while not vege(menet) and len(menet) < max_licit:
        d = dontes(betolto, kezek[ules], ules, oszto, zona, menet, rendszer, kovetkeztetes)
        menet.append(d["call"])
        ules = ULESEK[(ULESEK.index(ules) + 1) % 4]
    return menet


_SZ = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}


def _szep(c: str) -> str:
    if c == "P":
        return "–"
    if c in ("X", "XX"):
        return c
    return c[:-2] + "NT" if c.endswith("NT") else c[0] + _SZ.get(c[1:], c[1:])


def _kez_szep(k: list[str]) -> str:
    p = pbn(k).replace("T", "10").split(".")
    return " ".join(_SZ[s] + (x or "—") for s, x in zip("SHDC", p))


def teljes_jelentes(betolto, fej: dict, sorok: list[dict], rendszer: str,
                    kovetkeztetes: bool = False, csak: set | None = None) -> str:
    """
    TELJES ÚJRAJÁTSZÁS (2026-10-05): a pontonkénti összevetés a RÉGI menet-
    előtagon dönt — a későbbi pontok így néha olyan helyzetből indulnak,
    amibe az új rendszer el sem jutna. Itt minden érintett leosztást az új
    rendszerrel végiglicitálunk, és a két teljes menetet a négy lappal
    együtt mutatjuk (Markdown).
    """
    mag = int(fej.get("mag", 1))
    leosztasok: dict[int, dict] = {}
    for s in sorok:
        leosztasok.setdefault(s["deal"], s)
    regi_menet: dict[int, list[str]] = {}
    for s in sorok:
        m = list(s["auction"]) + [s["call"]]
        if len(m) > len(regi_menet.get(s["deal"], [])):
            regi_menet[s["deal"]] = m
    ki = []
    for i, s in sorted(leosztasok.items()):
        if csak is not None and i not in csak:
            continue
        kezek = leosztas(mag, i)
        uj = jatszma(betolto, kezek, s["dealer"], s["vul"], rendszer, kovetkeztetes)
        regi = regi_menet[i]
        if uj == regi:
            continue
        sorrend = [ULESEK[(ULESEK.index(s["dealer"]) + k) % 4] for k in range(4)]
        ki += [f"### {i}. leosztás — oszt: {s['dealer']}, zóna: {s['vul']}", ""]
        ki += [f"- **{u}**: {_kez_szep(kezek[u])} ({_hcp(kezek[u])})" for u in "NESW"]
        ki += ["", "```", "        " + "".join(f"{u:<7}" for u in sorrend)]
        for nev, m in (("régi", regi), ("új", uj)):
            for k in range(0, len(m), 4):
                cim = nev if k == 0 else ""
                ki.append(f"{cim:<8}" + "".join(f"{_szep(x):<7}" for x in m[k:k + 4]).rstrip())
        ki.append("```")
        ki.append("")
    return "\n".join(ki)


def _olvas(ut: str) -> tuple[dict, list[dict]]:
    fej, sorok = {}, []
    with open(ut, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            d = json.loads(ln)
            if d.get("_fej"):
                fej = d
            else:
                sorok.append(d)
    return fej, sorok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A kibic aranykészlete: rögzítés és összevetés")
    al = ap.add_subparsers(dest="parancs", required=True)
    r = al.add_parser("rogzit", help="az alap rögzítése")
    r.add_argument("--rendszer", default="KIBIC_STAND")
    r.add_argument("--leosztas", type=int, default=300)
    r.add_argument("--mag", type=int, default=1)
    r.add_argument("--ki", required=True)
    r.add_argument("--kovetkeztetes", action="store_true",
                   help="a kizárásos következtetéssel (lassabb)")
    r.add_argument("--elotag", default=None,
                   help='célzott készlet: pozíciónként a megengedett hívások, pl. '
                        '"1H|1S,P,2C|2D,P,2H|2S,P" (az osztó É)')
    r.add_argument("--egyezo", default=None,
                   help='ezeken a pozíciókon azonos szín, pl. "0,4" (1M … 2M)')
    r.add_argument("--min-hcp", default=None,
                   help='olcsó előszűrés, pl. "N:11,S:11"')
    o = al.add_parser("osszevet", help="hol licitál mást a mostani kibic?")
    o.add_argument("--be", required=True)
    o.add_argument("--rendszer", default=None, help="alap: a rögzítéskori")
    o.add_argument("--max", type=int, default=40, help="ennyi eltérést ír ki részletesen")
    o.add_argument("--json", default=None, help="az eltérések JSONL-be")
    o.add_argument("--arnyek", default=None,
                   help="egy árnyék-döntéshozó neve: azt veti össze az alappal")
    o.add_argument("--teljes", default=None,
                   help="Markdown-fájl: az eltérő leosztások teljes újrajátszása a négy lappal")
    for p in (r, o):
        p.add_argument("--yaml", nargs="*", default=["rendszerek/yaml"],
                       help="a rendszer-YAML könyvtár(ak)")
    a = ap.parse_args(argv)
    betolto = yaml_betolto(a.yaml)

    if a.parancs == "rogzit":
        Path(a.ki).parent.mkdir(parents=True, exist_ok=True)
        t0, n = time.time(), 0
        with open(a.ki, "w", encoding="utf-8") as f:
            f.write(json.dumps({"_fej": True, "rendszer": a.rendszer, "mag": a.mag,
                                "leosztas": a.leosztas, "kovetkeztetes": a.kovetkeztetes,
                                "elotag": a.elotag, "egyezo": a.egyezo, "min_hcp": a.min_hcp,
                                "rogzitve": time.strftime("%Y-%m-%dT%H:%M:%S")},
                               ensure_ascii=False) + "\n")
            mh = ({x.split(":")[0]: int(x.split(":")[1]) for x in a.min_hcp.split(",")}
                  if a.min_hcp else None)
            for s in rogzit(betolto, a.rendszer, a.leosztas, a.mag, a.kovetkeztetes,
                            elotag=elotag_parse(a.elotag), min_hcp=mh, egyezo=a.egyezo):
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
                n += 1
        print(f"{n} döntéspont, {a.leosztas} leosztás, {time.time() - t0:.0f} s → {a.ki}")
        return 0

    fej, sorok = _olvas(a.be)
    rendszer = a.rendszer or fej.get("rendszer") or "KIBIC_STAND"
    kov = bool(fej.get("kovetkeztetes"))
    elteresek = []
    t0 = time.time()
    for s, uj, ok in osszevet(betolto, sorok, rendszer, kov, a.arnyek):
        if not ok:
            elteresek.append((s, uj))
    print(f"{len(sorok)} döntéspont, {len(elteresek)} eltérés "
          f"({time.time() - t0:.0f} s; rendszer: {rendszer}, rögzítve: {fej.get('rogzitve')})")
    for s, uj in elteresek[:a.max]:
        menet = " ".join(s["auction"]) or "—"
        print(f"  #{s['deal']} {s['seat']} [{menet}] {s['hand']}: "
              f"{s['call']} ({s['source']}) → {uj['call']} ({uj['source']})")
        print(f"      most: {uj['explanation']}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            for s, uj in elteresek:
                f.write(json.dumps({"regi": s, "uj": uj}, ensure_ascii=False) + "\n")
    if a.teljes:
        csak = {s["deal"] for s, _ in elteresek}
        md = teljes_jelentes(betolto, fej, sorok, rendszer, kov, csak)
        Path(a.teljes).write_text(md + "\n", encoding="utf-8")
        print(f"teljes újrajátszás: {a.teljes}")
    return 1 if elteresek else 0


if __name__ == "__main__":
    sys.exit(main())
