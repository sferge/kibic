"""
KONVENCIÓKÁRTYA — a WBF-kártya szerkezetében, a rendszer adataiból.

A kártya két forrásból áll:

  * GENERÁLT rész — a (feloldott) licitszabályokból: a nyitások táblázata
    (nyitás, mesterséges-e, minimális hossz, negatív kontra meddig, leírás,
    válaszok, a folytatás konvenciói, passzolt kéz), a védekező és küzdelmi
    licitek, a használt konvenciók. Ez mindig naprakész: ha a rendszer
    változik, a kártya is.

  * KÉZZEL ÍRT rész — a rendszer YAML-jának `kartya:` blokkjából (az
    adatbázisban a `rendszer.kartya` oszlop): indulások, jelzések,
    általános stílus, kényszerítő passzok, pszichik. Ezek nincsenek a
    licitszabályokban.

A kártya a MEGÁLLAPODÁST írja le — kéz nem kell hozzá, és nem is kerül
bele; bárki elkérheti az asztalnál (`/v1/bridge/card`).
"""
from __future__ import annotations

import html
import re
from collections import OrderedDict
from pathlib import Path

from .minta import MintaHiba, minta_parse

SZIMBOLUM = {"C": "♣", "D": "♦", "H": "♥", "S": "♠"}
SZIN_NEV = {"C": "treff", "D": "káró", "H": "kőr", "S": "pikk"}
RANG = {"C": 0, "D": 1, "H": 2, "S": 3, "NT": 4}
NYITASI_SORREND = [f"{sz}{s}" for sz in range(1, 8) for s in ("C", "D", "H", "S", "NT")]


def szep(szoveg: str | None) -> str:
    """'1NT-2C', '(1S) 2H' -> '1NT–2♣', '(1♠) 2♥' (a változókat hagyja)."""
    if not szoveg:
        return ""
    s = re.sub(r"(?<![A-Za-z])([1-7])(C|D|H|S)(?![A-Za-z])",
               lambda m: m.group(1) + SZIMBOLUM[m.group(2)], szoveg)
    s = re.sub(r"(?<![A-Za-z])([1-7])N(?!T)", r"\1NT", s)
    return s.replace("-", "–")


def _rovid(szoveg: str | None, n: int = 90) -> str:
    s = (szoveg or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _licit_rang(licit: str) -> tuple[int, int]:
    if not licit or licit[0] not in "1234567":
        return (9, 9)
    return (int(licit[0]), RANG.get(licit[1:], 9))


# --- A nyitások táblázata ---------------------------------------------

def _elso_illik(t, nyitas: str) -> dict | None:
    """Illik-e a minta első tokenje a nyitásra? Visszaadja a kötést."""
    if t.ellenfel or t.hivas or t.szint != nyitas[0]:
        return None
    szin = nyitas[1:]
    if t.szin == szin:
        return {}
    if t.szin == "M" and szin in ("H", "S"):
        return {"M": szin}
    if t.szin == "m" and szin in ("C", "D"):
        return {"m": szin}
    return None


def _token_szoveg(t, kotes: dict) -> str:
    """Egy mintatoken megjelenítése a kötött színnel ('2M' -> '2♥')."""
    if t.hivas:
        return t.hivas
    sz = t.szin
    if sz in kotes:
        sz = kotes[sz]
    elif sz == "oM" and "M" in kotes:
        sz = "S" if kotes["M"] == "H" else "H"
    elif sz == "om" and "m" in kotes:
        sz = "D" if kotes["m"] == "C" else "C"
    return f"{t.szint}{SZIMBOLUM.get(sz, sz)}" if sz != "NT" else f"{t.szint}NT"


def _passzolt_kezes(sor) -> bool:
    """Csak passzolt kézzel (1-2. ülésben válaszolva) érvényes szabály (pl. Drury)."""
    ha = getattr(sor, "ha_feltetel", None) or {}
    return ha.get("t") == "ULES" and set(ha.get("ertek") or []) <= {1, 2}


def _mert_min_hossz(sorok_ny, szin: str, db: int = 4000) -> int:
    """A nyitás-feltételt teljesítő véletlen kezekben a szín legrövidebb hossza."""
    import random
    from ..domain import Kez, Lap
    from ..domain.kartya import LAPOK
    from .kifejezes import Kontextus, kiertekel
    pakli = [Lap(sz, e) for sz in "SHDC" for e in LAPOK]
    rnd = random.Random(7)
    legkisebb = 13
    talalt = 0
    for _ in range(db * 10):
        k = Kez(frozenset(rnd.sample(pakli, 13)))
        if any(kiertekel(s.feltetel, k, Kontextus()) is True
               for s in sorok_ny if s.feltetel):
            talalt += 1
            legkisebb = min(legkisebb, k.hossz(szin))
            if talalt >= db:
                break
    return legkisebb if talalt else 0


def nyitasok(sorok, prop=None, konv_nev: dict | None = None,
             alap: set | None = None) -> list[dict]:
    konv_nev = konv_nev or {}
    alap = alap or set()
    elemzett = []
    for s in sorok:
        if getattr(s, "szabaly_fajta", "SZABALY") == "ELV":
            continue
        try:
            m = minta_parse(s.minta)
        except MintaHiba:
            continue
        elemzett.append((m, s))

    ki: list[dict] = []
    nyito_sorok = {}
    for m, s in elemzett:
        if m.paroslicit and len(m.tokenek) == 1 and m.tokenek[0].szint \
                and m.tokenek[0].szin in RANG and not m.tokenek[0].hivas:
            nyito_sorok.setdefault(str(m.tokenek[0]), []).append(s)

    for nyitas in NYITASI_SORREND:
        sorok_ny = nyito_sorok.get(nyitas)
        if not sorok_ny:
            continue
        fo = max(sorok_ny, key=lambda x: x.prioritas or 0)
        tetel: dict = {"opening": nyitas, "label": szep(nyitas),
                       "artificial": any(getattr(x, "alert", False) for x in sorok_ny),
                       "description": _rovid(fo.magyarazat or fo.feltetel_szoveg, 140),
                       "system": fo.rendszer_kod}
        # pontsáv és minimális hossz a jelentésből (kéz nélkül)
        if prop is not None:
            parok = prop.jelentes_sorokkal([], "N", nyitas, None, "N")
            if parok:
                from .propagal import egyesit
                ig = egyesit([ig for _, ig in parok])
                if ig.pont_min > 0 or ig.pont_max < 40:
                    tetel["points"] = [int(ig.pont_min), int(ig.pont_max)]
                szin = nyitas[1:]
                if szin in SZIMBOLUM:
                    tetel["min_length"] = ig.hossz(szin)[0]
                    if tetel["min_length"] == 0 and not tetel["artificial"]:
                        # A jelentés nem mondja ki (pl. "a hosszabb minor"):
                        # a feltételt teljesítő kezekből mérjük meg.
                        tetel["min_length"] = _mert_min_hossz(sorok_ny, szin)

        valaszok: "OrderedDict[str, dict]" = OrderedDict()
        passzolt: list[str] = []
        folytatas: set[str] = set()
        neg_kontra_max = None
        for m, s in elemzett:
            t = m.tokenek
            if not t:
                continue
            kotes = _elso_illik(t[0], nyitas)
            if kotes is None:
                continue
            if m.paroslicit and len(t) == 2 and not t[1].hivas:
                cimke = _token_szoveg(t[1], kotes)
                if _passzolt_kezes(s):
                    passzolt.append(f"{cimke}: {_rovid(s.magyarazat, 60)}")
                    continue
                elozo = valaszok.get(cimke)
                if elozo is None or (s.prioritas or 0) > elozo["priority"]:
                    valaszok[cimke] = {"call": cimke, "priority": s.prioritas or 0,
                                       "text": _rovid(s.magyarazat or s.feltetel_szoveg, 70),
                                       "alert": bool(getattr(s, "alert", False))}
            elif m.paroslicit and len(t) >= 3:
                if s.rendszer_kod not in alap:
                    folytatas.add(konv_nev.get(s.rendszer_kod, s.rendszer_kod))
            elif not m.paroslicit and len(t) == 3 and t[1].ellenfel \
                    and t[2].hivas == "X" and s.rendszer_kod == "NEGATIV_KONTRA":
                if t[1].szint and t[1].szin in RANG:
                    r = (int(t[1].szint), RANG[t[1].szin])
                    if neg_kontra_max is None or r > neg_kontra_max[0]:
                        neg_kontra_max = (r, f"{t[1].szint}{t[1].szin}")
        tetel["responses"] = sorted(
            valaszok.values(),
            key=lambda v: _licit_rang(v["call"].replace("♣", "C").replace("♦", "D")
                                      .replace("♥", "H").replace("♠", "S")))
        for v in tetel["responses"]:
            v.pop("priority", None)
        if passzolt:
            tetel["passed_hand"] = passzolt
        if folytatas:
            tetel["subsequent"] = sorted(folytatas)
        if neg_kontra_max:
            tetel["neg_double_through"] = szep(neg_kontra_max[1])
        ki.append(tetel)
    return ki


# --- Védekező és küzdelmi licitek -------------------------------------

_SZIN_SZO = re.compile(r"\b(treff|káró|kőr|pikk)\b")


def _normal(szoveg: str) -> str:
    """Az egymástól csak a színben eltérő szövegeket összevonjuk."""
    return _SZIN_SZO.sub("szín", szoveg or "")


def _gyujt(sorok, feltetel, n: int = 6) -> list[str]:
    ki: "OrderedDict[str, str]" = OrderedDict()
    for s in sorok:
        if not feltetel(s):
            continue
        kulcs = _normal(s.magyarazat or "")
        if not kulcs or kulcs in ki:
            continue
        ki[kulcs] = f"{szep(s.minta)}: {_rovid(s.magyarazat, 80)}"
        if len(ki) >= n:
            break
    return list(ki.values())


def versenylicit(sorok) -> dict:
    def ag(s):
        return getattr(s, "ag", None)

    def m(s):
        return s.minta

    ved = [s for s in sorok if ag(s) == "VEDEKEZO"]
    kuzd = [s for s in sorok if ag(s) == "KUZDELMI"]
    kategoriak = OrderedDict([
        ("overcalls", _gyujt(ved, lambda s: re.fullmatch(r"\(1[CDHS]\) [12][CDHS]", m(s))
                             and s.rendszer_kod not in ("GYENGE_UGRO_KOZBESZOLAS", "MICHAELS"), 3)),
        ("nt_overcall", _gyujt(ved, lambda s: re.fullmatch(r"\(1[CDHS]\)(?: P \(P\))? 1NT", m(s)), 3)),
        ("jump_overcalls", _gyujt(ved, lambda s: s.rendszer_kod == "GYENGE_UGRO_KOZBESZOLAS", 2)),
        ("takeout_double", _gyujt(ved, lambda s: re.fullmatch(r"\([123][CDHS]\)(?: P \(P\))? X", m(s)), 4)),
        ("cue_bids", _gyujt(ved, lambda s: s.rendszer_kod in ("MICHAELS", "SZOKATLAN_2NT")
                            and len(m(s).split()) == 2, 6)),
        ("vs_nt", _gyujt(ved, lambda s: m(s).startswith("(1NT)") and len(m(s).split()) == 2, 8)),
        ("vs_preempts", _gyujt(ved, lambda s: re.match(r"\([234][CDHS]\) ", m(s))
                               and len(m(s).split()) == 2, 6)),
        ("advances", _gyujt(ved, lambda s: re.fullmatch(r"\(1[CDHS]\) 1[CDHS] \(P\) \S+", m(s)), 6)),
        ("over_takeout_double", _gyujt(kuzd, lambda s: re.fullmatch(r"1[CDHS] \(X\) \S+", m(s)), 8)),
        ("after_overcall", _gyujt(kuzd, lambda s: re.fullmatch(r"1[CDHS] \([12][CDHS]\) \S+", m(s))
                                  and s.rendszer_kod != "NEGATIV_KONTRA", 6)),
        ("our_1nt_interfered", _gyujt(kuzd, lambda s: m(s).startswith("1NT (")
                                      and len(m(s).split()) == 3, 8)),
    ])
    return {k: v for k, v in kategoriak.items() if v}


# --- Indítás és jelzések (a jelzési profilból) -----------------------

# A kártya indítási táblázatának lapállásai (a WBF- és az ACBL-kártya
# mintájára). Az `x` helyére konkrét kis lapok kerülnek, a motor ezekre
# futtatja le a szabályokat: a táblázat tehát a szabályokból GENERÁLÓDIK.
INDITO_LAPALLASOK = (
    ("Sorozatok", ["AK", "AKx", "AKQx", "KQx", "KQJx", "KQxx", "QJx", "QJxx",
                   "JTx", "T9x", "T98x"]),
    ("Belső sorozatok", ["AQJx", "AJTx", "KJTx", "KT9x", "QT9x", "AT9x"]),
    ("Figura mellől", ["Kx", "Kxx", "Kxxx", "Kxxxx", "Txxx", "Txxxx"]),
    ("Figura nélkül", ["x", "xx", "xxx", "xxxx", "xxxxx"]),
)
_KISLAPOK = "765432"
_HIVAS_LAPALLASOK = ("xx", "Kxx", "Kxxx", "Kxxxx", "Kxxxxx", "xxx", "xxxx")


def _konkret(minta: str) -> str:
    kicsi = iter(c for c in _KISLAPOK if c not in minta)
    return "".join(next(kicsi) if c == "x" else c for c in minta)


def _megjelol(jelzesek, minta: str, felvetel: str, helyzet: str = "INDITAS") -> dict:
    """
    A minta (pl. "KQxx") konkrét lapokkal lefuttatva: melyik lapot hívja a
    motor. A kártyán a lapállás a minta jeleivel látszik (K D x x), a
    kiválasztott lap kiemelve; `javasolt`: a szabály még nincs jóváhagyva.
    """
    from .jelzes import lapok, szep
    konk = _konkret(minta)
    lapsor = lapok(konk)
    lap, sor = jelzesek.indito_lap(lapsor, felvetel, helyzet)
    jel = {k: ("x" if m == "x" else szep(k)) for k, m in zip(konk, minta)}
    return {"tokens": [jel[c] for c in lapsor],
            "idx": lapsor.index(lap) if lap else None,
            "javasolt": bool(sor and sor.allapot != "ELFOGADOTT"),
            "megjegyzes": sor.megjegyzes if sor else None}


def inditasi_tablazat(jelzesek) -> dict:
    """{"csoportok": [{"cim", "sorok": [{"minta", "SZIN", "SZAN"}]}], ...}"""
    csop = []
    for cim, mintak in INDITO_LAPALLASOK:
        csop.append({"cim": cim, "sorok": [
            {"minta": m, "SZIN": _megjelol(jelzesek, m, "SZIN"),
             "SZAN": _megjelol(jelzesek, m, "SZAN")} for m in mintak]})
    partner = any(s.helyzet == "PARTNER_SZINE" for s in jelzesek.sorok)
    hivas = [{"minta": m, "lap": _megjelol(jelzesek, m, "SZIN", "HIVAS")}
             for m in _HIVAS_LAPALLASOK] \
        if any(s.helyzet == "HIVAS" for s in jelzesek.sorok) else []
    return {"csoportok": csop, "hivas": hivas,
            "partner_szine": None if partner else "ugyanígy, mint a saját színben"}


RACS_NEV = {"PARTNER_INDIT": "A partner indít", "FELVEVO_HIV": "A felvevő hív",
            "DOBAS": "Első dobás", "VEDO_HIV": "Menet közben mi hívunk"}
JEL_NEV = {"KERES": "Kérés", "ATTITUD": "Attitűd", "LAPSZAM": "Lapszám",
           "MARADEK": "Maradék lapszám", "PREF": "Preferencia", "SMITH": "Smith"}
MODSZER_SZOVEG = {
    "KERES": {"KICSI": "kis lap kér", "NAGY": "nagy lap kér"},
    "LAPSZAM": {"FORDITOTT": "fordított: kicsi-nagy = páros, nagy-kicsi = páratlan",
                "STANDARD": "standard: nagy-kicsi = páros, kicsi-nagy = páratlan"},
    "LAPSZAM_ALAP": {"MARADEK": "maradék lapszám", "TELJES": "teljes lapszám"},
    "PREF": {"EGYENES": "egyenes: kis lap kéri a dobott színt, nagy nem kéri",
             "LAVINTHAL": "Lavinthal",
             "LAVINTHAL_3": "Lavinthal: kicsi = alsó, nagy = felső, közepes = semleges"},
    "SMITH": {"KICSI_POZITIV": "kis lap = jó az indítás",
              "NAGY_POZITIV": "nagy lap = jó az indítás"},
}
_MODSZER_CIM = {"KERES": "Kérés", "ATTITUD": "Attitűd", "LAPSZAM": "Lapszám",
                "LAPSZAM_ALAP": "", "PREF": "Preferencia", "SMITH": "Smith"}


def _racs_cella(e: dict) -> dict:
    return {"jel": JEL_NEV.get(e["jel"], e["jel"]) + (f" ({e['hossz']})" if e.get("hossz") else ""),
            "kulonben": JEL_NEV.get(e["kulonben"], e["kulonben"]) if e.get("kulonben") else None,
            "mikor": e.get("mikor"), "feltetelezes": bool(e.get("feltetelezes"))}


def jelzes_adat(jelzesek) -> dict:
    racs = []
    for h, nev in RACS_NEV.items():
        sor = {"helyzet": nev}
        for f in ("SZIN", "SZAN"):
            sor[f] = [_racs_cella(e) for e in (jelzesek.racs.get(h, {}).get(f) or [])]
        racs.append(sor)
    from .jelzes import esetek_szoveg
    m = jelzesek.modszer
    # a menet közbeni hívás jele(i): ennél a módszernél a hívott lapot is kiírjuk
    hivas_jel = {c["jel"] for f in (jelzesek.racs.get("VEDO_HIV") or {}).values()
                 for c in f if c["sorrend"] == 1}
    modszer = []
    for k in ("KERES", "ATTITUD", "LAPSZAM", "PREF", "SMITH"):
        hiv = jelzesek.hivas_modszer.get(k) if k in hivas_jel else None
        if k not in m and not hiv:
            continue
        reszek = []
        if k in m:
            szoveg = MODSZER_SZOVEG.get(k, {}).get(m[k], m[k])
            if k == "LAPSZAM" and m.get("LAPSZAM_ALAP"):
                szoveg += ", " + MODSZER_SZOVEG["LAPSZAM_ALAP"].get(
                    m["LAPSZAM_ALAP"], m["LAPSZAM_ALAP"])
            reszek.append(szoveg)
        if hiv:
            reszek.append("menet közbeni hívásnál " + esetek_szoveg(hiv))
        modszer.append({"cim": _MODSZER_CIM[k], "szoveg": "; ".join(reszek)})
    for nev, esetek in jelzesek.technikak.items():
        if not any(f"TECHNIKA/{nev}" in s.kulcs for s in jelzesek.sorok):
            continue                  # örökölt, de itt nem használt technika
        modszer.append({"cim": nev.replace("_", "-").lower(), "szoveg": esetek_szoveg(esetek)})
    fo = jelzesek.rendszer
    def kerdes(t):
        return (("Kivétel: " if t.get("fajta") == "KIVETEL" else "") + t["szoveg"]
                + (" (?)" if t.get("allapot") != "ELFOGADOTT" else ""))
    return {"racs": racs, "modszer": modszer,
            "elvek": [kerdes(t) for t in jelzesek.elvek if t.get("kartyan", True)],
            "kulonleges": [kerdes(t) for t in jelzesek.kulonleges if t.get("kartyan", True)],
            "licit_inditas": [kerdes(t) for t in jelzesek.licit_inditas
                              if t.get("kartyan", True)],
            "rendszer": {"code": fo.kod, "name": fo.nev} if fo else None,
            "alapja": [r.nev for r in jelzesek.alapok],
            "lanc": list(jelzesek.lanc),
            "forrasok": [x for x in dict.fromkeys(
                r.forras for r in [fo, *jelzesek.alapok] if r and r.forras)],
            "hianyzo": list(jelzesek.hianyzo)}


# --- Az egész kártya --------------------------------------------------

def kartya_adat(rendszer: dict, sorok, meta: dict | None = None,
                konvenciok: list[dict] | None = None, paramtar=None,
                jelzesek=None) -> dict:
    """
    `rendszer`: {"kod", "nev", "leiras"}; `sorok`: a feloldott szabálylista;
    `meta`: a kézzel írt `kartya:` blokk; `konvenciok`: [{"kod", "nev",
    "leiras", "fajta"}] a feloldási láncból.
    """
    from .propagal import Propagalo
    meta = dict(meta or {})
    konvenciok = konvenciok or []
    konv_nev = {k["kod"]: k.get("nev") or k["kod"] for k in konvenciok}
    alap = {k["kod"] for k in konvenciok if k.get("fajta") != "KONVENCIO"}
    alap.add(rendszer.get("kod"))
    prop = Propagalo(sorok, paramtar)
    alertek = sum(1 for s in sorok if getattr(s, "alert", False))
    return {
        "system": rendszer.get("kod"),
        "name": rendszer.get("nev") or rendszer.get("kod"),
        "description": rendszer.get("leiras"),
        "header": {k: meta.get(k) for k in ("jatekosok", "kategoria", "esemeny")
                   if meta.get(k)},
        "general": meta.get("altalanos"),
        "openings": nyitasok(sorok, prop, konv_nev, alap),
        "competitive": versenylicit(sorok),
        "conventions": [{"code": k["kod"], "name": k.get("nev") or k["kod"],
                         "summary": _rovid(re.sub(r"\s*Forrás:.*$", "",
                                                  k.get("leiras") or ""), 160)}
                        for k in konvenciok if k.get("fajta") == "KONVENCIO"],
        "leads": inditasi_tablazat(jelzesek) if jelzesek else meta.get("indulas"),
        "signals": jelzes_adat(jelzesek) if jelzesek else meta.get("jelzesek"),
        "slam": meta.get("szlem"),
        "forcing_pass": meta.get("kenyszerito_passz"),
        "psychics": meta.get("pszichik"),
        "special": meta.get("kulonleges"),
        "stats": {"rules": len(sorok), "alerts": alertek},
    }


# --- HTML (A4 fekvő, a WBF-kártya elrendezésében) --------------------

_CIM = {
    "overcalls": "Sima közbeszólás", "nt_overcall": "1NT közbeszólás",
    "jump_overcalls": "Ugró közbeszólás", "takeout_double": "Információs kontra",
    "cue_bids": "Kétszínű licitek (Michaels, szokatlan szan)",
    "vs_nt": "Az ellenfél 1NT nyitása ellen", "vs_preempts": "Blokknyitások ellen",
    "advances": "Válasz a közbeszólásra",
    "over_takeout_double": "Nyitásunk után, az ellenfél kontrája",
    "after_overcall": "Nyitásunk után, az ellenfél közbeszólása",
    "our_1nt_interfered": "1NT nyitásunk után közbeszólás",
}

_CSS = """
@page { size: A4 landscape; margin: 8mm; }
* { box-sizing: border-box; }
body { font: 9.5px/1.3 "DejaVu Sans", Arial, sans-serif; color: #111; margin: 0;
       background: #fff; }
.lap { width: 281mm; min-height: 190mm; margin: 0 auto 6mm; padding: 3mm;
       border: 1px solid #333; page-break-after: always; display: grid; gap: 3mm; }
.lap1 { grid-template-columns: 1fr 1fr 1fr; }
h1 { font-size: 15px; margin: 0 0 2px; } h2 { font-size: 10.5px; margin: 6px 0 2px;
  background: #222; color: #fff; padding: 1px 4px; text-transform: uppercase;
  letter-spacing: .03em; }
h3 { font-size: 9.5px; margin: 5px 0 1px; border-bottom: 1px solid #999; }
ul { margin: 0; padding-left: 12px; } li { margin: 0 0 1px; }
table { border-collapse: collapse; width: 100%; } th, td { border: 1px solid #555;
  padding: 1px 3px; vertical-align: top; text-align: left; }
th { background: #e5e5e5; font-size: 8.5px; }
.nyit { font-weight: bold; font-size: 11px; white-space: nowrap; }
.alert { color: #b00; font-weight: bold; }
.halvany { color: #777; } .fej { border: 1px solid #333; padding: 3px; }
.kicsi { font-size: 8.5px; }
.piros { color: #c00; }
.ind td { white-space: nowrap; font-family: "DejaVu Sans Mono", monospace; font-size: 8.5px; }
.ind th.csop { background: #f2f2f2; text-align: left; }
.lap-ki { font-weight: bold; text-decoration: underline; color: #000; }
.kerdes { color: #b60; font-weight: bold; }
.racs td, .racs th { text-align: center; } .racs td:first-child { text-align: left; }
@media screen { body { background: #ddd; padding: 6mm 0; } .lap { background: #fff; } }
"""


def _e(x) -> str:
    return html.escape(str(x)) if x is not None else ""


def _piros(s: str) -> str:
    """A kőr és a káró jele pirosan."""
    return s.replace("♥", '<span class="piros">♥</span>').replace(
        "♦", '<span class="piros">♦</span>')


def _szoveg_blokk(ertek) -> str:
    if not ertek:
        return '<p class="halvany">— (kitöltendő)</p>'
    if isinstance(ertek, str):
        return f"<p>{_piros(_e(ertek))}</p>"
    if isinstance(ertek, list):
        return "<ul>" + "".join(f"<li>{_piros(_e(x))}</li>" for x in ertek) + "</ul>"
    if isinstance(ertek, dict):
        return "<table>" + "".join(
            f"<tr><th>{_e(k)}</th><td>{_piros(_e(v))}</td></tr>"
            for k, v in ertek.items()) + "</table>"
    return f"<p>{_e(ertek)}</p>"


def _lapallas_html(cella: dict) -> str:
    t = []
    for i, x in enumerate(cella["tokens"]):
        x = _e(x)
        t.append(f'<span class="lap-ki">{x}</span>' if i == cella.get("idx") else x)
    ki = " ".join(t)
    if cella.get("javasolt"):
        ki += ' <span class="kerdes" title="{}">?</span>'.format(
            _e(cella.get("megjegyzes") or "még nincs jóváhagyva"))
    return ki


def _inditas_html(leads) -> str:
    if not isinstance(leads, dict) or "csoportok" not in leads:
        return _szoveg_blokk(leads)
    sorok = ["<table class=ind><tr><th>Szín ellen</th><th>Szan ellen</th></tr>"]
    for cs in leads["csoportok"]:
        sorok.append(f"<tr><th class=csop colspan=2>{_e(cs['cim'])}</th></tr>")
        for r in cs["sorok"]:
            sorok.append(f"<tr><td>{_lapallas_html(r['SZIN'])}</td>"
                         f"<td>{_lapallas_html(r['SZAN'])}</td></tr>")
    sorok.append("</table>")
    if leads.get("partner_szine"):
        sorok.append(f"<p><b>A partner színében:</b> {_e(leads['partner_szine'])}.</p>")
    if leads.get("hivas"):
        sorok.append("<p><b>Menet közbeni hívás:</b> " + ", ".join(
            _lapallas_html(h["lap"]) for h in leads["hivas"]) + "</p>")
    sorok.append('<p class="halvany kicsi">Aláhúzva a hívott lap. '
                 '<span class="kerdes">?</span> = a rendszer nem mondja ki, '
                 'feltételezés.</p>')
    return "".join(sorok)


def _jelzes_html(sig) -> str:
    if not isinstance(sig, dict) or "racs" not in sig:
        return _szoveg_blokk(sig)
    labjegyzet: list[str] = []

    def cella(jelek, i):
        if i >= len(jelek):
            return ""
        j = jelek[i]
        ki = _e(j["jel"])
        if j.get("mikor"):
            szoveg = f"{j['jel']}: {j['mikor']}" + (
                f"; különben {j['kulonben'].lower()}" if j.get("kulonben") else "")
            if szoveg not in labjegyzet:
                labjegyzet.append(szoveg)
            ki += f"<sup>{labjegyzet.index(szoveg) + 1}</sup>"
            if j.get("kulonben"):
                ki += " / " + _e(j["kulonben"])
        return ki + (' <span class="kerdes">?</span>' if j["feltetelezes"] else "")
    t = ["<table class=racs><tr><th rowspan=2></th><th colspan=3>Szín ellen</th>"
         "<th colspan=3>Szan ellen</th></tr><tr>"
         + "".join(f"<th>{i}.</th>" for i in (1, 2, 3)) * 2 + "</tr>"]
    for r in sig["racs"]:
        t.append(f"<tr><td>{_e(r['helyzet'])}</td>"
                 + "".join(f"<td>{cella(r['SZIN'], i)}</td>" for i in range(3))
                 + "".join(f"<td>{cella(r['SZAN'], i)}</td>" for i in range(3))
                 + "</tr>")
    t.append("</table>")
    for i, x in enumerate(labjegyzet, 1):
        t.append(f'<p class="kicsi"><sup>{i}</sup> {_e(x)}</p>')
    t.append("<ul>")
    for m in sig.get("modszer") or []:
        t.append(f"<li><b>{_e(m['cim'])}:</b> {_e(m['szoveg'])}</li>")
    t.append("</ul>")
    if sig.get("elvek"):
        t.append("<h3>Elv</h3>" + _szoveg_blokk(sig["elvek"]))
    if sig.get("kulonleges"):
        t.append("<h3>Különleges helyzetek</h3>" + _szoveg_blokk(sig["kulonleges"]))
    if sig.get("licit_inditas"):
        t.append("<h3>Indítást irányító licitek</h3>" + _szoveg_blokk(sig["licit_inditas"]))
    if sig.get("hianyzo"):
        t.append('<p class="alert">Hiányzó jelzésrendszer: '
                 + _e(", ".join(sig["hianyzo"])) + "</p>")
    if sig.get("forrasok"):
        t.append('<p class="halvany kicsi">Forrás: ' + _e("; ".join(sig["forrasok"])) + "</p>")
    return "".join(t)


def _valaszok_html(valaszok: list[dict]) -> str:
    """Az alertálandó válaszok soronként, a természetesek egy sorba sűrítve."""
    ki, termeszetes = [], []
    for v in valaszok:
        if v["alert"]:
            ki.append(f"<div><span class=alert>{_piros(_e(v['call']))}!</span> "
                      f"{_piros(_e(v['text']))}</div>")
        else:
            termeszetes.append(_piros(_e(v["call"])))
    if termeszetes:
        ki.append('<div class="halvany">Természetes: ' + ", ".join(termeszetes) + "</div>")
    return "".join(ki)


def kartya_html(adat: dict) -> str:
    fej = adat.get("header") or {}
    ny = adat.get("openings") or []
    verseny = adat.get("competitive") or {}

    bal = ["<h2>Védekező és küzdelmi licitek</h2>"]
    for k, cim in _CIM.items():
        if verseny.get(k):
            bal.append(f"<h3>{_e(cim)}</h3><ul>" + "".join(
                f"<li>{_piros(_e(x))}</li>" for x in verseny[k]) + "</ul>")
    if adat.get("forcing_pass"):
        bal.append("<h3>Kényszerítő passzok</h3>" + _szoveg_blokk(adat["forcing_pass"]))

    sig = adat.get("signals")
    jr = ""
    if isinstance(sig, dict) and sig.get("rendszer"):
        jr = f'<p class="kicsi"><b>Jelzésrendszer:</b> {_e(sig["rendszer"]["name"])}'
        if sig.get("alapja"):
            jr += " — alapja: " + _e(", ".join(sig["alapja"]))
        jr += "</p>"
    kozep = ["<h2>Indító kijátszás</h2>", jr, _inditas_html(adat.get("leads")),
             "<h2>Jelzések</h2>", _jelzes_html(sig)]
    konv = ["<h2>Konvenciók</h2><ul class=kicsi>"]
    for k in adat.get("conventions") or []:
        konv.append(f"<li><b>{_e(k['name'])}</b> — {_piros(_e(k['summary']))}</li>")
    konv.append("</ul>")

    jobb = ['<div class="fej"><h1>' + _e(adat.get("name")) + "</h1>",
            f'<div class="kicsi">{_e(adat.get("system"))} · WBF-szerkezetű konvenciókártya'
            " · a kibic generálta</div>"]
    for k, cim in (("jatekosok", "Játékosok"), ("kategoria", "Kategória"),
                   ("esemeny", "Esemény")):
        if fej.get(k):
            jobb.append(f"<div><b>{cim}:</b> {_e(fej[k])}</div>")
    jobb.append("</div><h2>Általános stílus</h2>")
    jobb.append(_szoveg_blokk(adat.get("general") or adat.get("description")))
    kulonleges = [f"{o['label']}: {_rovid(o['description'], 70)}"
                  for o in ny if o.get("artificial")]
    jobb.append("<h2>Védekezést igénylő nyitások</h2>" + _szoveg_blokk(kulonleges or None))
    if adat.get("special"):
        jobb.append("<h2>Különleges megállapodások</h2>" + _szoveg_blokk(adat["special"]))
    if adat.get("slam"):
        jobb.append("<h2>Szlemlicit</h2>" + _szoveg_blokk(adat["slam"]))
    jobb.append("<h2>Pszichik</h2>" + _szoveg_blokk(adat.get("psychics")))
    st = adat.get("stats") or {}
    jobb.append(f'<p class="halvany kicsi">{st.get("rules", 0)} szabály, '
                f'{st.get("alerts", 0)} alertálandó.</p>')

    sorok = []
    for o in ny:
        valasz = _valaszok_html(o.get("responses", []))
        pont = ""
        if o.get("points"):
            lo, hi = o["points"]
            pont = f"{lo}+" if hi >= 37 else f"{lo}-{hi}"
        sorok.append(
            f"<tr><td class=nyit>{_piros(_e(o['label']))}</td>"
            f"<td>{'igen' if o.get('artificial') else 'nem'}</td>"
            f"<td>{_e(o.get('min_length', ''))}</td>"
            f"<td>{_piros(_e(o.get('neg_double_through', '')))}</td>"
            f"<td>{_e(pont)}{' FP' if pont else ''}<br>{_piros(_e(o['description']))}</td>"
            f"<td class=kicsi>{valasz}</td>"
            f"<td class=kicsi>{_e(', '.join(o.get('subsequent', [])))}</td>"
            f"<td class=kicsi>{_piros(_e('; '.join(o.get('passed_hand', []))))}</td></tr>")
    tabla = ("<table><tr><th>Nyitás</th><th>Mest.</th><th>Min.<br>hossz</th>"
             "<th>Neg. X<br>meddig</th><th>Leírás</th><th>Válaszok</th>"
             "<th>Folytatás</th><th>Passzolt kéz / 3-4. kéz</th></tr>"
             + "".join(sorok) + "</table>")

    return ("<!doctype html><html lang=hu><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width, initial-scale=1'>"
            f"<title>{_e(adat.get('name'))} — konvenciókártya</title>"
            f"<style>{_CSS}</style></head><body>"
            f"<section class='lap lap1'><div>{''.join(bal)}</div>"
            f"<div>{''.join(kozep)}</div><div>{''.join(jobb)}</div></section>"
            f"<section class='lap'><div><h2>Nyitások és válaszok</h2>{tabla}"
            f"{''.join(konv)}</div></section></body></html>")


# --- Betöltés: adatbázisból és YAML-ból ------------------------------

# A jelzéscsomagok kanonikus helye (mint a rendszerek/yaml a licitnek)
JELZES_KONYVTAR = Path(__file__).resolve().parents[3] / "rendszerek" / "jelzesek"


def _profil_lancbol(profilok: list) -> str | None:
    """A feloldási lánc első (legközelebbi) nem üres jelzési profilja: a kód."""
    from .jelzes import profil_kod
    for p in profilok:
        if p:
            return profil_kod(p)
    return None


def jelzesek_yamlbol(kod: str | None, utak=None, szint: str = "KARTYA"):
    from .jelzes import jelzesek, rendszerek_betolt
    if not kod:
        return None
    utak = utak or ([JELZES_KONYVTAR] if JELZES_KONYVTAR.is_dir() else [])
    return jelzesek(kod, rendszerek_betolt(utak), szint)


def jelzesek_db(conn, kod: str | None, szint: str = "KARTYA"):
    """A jelzésrendszer a `jelzesrendszer` / `jelzesmenet` táblákból (030)."""
    from .jelzes import jelzesek
    from .jelzes_db import rendszerek_db
    if not kod:
        return None
    return jelzesek(kod, rendszerek_db(conn), szint)


def jelzesek_rendszerhez_db(conn, rendszer_kod: str, teszt: bool = False):
    """
    Amit egy licitrendszer (pl. KIBIC_STAND) pára játszik: a feloldási lánc
    első `jelzesek:` profilja -> a feloldott jelzésrendszer (élesben csak az
    elfogadott sorok, teszt módban a javasolt is). None, ha nincs profil.
    """
    import json
    from .feloldas import feloldas
    kodok = [k for k, _ in feloldas(conn, rendszer_kod, teszt=teszt).lanc]
    cur = conn.cursor()
    cur.execute("SELECT kod, jelzesek FROM rendszer WHERE kod IN ("
                + ",".join(["%s"] * len(kodok)) + ")", kodok)
    adat = {k: (json.loads(j) if isinstance(j, (str, bytes)) else j) for k, j in cur.fetchall()}
    profil = _profil_lancbol([adat.get(k) for k in kodok])
    return jelzesek_db(conn, profil, "TESZT" if teszt else "ELES") if profil else None


def jelzesek_rendszerhez_yaml(rendszer_kod: str, teszt: bool = False, forrasok=None):
    """Mint a jelzesek_rendszerhez_db, de a YAML-ból (rendszerek/yaml + jelzesek):
    tartalék, ha az adatbázisból nem jön (pl. a 031-es migráció még nem futott)."""
    from ..impex.rendszer_yaml import betolt
    from .rendszercheck import feloldas_forrasokbol
    if forrasok is None:
        forrasok = betolt([JELZES_KONYVTAR.parent / "yaml"])
    f, _ = feloldas_forrasokbol(forrasok, rendszer_kod)
    profil = _profil_lancbol([getattr(forrasok[k], "jelzesek", None)
                              for k, _ in f.lanc if k in forrasok])
    return jelzesek_yamlbol(profil, szint="TESZT" if teszt else "ELES") if profil else None


def _meta_osszefesul(lanc_metak: list[dict]) -> dict:
    """A kártya-blokkok összefésülése: a lánc elején álló (a kártya) nyer."""
    ki: dict = {}
    for m in reversed(lanc_metak):
        for k, v in (m or {}).items():
            if v not in (None, "", [], {}):
                ki[k] = v
    return ki


def kartya_db(conn, rendszer_kod: str, teszt: bool = False) -> dict:
    import json
    from .feloldas import feloldas
    from .kriterium import parametertar_betolt
    f = feloldas(conn, rendszer_kod, teszt=teszt)
    pt = parametertar_betolt(conn, rendszer_kod)
    cur = conn.cursor()
    kodok = [k for k, _ in f.lanc]
    helyek = ",".join(["%s"] * len(kodok))
    try:
        cur.execute(f"SELECT kod, nev, leiras, fajta, kartya, jelzesek FROM rendszer"
                    f" WHERE kod IN ({helyek})", kodok)
        adatok = {r[0]: r for r in cur.fetchall()}
    except Exception:              # noqa: BLE001 — a 029/030 (vagy a 018) még nem futott le
        try:
            cur.execute(f"SELECT kod, nev, leiras, fajta, kartya, NULL FROM rendszer"
                        f" WHERE kod IN ({helyek})", kodok)
        except Exception:          # noqa: BLE001
            cur.execute(f"SELECT kod, nev, leiras, fajta, NULL, NULL FROM rendszer"
                        f" WHERE kod IN ({helyek})", kodok)
        adatok = {r[0]: r for r in cur.fetchall()}

    def meta(r, i=4):
        x = r[i]
        if isinstance(x, (str, bytes)):
            try:
                return json.loads(x)
            except ValueError:
                return {}
        return x or {}

    gy = adatok.get(rendszer_kod)
    rendszer = {"kod": rendszer_kod, "nev": gy[1] if gy else rendszer_kod,
                "leiras": gy[2] if gy else None}
    konv = [{"kod": k, "nev": adatok[k][1], "leiras": adatok[k][2],
             "fajta": adatok[k][3]} for k in kodok if k in adatok and k != rendszer_kod]
    profil = _profil_lancbol([meta(adatok[k], 5) for k in kodok if k in adatok])
    try:
        jelz = jelzesek_db(conn, profil) if profil else None
    except Exception:              # noqa: BLE001 — a 030 még nem futott le
        jelz = None
    return kartya_adat(rendszer, f.sorok,
                       _meta_osszefesul([meta(adatok[k]) for k in kodok if k in adatok]),
                       konv, pt, jelz)


def kartya_yamlbol(forrasok: dict, rendszer_kod: str, kulso=None,
                   jelzes_utak=None) -> dict:
    from .kriterium import Parametertar
    from .rendszercheck import feloldas_forrasokbol
    f, _ = feloldas_forrasokbol(forrasok, rendszer_kod, kulso=kulso)
    gy = forrasok[rendszer_kod]
    kodok = [k for k, _ in f.lanc]
    konv = [{"kod": k, "nev": forrasok[k].nev, "leiras": forrasok[k].leiras,
             "fajta": forrasok[k].fajta} for k in kodok
            if k in forrasok and k != rendszer_kod]
    meta = _meta_osszefesul([forrasok[k].kartya for k in kodok if k in forrasok])
    profil = _profil_lancbol([getattr(forrasok[k], "jelzesek", None)
                              for k in kodok if k in forrasok])
    return kartya_adat({"kod": gy.kod, "nev": gy.nev, "leiras": gy.leiras},
                       f.sorok, meta, konv,
                       Parametertar(rendszer_ertek=dict(gy.parameterek)),
                       jelzesek_yamlbol(profil, jelzes_utak))


# --- A kínált rendszerek (capabilities) --------------------------------

def kinalt_rendszerek_db(conn) -> list[dict]:
    """
    Azok a rendszerek, amelyekben a kibic licitálni tud ÉS van
    konvenciókártyájuk: aktív ALAPRENDSZER / RENDSZER (a 019 előtt:
    LICITRENDSZER / KONVENCIOKARTYA), kitöltött
    `kartya` oszloppal. (A konvenciók — Stayman stb. — önmagukban nem
    rendszerek, ezért nem szerepelnek.)
    """
    cur = conn.cursor()
    try:
        cur.execute("SELECT kod, nev, fajta, csalad, leiras, verzio FROM rendszer"
                    " WHERE aktiv = 1 AND kartya IS NOT NULL"
                    " AND fajta IN ('ALAPRENDSZER', 'RENDSZER',"
                    " 'LICITRENDSZER', 'KONVENCIOKARTYA')"
                    " ORDER BY kod")
    except Exception:              # noqa: BLE001 — a 018 még nem futott le
        return []
    return [{"system": r[0], "name": r[1], "kind": r[2], "family": r[3],
             "description": r[4], "version": r[5]} for r in cur.fetchall()]


def kartya_kivonat(adat: dict) -> dict:
    """
    Rövid, döntést segítő összefoglaló a kártyából — a rendszernév
    önmagában kevés ahhoz, hogy valaki profilt válasszon.
    """
    ny = []
    for o in adat.get("openings") or []:
        resz = [o.get("label") or szep(o.get("opening"))]
        if o.get("min_length"):
            resz.append(f"{o['min_length']}+")
        if o.get("points"):
            resz.append("{}–{}".format(*o["points"]) if o["points"][1] < 40
                        else f"{o['points'][0]}+")
        if o.get("artificial"):
            resz.append("(alert)")
        ny.append(" ".join(resz))
    return {"openings": " · ".join(ny[:12]),
            "general": _rovid(adat.get("general") if isinstance(adat.get("general"), str)
                              else None, 200) or None,
            "conventions": [c.get("name") for c in adat.get("conventions") or []]}
