"""
LICITÁLÓ ÉS LICITMAGYARÁZÓ szolgáltatás.

A DD-elemzés testvére: az megmondja, mi lett volna a legjobb LAP, ez azt
mondja meg, mit licitálna a kibic — és ami fontosabb, hogy MIÉRT, meg
hogy MIT ÉRTETT MEG az eddigi menetből.

MIÉRT A MAGYARÁZAT A LÉNYEG
----------------------------
Egy licitet adni önmagában keveset ér: nem lehet megmondani róla, jó-e.
Ez a végpont ezért minden válaszban elszámol azzal, hogy

    * a menet EDDIGI licitjei közül melyiket értette meg és melyiket nem
      (`auction_understanding`) — a nem értett licit nem félreértés,
      hanem HIÁNY a rendszerleírásban, és ezt jobb kimondani;
    * mit tud a négy kézről a licitekből (`constraints`);
    * a javaslat honnan jön: konkrét SZABÁLY, visszaesés ELVre, vagy
      szimulációs MÉRLEGELÉS (`source`);
    * ha több jelölt volt, mi maradt versenyben (`candidates`).

Így a hívó app akkor is tud mit mutatni, ha a kibic nem tud licitálni —
és épp az a visszajelzés a legértékesebb, hogy hol néma.

VISZONY A MOHABRIDZS AI GATEWAY PROTOKOLLHOZ
--------------------------------------------
Ez sem része a `mohabridzs-ai/1.0` szerződésnek: az döntéshozatalról
szól szigorú határidővel és "pontosan egy Action" válasszal, ez pedig
MAGYARÁZÓ elemzés. Saját névtérben él: `POST /v1/kibic/licit`.
A jelölések viszont szándékosan azonosak: égtáj `N E S W`, szín
`C D H S`, beliállás `none ns ew both`, hívás `P X XX` vagy `2H`.
(Egy eltérés: itt a szan `NT`, a dróton `N` — az `atjaro.drotra()` vált.)

A MohaBridzs webapp NEM ezt hívja, hanem a `POST /v1/bridge/bid`
végpontot; azt a `szolgaltatas/atjaro.py` fordítja rá erre a függvényre.
Ott a `call` nem lehet `null`, itt lehet — és épp az a mérés. Lásd:
`doc/mohabridzs-atjaro.md`.

BEMENET
-------
    {
      "request_id": "opcionális, változatlanul visszaadjuk",
      "hand": ["SA","SK","HQ", ...],        a KÉRDEZŐ 13 lapja
      "seat": "S",
      "dealer": "N",
      "vulnerability": "ns",
      "auction": [{"seat":"N","call":"1S"}, {"seat":"E","call":"P"}],
      "system": "LICREN_STAND",             melyik rendszer szerint
      "pair": "gal - korszurku",            opcionális paraméter-forrás
      "legal_actions": ["P","X","2H", ...], opcionális szűrés
      "simulate": true                      mérlegeljen-e (lassabb)
    }

Az `auction` megadható rövid alakban is: `["1S","P","2C"]` — ilyenkor az
osztótól számítva osztjuk ki az üléseket.

FONTOS KORLÁT
-------------
A kibic annyit tud, amennyi a rendszerleírásában benne van. Ahol a
tudásbázis hiányos — márpedig a kompetitív ágakon ma az —, ott a válasz
`call` mezője `null` lesz. Ez nem hiba, hanem mérés.
"""
from __future__ import annotations

from ..domain import Kez, Lap, ULESEK, kovetkezo_ules, vonal

import os as _os

# KIZÁRÁSOS KÖVETKEZTETÉS (motor/kovetkeztetes.py): időkeret licitkérésenként.
# 0 = kikapcsolva. Kérésenként: "inference": false / true, "inference_ms": N.
KOVETKEZTETES_MS = int(_os.environ.get("KIBIC_KOVETKEZTETES_MS", "800"))

FIGYELMEZTETES = (
    "A kibic csak azt tudja, ami a betöltött rendszerleírásában benne "
    "van. Ahol nincs szabálya, ott nem találgat: inkább nem licitál. "
    "Az `auction_understanding` és a `coverage` megmutatja, mennyit "
    "értett meg egyáltalán az eddigi menetből."
)

BELI_TERKEP = {"NONE": "NONE", "NS": "NS", "EW": "EW", "BOTH": "ALL",
               "ALL": "ALL", "": "NONE"}

FORRAS_SZOVEG = {
    "SZABALY": "konkrét szabály a rendszerben",
    "ELV": "nincs rá megállapodás, az általános elv szerint",
    "MERLEGELES": "a szabály csak beengedte; a döntés szimulációból jött",
    "NINCS": "nincs rá szabály a betöltött rendszerben",
    "HEZAG": "nincs rá szabály; a hézag-elv döntött (közös erő és kényszer alapján)",
    "SPIRAL": "a kulcslap-válasz utáni spirál (MOHA_SPIRAL)",
}


class LicitHiba(ValueError):
    """Hibás bemenet. A hívó HTTP 400-zal fordíthatja le."""


# --- Bemenet értelmezése ---------------------------------------------

def _kez(lapok) -> Kez:
    if not isinstance(lapok, (list, tuple)):
        raise LicitHiba("A 'hand' mező lapok listája legyen")
    try:
        keszlet = {Lap.parse(str(x)) for x in lapok}
    except ValueError as e:
        raise LicitHiba(f"Érvénytelen lapjelölés: {e}") from e
    if len(keszlet) != 13:
        raise LicitHiba(f"13 lap kell, {len(keszlet)} érkezett")
    return Kez(frozenset(keszlet))


def _hivas(ertek) -> str:
    """'p' -> 'P', '2h' -> '2H', 'dbl' -> 'X', '1n' -> '1NT'."""
    s = str(ertek or "").strip().upper()
    if s in ("P", "PASS", "-"):
        return "P"
    if s in ("X", "DBL", "D", "*"):
        return "X"
    if s in ("XX", "RDBL", "R", "**"):
        return "XX"
    if len(s) >= 2 and s[0] in "1234567":
        szin = s[1:]
        if szin in ("N", "NT", "SA"):
            szin = "NT"
        if szin not in ("C", "D", "H", "S", "NT"):
            raise LicitHiba(f"Érvénytelen hívás: {ertek!r}")
        return f"{s[0]}{szin}"
    raise LicitHiba(f"Érvénytelen hívás: {ertek!r}")


def _menet(auction, oszto: str) -> list[dict]:
    """Elemek {seat, call} vagy puszta hívások; utóbbinál osztunk ülést."""
    ki: list[dict] = []
    u = oszto
    for elem in (auction or []):
        if isinstance(elem, dict):
            ules = str(elem.get("seat") or elem.get("ules") or u).upper()
            hivas = _hivas(elem.get("call") or elem.get("licit"))
        else:
            ules, hivas = u, _hivas(elem)
        if ules not in ULESEK:
            raise LicitHiba(f"Érvénytelen ülés: {ules!r}")
        e = {"ules": ules, "licit": hivas}
        if isinstance(elem, dict) and elem.get("alert"):
            e["alert"] = elem["alert"]       # az asztalnál kapott magyarázat
        info = elem.get("information") if isinstance(elem, dict) else None
        if isinstance(info, dict):
            # mohabridzs-ai 1.1: a kibic kérésére begyűjtött magyarázat
            # (status: available / none / error). Ha van szöveg, az erősebb
            # a régi alertnél: kifejezetten erre a kérdésre jött.
            e["informacio"] = str(info.get("status") or "")
            if info.get("status") == "available" and info.get("text"):
                e["alert"] = {"text": str(info["text"]),
                              "alerted": bool(info.get("alerted"))}
        ki.append(e)
        u = kovetkezo_ules(ules)
    return ki


def szabalyos_hivasok(licitek: list[dict], ules: str) -> list[str]:
    """A szabályos hívások a menet után (P, X, XX, a legmagasabb fölötti licitek)."""
    from ..domain import vonal
    rang = {"C": 0, "D": 1, "H": 2, "S": 3, "NT": 4}
    legmagasabb = (0, -1)
    utolso = None                     # (ülés, hívás) az utolsó nem-passz
    for e in licitek:
        h = e["licit"]
        if h == "P":
            continue
        utolso = (e["ules"], h)
        if h not in ("X", "XX"):
            legmagasabb = (int(h[0]), rang[h[1:]])
    ki = ["P"]
    if utolso and vonal(utolso[0]) != vonal(ules):
        if utolso[1] not in ("X", "XX"):
            ki.append("X")
        elif utolso[1] == "X":
            ki.append("XX")
    for szint in range(1, 8):
        for sz in ("C", "D", "H", "S", "NT"):
            if (szint, rang[sz]) > legmagasabb:
                ki.append(f"{szint}{sz}")
    return ki


def _ules(ertek, mezo: str) -> str:
    u = str(ertek or "").strip().upper()
    if u not in ULESEK:
        raise LicitHiba(f"A '{mezo}' mező N/E/S/W legyen, nem {ertek!r}")
    return u


# --- Kimenet építése --------------------------------------------------

def _szam(x):
    """Az egész értékek maradjanak egészek a JSON-ban."""
    return int(x) if float(x).is_integer() else round(float(x), 2)


def _igeret_json(ig) -> dict | None:
    if not ig.nyilatkozott:
        return None
    ki: dict = {}
    if ig.pont_min > 0 or ig.pont_max < 40:
        ki["points"] = [_szam(ig.pont_min), _szam(ig.pont_max)]
    szinek = {}
    for sz in ("S", "H", "D", "C"):
        lo, hi = ig.hossz(sz)
        if lo > 0 or hi < 13:
            szinek[sz] = [lo, hi]
    if szinek:
        ki["suits"] = szinek
    if ig.tagad:
        ki["denies"] = sorted(ig.tagad)
    if getattr(ig, "fogas", None):
        ki["stoppers"] = [sz for sz in ("S", "H", "D", "C") if sz in ig.fogas]
    if ig.forsz and ig.forsz != "NEM":
        ki["forcing"] = ig.forsz
    if not ki:
        # Nyilatkozott, de egyik licitjét sem értettük: ezt mondjuk ki,
        # mert nem ugyanaz, mint a hallgatás.
        return {"described": "nyilatkozott, de nem értettük a licitjeit",
                "understood": False}
    ki["described"] = ig.leiras()
    ki["understood"] = True
    return ki


def vonalas_propagalo(sorok, paramtar, betolto, ules: str,
                      ellen_kod: str | None, csaladok: dict | None,
                      teszt: bool | None = None):
    """
    A jelentés-propagáló a két vonalra: a mi licitjeinket a mi
    rendszerünk, az ellenfélét az ÖVÉK (ismert rendszer vagy
    rendszercsalád) szerint érti. Ha az ellenfél rendszere nincs megadva
    vagy nem tölthető be, mindenkit a mi rendszerünk szerint (a régi
    működés).
    """
    from ..domain import vonal
    from ..motor.propagal import Propagalo
    ellen = None
    if ellen_kod:
        try:
            e_sorok, e_param = (betolto(ellen_kod, None) if teszt is None
                                else betolto(ellen_kod, None, bool(teszt)))
            ellen = Propagalo(e_sorok, e_param)
        except Exception:          # noqa: BLE001 — ismeretlen rendszer: a régi működés
            ellen = None
    return Propagalo(sorok, paramtar, ellenfel=ellen,
                     sajat_vonal=vonal(ules),
                     csaladok=csaladok)


def kenyszertar_menetbol(keres: dict, betolto) -> dict:
    """
    A licitmenetből a négy kéz kényszertára (mit ígértek a licitjeikkel) —
    a lejátszó réteg mintavételéhez. `keres`: seat, dealer, vulnerability,
    auction, system, pair, opponent_system, families, test_mode.
    """
    oszto = _ules(keres.get("dealer", keres.get("seat")), "dealer")
    ules = _ules(keres.get("seat"), "seat")
    beli = BELI_TERKEP.get(str(keres.get("vulnerability", "none")).upper(), "NONE")
    licitek = _menet(keres.get("auction"), oszto)
    teszt = keres.get("test_mode")
    sorok, paramtar = (betolto(keres["system"], keres.get("pair")) if teszt is None
                       else betolto(keres["system"], keres.get("pair"), bool(teszt)))
    prop = vonalas_propagalo(sorok, paramtar, betolto, ules, keres.get("opponent_system"),
                             keres.get("families") or {}, teszt)
    return prop.kenyszertar(licitek, oszto=oszto, beliallas=beli).kenyszertar


def _megertes(prop, licitek: list[dict], oszto: str, er=None) -> list[dict]:
    """
    Licitenként: megértette-e a rendszer, és ha igen, mit jelent.

    Nem elég a végeredményt megmutatni: a hívó appnak azt is látnia
    kell, hol szakadt el a fonal. Ha a 3. licitet nem értettük, az
    utána következő kényszertár is ennyivel kevesebbet ér.

    `er`: a propagálás eredménye — a jelentést ugyanabból az állapotból
    olvassuk, amiből a kényszertár épült (a "partner ígérte" típusú
    elvekhez kell az addigi tár).
    """
    if er is None:
        er = prop.kenyszertar(licitek, oszto)
    forras_nev = {"SAJAT": "own_system", "ELLENFEL": "their_system", "ALERT": "alert"}
    ki: list[dict] = []
    for i, elem in enumerate(licitek):
        u, hivas = elem["ules"], elem["licit"]
        sor = {"seat": u, "call": hivas}
        if hivas == "P":
            sor["understood"] = True
            sor["meaning"] = "passz"
            ki.append(sor)
            continue
        if elem.get("alert") is True or (isinstance(elem.get("alert"), dict)
                                         and not elem["alert"].get("text")):
            sor["alerted_without_text"] = True
        info = (getattr(er, "licitenkent", None) or {}).get(i)
        if not info or info.get("igeret") is None:
            sor["understood"] = False
            sor["note"] = "nincs rá szabály a betöltött rendszerben"
            if elem.get("alert") and not sor.get("alerted_without_text"):
                sor["note"] += "; az alert szövegéből sem olvasható ki biztosan semmi"
        else:
            sor["source"] = forras_nev.get(info.get("honnan"), "own_system")
            sor["understood"] = True
            sor["meaning"] = info["igeret"].leiras()
            if info.get("db", 1) > 1:
                sor["ambiguous"] = info["db"]
        ki.append(sor)
    return ki


def _magyarazatkeres(megertes: list[dict], ules: str,
                     licitek: list[dict] | None = None) -> list[dict]:
    from ..domain import vonal
    mi = vonal(ules)
    ki = []
    for i, m in enumerate(megertes):
        if m["call"] == "P" or vonal(m["seat"]) == mi:
            continue
        if licitek is not None and i < len(licitek) and licitek[i].get("informacio"):
            continue                   # már megkérdeztük (bármi lett a válasz)
        if not m.get("understood") and "alert" not in (m.get("note") or ""):
            ki.append({"index": i, "seat": m["seat"], "call": m["call"],
                       "reason": "not_understood"})
        elif m.get("alerted_without_text") and m.get("source") != "their_system":
            ki.append({"index": i, "seat": m["seat"], "call": m["call"],
                       "reason": "alerted_without_explanation"})
    return ki


# 3NT fölött nincs alert — ez szabály, kivétel nélkül (Moha, 2026-10-02).
# Ha egyszer verseny- vagy párfüggő lesz, ebből paraméter lesz.
ALERT_FELSO_HATAR = "3NT"


def alertalando_szint(licit: str, licitek: list[dict] | None = None) -> bool:
    """A licit alertálható szinten van-e (legfeljebb ALERT_FELSO_HATAR)."""
    from ..motor.helyzet import _licit_rang
    r, h = _licit_rang(licit or ""), _licit_rang(ALERT_FELSO_HATAR)
    return r is None or h is None or r <= h


def _alert(d, prop=None, licitek=None, ules=None, tar=None, oszto=None) -> dict | None:
    """
    {"alert": true, "text": "..."} ha a licit alertálandó.

    Az alert a MEGÁLLAPODÁST mondja el, nem a lapot: ha ugyanarra a licitre
    ebben a menetben több szabály is van (pl. Walsh 1♣-1♦: gyenge VAGY
    erős), mindegyik szövege kimegy — különben a győztes sor szövege
    elárulná, melyik ágba esik a kéz.
    """
    j = getattr(d, "gyoztes", None)
    if j is None:
        return None
    if licitek is not None and not alertalando_szint(j.licit, licitek):
        return None
    sorok = [j.sor]
    if prop is not None and licitek is not None:
        try:
            sorok = [s for s, _ in prop.jelentes_sorokkal(licitek, ules, j.licit,
                                                           tar, oszto)] or sorok
        except Exception:          # noqa: BLE001 — az alert nem állíthatja meg a licitet
            sorok = [j.sor]
    alertos = [s for s in sorok if getattr(s, "alert", False)]
    if not alertos:
        return None
    szovegek, en = [], []
    for s in alertos:
        t = s.magyarazat or s.feltetel_szoveg or ""
        if t and t not in szovegek:
            szovegek.append(t)
        te = getattr(s, "magyarazat_en", None)
        if te and te not in en:
            en.append(te)
    return {"alert": True, "text": " / ".join(szovegek),
            "text_en": " / ".join(en) or None}


def _debug(d, kez) -> dict:
    """
    A TANÍTÓ nyom: minden szabály, ami ebben a helyzetben szóba jött,
    az eredménnyel és a "miért nem"-mel; a győztes forrása; a kéz rövid
    adatai. CSAK teszt/műhely módban megy ki.
    """
    from ..domain import ERTEKELOK
    sorrend = {"IGAZ": 0, "ISMERETLEN": 1, "HAMIS": 2, "HELYZET_NEM": 3,
               "NEM_LEGALIS": 4}
    nyom = sorted(d.nyom or [], key=lambda n: (sorrend.get(n["result"], 9),
                                                -(n["priority"] or 0)))
    ki: dict = {
        "hand": {"hcp": int(ERTEKELOK["HCP"](kez)),
                 "shape": {sz: kez.hossz(sz) for sz in ("S", "H", "D", "C")}},
        "considered": nyom[:25],
        "considered_total": len(nyom),
    }
    j = getattr(d, "gyoztes", None)
    if j is not None:
        ki["chosen"] = {"call": j.licit, "rule": j.sor.minta,
                        "system": j.sor.rendszer_kod,
                        "chapter": getattr(j.sor, "fejezet", None),
                        "source": getattr(j.sor, "forras", None),
                        "rule_id": j.sor.licitmenet_id,
                        "priority": j.sor.prioritas,
                        "condition": j.sor.feltetel_szoveg,
                        "explanation": j.sor.magyarazat}
        if getattr(d, "banky", None):
            # egyformán jó jelöltek közül a legalacsonyabb (Bánky-szabály)
            ki["chosen"]["tie_break"] = {"rule": "Bánky: a legalacsonyabb",
                                         "among": d.banky}
    elif d.licit:
        ki["chosen"] = {"call": d.licit, "rule": None,
                        "explanation": d.indoklas}
    return ki


def _jelolt_json(j) -> dict:
    return {"call": j.licit,
            "rule": j.sor.minta,
            "source_system": j.sor.rendszer_kod,
            "why": j.sor.magyarazat or j.indoklas or "",
            "specificity": j.minta_specifikussag,
            "alert": bool(getattr(j.sor, "alert", False))}


# --- A szolgáltatás ---------------------------------------------------

def _passz_nyitoero_nelkul(d, motor, licitek: list[dict],
                           engedelyezett) -> bool:
    """
    A LICREN hallgatólagos szabálya: ha NYITÓ helyzetben (eddig mindenki
    passzolt) egyik nyitás sem illik, akkor passz. Erre a rendszerben
    nincs sor, mert a LICREN így működik — a kibic viszont eddig "nincs
    szabályom"-nak vette, és az átjáró tartalékként naplózta.

    Szándékosan SZŰK: csak a nyitásra, és csak ha
      * a rendszerben egyáltalán van nyitás-szabály,
      * semmi nem maradt eldönthetetlen (különben nem tudjuk, hogy
        tényleg nincs-e nyitóerő),
      * nincs mérlegelendő jelölt,
      * a passz megengedett.
    A válaszoló helyzetekben a csendes passz valódi hiányt takarna el,
    ezért ott továbbra is NINCS a forrás. A `Dontes`-t helyben módosítja.
    """
    if d.licit is not None or d.merlegelendo or d.eldonthetetlen:
        return False
    if any(e["licit"] != "P" for e in licitek):
        return False
    if engedelyezett is not None and "P" not in engedelyezett:
        return False
    van_nyitas = any(len(m.tokenek) == 1 and not m.tokenek[0].ellenfel
                     for m, _ in motor.szabalyok)
    if not van_nyitas:
        return False
    d.licit = "P"
    d.indoklas = "nincs nyitóerő: egyik nyitás-szabály sem illik"
    return True


def licit_elemzes(keres: dict, betolto) -> dict:
    """
    `betolto(rendszer_kod, par_nev) -> (sorok, parametertar)`

    A betöltő kívülről jön, hogy a szolgáltatás tesztelhető legyen
    adatbázis nélkül, és hogy a gyorsítótárazás a hívó dolga maradjon:
    egy rendszer feloldása drága, kérésenként újra megcsinálni pazarlás.
    """
    from ..motor.helyzet import Allas
    from ..motor.kifejezes import rendszer_kontextus
    from ..motor.licital import Licitmotor
    from ..motor.propagal import Propagalo

    if not isinstance(keres, dict):
        raise LicitHiba("A kérés JSON-objektum legyen")

    kez = _kez(keres.get("hand"))
    oszto = _ules(keres.get("dealer", keres.get("seat")), "dealer")
    ules = _ules(keres.get("seat"), "seat")
    beli = BELI_TERKEP.get(str(keres.get("vulnerability", "none")).upper())
    if beli is None:
        raise LicitHiba(f"Ismeretlen beliállás: {keres.get('vulnerability')!r}")
    licitek = _menet(keres.get("auction"), oszto)
    rendszer_kod = keres.get("system")
    if not rendszer_kod:
        raise LicitHiba("A 'system' mező kötelező (pl. 'LICREN_STAND')")

    engedelyezett = keres.get("legal_actions")
    if engedelyezett:
        engedelyezett = [_hivas(x) for x in engedelyezett]
    else:
        # a MohaBridzs mindig küldi; a műhelyben a menetből számoljuk, hogy
        # a kibic itt se javasolhasson szabálytalan licitet
        engedelyezett = szabalyos_hivasok(licitek, ules)

    # TESZT MÓD: kérésenként is kérhető ("test_mode": true); ha nincs
    # megadva, a betöltő alapértelmezése (KIBIC_TESZT_MOD) él.
    teszt = keres.get("test_mode")
    if teszt is None:
        sorok, paramtar = betolto(rendszer_kod, keres.get("pair"))
    else:
        sorok, paramtar = betolto(rendszer_kod, keres.get("pair"), bool(teszt))
    teszt_mod = bool(teszt) if teszt is not None else \
        bool(getattr(betolto, "teszt_alap", False))

    # 1. Mit értettünk meg az eddigi menetből? Az ellenfél licitjeit —
    # ha a kérés megmondja — az ő rendszerük (családjuk) szerint.
    csaladok = keres.get("families") or {}
    prop = vonalas_propagalo(sorok, paramtar, betolto, ules,
                             keres.get("opponent_system"), csaladok, teszt)
    kov_ms = int(keres.get("inference_ms", KOVETKEZTETES_MS))
    if keres.get("inference") is False:
        kov_ms = 0
    er = prop.kenyszertar(licitek, oszto=oszto, beliallas=beli,
                          kovetkeztet_ulesek={u for u in ULESEK if u != ules},
                          kovetkeztetes_ms=kov_ms)
    megertes = _megertes(prop, licitek, oszto, er)
    for i, info in (er.kovetkeztetes_licitenkent or {}).items():
        if i < len(megertes):
            megertes[i]["inferred"] = "valószínűleg (amit nem licitált): " + info["text"]

    allas = Allas(ules=ules, beliallas=beli, licitek=list(licitek),
                  oszto=oszto, kenyszertar=er.kenyszertar, csaladok=csaladok)
    allas.valoszinu = er.kovetkeztetett or {}

    # 2. Mit licitálnánk?
    motor = Licitmotor(sorok, rendszer_kontextus(paramtar),
                       mod="SPECIFIKUSSAG")
    # DEBUG (tanító) nyom: teszt módban mindig, élesben csak ha kérik a
    # MŰHELY-végponton. A nyom a KÉZ értékeit is tartalmazza — ellenfélnek
    # szóló végpont (bridge/explain) soha nem adhatja ki.
    debug = bool(teszt_mod or keres.get("debug"))
    d = motor.licital(licitek, ules, kez, beliallas=beli,
                      engedelyezett=engedelyezett, allas=allas, oszto=oszto,
                      nyomkovetes=debug)
    nincs_nyitoero = _passz_nyitoero_nelkul(d, motor, licitek, engedelyezett)

    forras = ("ELV" if d.elvre_esett and d.licit else
              "SZABALY" if d.licit else
              "MERLEGELES" if d.merlegelendo else "NINCS")

    valasz: dict = {
        "request_id": keres.get("request_id"),
        "seat": ules,
        "system": rendszer_kod,
        "branch": allas.ag,
        "call": d.licit,
        "source": forras,
        "source_text": FORRAS_SZOVEG[forras],
        "explanation": d.osszefoglalo(),
        "uncertain": bool(d.bizonytalan or d.merlegelendo),
        "candidates": [_jelolt_json(j) for j in d.jeloltek],
        "to_deliberate": [_jelolt_json(j) for j in d.merlegelendo],
        "undecidable_rules": d.eldonthetetlen,
        "test_mode": teszt_mod,
        "implicit_pass": nincs_nyitoero,
        "auction_understanding": megertes,
        "constraints": {u: _igeret_json(er.kenyszertar[u]) for u in ULESEK},
        # valószínű tudás a kizárásos következtetésből (nem biztos!)
        "inferred": {u: _igeret_json(ig) for u, ig in (er.kovetkeztetett or {}).items()},
        "coverage": {
            "understood": er.ertett,
            "unknown": len(er.nem_ertett),
            "unknown_calls": er.nem_ertett,
            "ratio": round(er.lefedettseg, 3),
            "from_alert": er.alertbol,
        },
        # Az ellenfél licitjei, amelyeket se a rendszerük, se az alert nem
        # magyarázott meg: ezekre a kibic MAGYARÁZATOT KÉR (a szabály szerint
        # a soron lévő játékos kérdezhet). A MohaBridzs a következő kérésben
        # az auction[i].alert mezőben küldheti a választ.
        "explain_requests": _magyarazatkeres(megertes, ules, licitek),
        "warning": FIGYELMEZTETES,
    }
    if er.ellentmondas:
        valasz["inconsistent"] = er.ellentmondas
    if forras == "ELV" and d.helyzeti_megallapodas:
        # az ELV-réteg döntött, de egy konvenció helyzeti alakja (pl. RKC):
        # ez megállapodás, nem "általános elv"
        valasz["situational_agreement"] = d.helyzeti_megallapodas

    # ALERT: a választott szabály alertálandó-e. Ez a licittel együtt
    # megy ki (az ellenfélnek jár), és csak a MEGÁLLAPODÁST mondja el.
    valasz["alert"] = _alert(d, prop, licitek, ules, er.kenyszertar, oszto)

    if debug:
        valasz["debug"] = _debug(d, kez)

    # 2b. SPIRÁL (MOHA_SPIRAL, 2026-10-04): a kulcslap-válasz után a
    # spirál-kérdezés és -válasz a menetből számolódik (motor/spiral.py);
    # ilyenkor ez dönt — a szabálysorok itt félreértenék a reléket (pl.
    # kulcslicitnek vagy ászkérdésnek).
    if keres.get("spiral", True) is not False:
        from ..motor.spiral import spiral_dontes
        sp = spiral_dontes(kez, allas, er, licitek, engedelyezett)
        if sp is not None:
            valasz["call"] = sp.licit
            valasz["source"] = "SPIRAL"
            valasz["source_text"] = FORRAS_SZOVEG["SPIRAL"]
            valasz["explanation"] = f"{sp.licit} — {sp.indok}"
            valasz["alert"] = None            # 3NT fölött nincs alert
            valasz["spiral"] = {"role": sp.szerep, "reason": sp.indok}
            return _arnyekkal(valasz, keres, kez, allas, er, licitek, engedelyezett, betolto)

    # 3. Ha van mérlegelendő jelölt, és kérték: szimuláció.
    if d.merlegelendo and keres.get("simulate"):
        valasz["deliberation"] = _merlegeles(allas, kez, keres, d)
        # "A szabály kapuz, a mérlegelés dönt": ha a szimuláció
        # végkontraktust választott, az a licit.
        ajanl = valasz["deliberation"].get("recommended_call")
        if ajanl:
            valasz["call"] = ajanl
            valasz["source"] = "MERLEGELES"
            valasz["source_text"] = FORRAS_SZOVEG["MERLEGELES"]

    # 4. HÉZAG-ELV (2026-10-03, Moha): ha sem szabály, sem elv, sem a
    # mérlegelés nem adott licitet, a közös erő és a kényszer dönt — nem a
    # vak passz (motor/hezag.py). Kérésenként kikapcsolható: "gap_principle": false.
    if valasz["call"] is None and keres.get("gap_principle", True) is not False:
        from ..motor.hezag import hezag_dontes
        # a büntető passz kérdéséhez a szimuláció (DD-mintavétel), ha kérték
        buntetes = (lambda: _merlegeles(allas, kez, keres, None)) \
            if keres.get("simulate") else None
        vegk = (lambda hivasok: _vegkontraktus_szim(allas, kez, keres, hivasok)) \
            if keres.get("simulate") else None
        h = hezag_dontes(kez, allas, prop, licitek, ules, oszto, engedelyezett,
                         megertes, er.kovetkeztetett or {}, buntetes, vegk,
                         keres.get("scoring"))
        if h is not None and (not engedelyezett or h.licit in engedelyezett):
            valasz["call"] = h.licit
            valasz["source"] = "HEZAG"
            valasz["source_text"] = FORRAS_SZOVEG["HEZAG"]
            valasz["explanation"] = f"{h.licit} — hézag-elv ({h.pont}. pont): {h.indok}"
            valasz["gap"] = {"rule": h.pont, "reason": h.indok}

    return _arnyekkal(valasz, keres, kez, allas, er, licitek, engedelyezett, betolto)


def _arnyekkal(valasz: dict, keres: dict, kez, allas, er, licitek, engedelyezett,
               betolto=None) -> dict:
    """ÁRNYÉK MÓD (motor/arnyek.py): a bekapcsolt új döntéshozók is lefutnak;
    a különbség a `shadow` mezőbe kerül, a licit a régi marad."""
    from ..motor import arnyek
    nevek = arnyek.kivalasztott(keres)
    if nevek:
        valasz["shadow"] = arnyek.futtat(
            {"kez": kez, "allas": allas, "er": er, "licitek": licitek,
             "engedelyezett": engedelyezett, "keres": keres, "valasz": valasz,
             "betolto": betolto}, nevek)
    return valasz


# A versenyforma (game.scoring): MP / BAM = párosverseny-jellegű (a pontszám
# nagysága mindegy, csak hogy több-e); IMP (és ha hiányzik) = csapatverseny.
PAROSVERSENY = ("MP", "MPS", "BAM", "PAIRS", "MATCHPOINTS")


def parosverseny(scoring) -> bool:
    return str(scoring or "").strip().upper() in PAROSVERSENY


def _vegkontraktus_jeloltek(allas, d) -> list[str] | None:
    """Ha a jelöltek mind VÉGKONTRAKTUS-választások (passz vagy nem
    forszoló szín-/szanlicit), és a legmagasabb licit a mi vonalunké."""
    from ..domain import vonal
    if allas._legmagasabb_ules is None or \
            vonal(allas._legmagasabb_ules) != vonal(allas.ules):
        return None
    jelolt = {j.licit: j for j in d.merlegelendo}
    if d.gyoztes is not None:
        jelolt.setdefault(d.gyoztes.licit, d.gyoztes)
    if len(jelolt) < 2:
        return None
    for licit, j in jelolt.items():
        if licit == "P":
            continue
        if allas._bont(licit)[0] is None:
            return None
        if (getattr(j.sor, "forsz", None) or "NEM") != "NEM":
            return None
    return sorted(jelolt, key=lambda x: (x != "P", x))


# SZIMULÁCIÓ IDŐKERETE (2026-10-20, a szerkesztő): a kérés `simulate_ms`-e
# (az átjáró adja: alapból 10 s) az EGÉSZ kérésre szól — minden szimuláció
# ugyanabból az időből gazdálkodik. Ha letelik, az addig feldolgozott mintán
# döntünk, ha az legalább SZIM_MIN_MINTA; különben a szabály-alapú becslés.
SZIM_ALAP_MS = int(_os.getenv("KIBIC_SZIM_MS", "10000"))
SZIM_MIN_MINTA = int(_os.getenv("KIBIC_SZIM_MIN_MINTA", "12"))


def _szim_hatarido(keres: dict) -> float:
    import time
    if "_szim_hatarido" not in keres:
        ms = float(keres.get("simulate_ms") or SZIM_ALAP_MS)
        keres["_szim_hatarido"] = time.monotonic() + ms / 1000.0
    return keres["_szim_hatarido"]


def _szim_lejart(keres: dict) -> bool:
    import time
    return time.monotonic() > _szim_hatarido(keres)


def _vegkontraktus_szim(allas, kez, keres: dict, hivasok: list[str]) -> dict:
    """
    Hézag-elv: melyik végkontraktus jobb (pl. passz = a mostani marad, vagy
    javítás a jobb fitbe)? DD-mintavétel a kényszertárból (a kizárásos
    következtetéssel szűkítve), ugyanúgy, mint a mérlegelésnél.
    """
    from ..motor.merlegel import Kalibracio, vegkontraktus_valasztas
    from ..motor.mintavetel import MintavetelHiba, mintavetel
    from ..motor.kovetkeztetes import szukitett_tar
    db = int(keres.get("samples", 60))
    if _szim_lejart(keres):
        return {"error": "a szimuláció időkerete elfogyott"}
    valoszinu = getattr(allas, "valoszinu", None) or {}
    m = None
    try:
        if valoszinu:
            try:
                m = mintavetel(kez, allas.ules, szukitett_tar(allas.kenyszertar, valoszinu),
                               db=db, beliallas=allas.beliallas, mag=1)
                if len(m.leosztasok) < db // 2:
                    m = None
            except MintavetelHiba:
                m = None
        if m is None:
            m = mintavetel(kez, allas.ules, allas.kenyszertar, db=db,
                           beliallas=allas.beliallas, mag=1)
        ut = keres.get("calibration")
        kal = Kalibracio.betolt(ut) if ut else Kalibracio()
        ki_k = vegkontraktus_valasztas(allas, m.leosztasok, hivasok, kalibracio=kal, mag=1,
                                       hatarido=_szim_hatarido(keres))
    except (MintavetelHiba, ValueError, ImportError) as e:
        return {"error": str(e)}
    n = min((len(k.pontszamok) for k in ki_k), default=0)
    if n < min(SZIM_MIN_MINTA, len(m.leosztasok)):
        return {"error": f"az időkeretben csak {n} minta készült el (legalább {SZIM_MIN_MINTA} kell)"}
    if parosverseny(keres.get("scoring")):
        legjobb = max(ki_k, key=lambda k: k.atlag)
    else:
        from ..domain.pontozas import imp
        legjobb = max(ki_k, key=lambda k: sum(
            sum(imp(x - y) for x, y in zip(k.pontszamok, o.pontszamok))
            for o in ki_k if o is not k))
    return {"best": legjobb.cimke, "samples": n, "timed_out": n < len(m.leosztasok),
            "options": {k.cimke: round(k.atlag) for k in ki_k}}


def _merlegeles(allas, kez, keres: dict, d=None) -> dict:
    from ..motor.merlegel import (Kalibracio, buntetes_vagy_sajat,
                                  vegkontraktus_valasztas)
    from ..motor.mintavetel import MintavetelHiba, mintavetel

    db = int(keres.get("samples", 60))
    if _szim_lejart(keres):
        return {"error": "a szimuláció időkerete elfogyott"}
    from ..motor.kovetkeztetes import szukitett_tar
    valoszinu = getattr(allas, "valoszinu", None) or {}
    try:
        # a kizárásos következtetéssel szűkítve, ha az mintavehető; különben a biztos tár
        m = None
        if valoszinu:
            try:
                m = mintavetel(kez, allas.ules, szukitett_tar(allas.kenyszertar, valoszinu),
                               db=db, beliallas=allas.beliallas, mag=1)
                if len(m.leosztasok) < db // 2:
                    m = None
            except MintavetelHiba:
                m = None
        if m is None:
            m = mintavetel(kez, allas.ules, allas.kenyszertar, db=db,
                           beliallas=allas.beliallas, mag=1)
    except MintavetelHiba as e:
        return {"error": str(e)}
    if not m.leosztasok:
        return {"error": "nem sikerült mintát venni a kényszertárból"}

    ki: dict = {"samples": len(m.leosztasok),
                "biased_sample": m.torzitott}
    ut = keres.get("calibration")
    kal = Kalibracio.betolt(ut) if ut else Kalibracio()

    vegk = _vegkontraktus_jeloltek(allas, d) if d is not None else None
    if vegk:
        from ..domain.pontozas import imp
        try:
            ki_k = vegkontraktus_valasztas(allas, m.leosztasok, vegk,
                                           kalibracio=kal, mag=1,
                                           hatarido=_szim_hatarido(keres))
        except (ValueError, ImportError) as e:
            ki["error"] = str(e)
            return ki
        n = min((len(k.pontszamok) for k in ki_k), default=0)
        ki["samples_used"] = n
        if n < min(SZIM_MIN_MINTA, len(m.leosztasok)):
            ki["error"] = f"az időkeretben csak {n} minta készült el (legalább {SZIM_MIN_MINTA} kell)"
            return ki
        if parosverseny(keres.get("scoring")):
            # párosverseny (MP / BAM): a pontszám-átlag (ahol több pont, ott nyerünk)
            legjobb = max(ki_k, key=lambda k: k.atlag)
        else:
            # csapatverseny (IMP, alapértelmezés): az IMP-átlag a többi lehetőség ellen
            def _imp_atlag(k):
                return sum(sum(imp(x - y) for x, y in zip(k.pontszamok, o.pontszamok))
                           for o in ki_k if o is not k) / max(1, len(k.pontszamok))
            legjobb = max(ki_k, key=_imp_atlag)
        ki["scoring"] = "MP" if parosverseny(keres.get("scoring")) else "IMP"
        ki.update({
            "kind": "final_contract",
            "options": [{"call": k.cimke,
                         "contract": f"{k.kontraktus.szint}{k.kontraktus.szin}"
                                     f"{k.kontraktus.kontra} {k.kontraktus.felvevo}",
                         "average_score": round(k.atlag),
                         "imp_vs_best": round(sum(imp(x - y) for x, y in zip(
                             k.pontszamok, legjobb.pontszamok)) / len(k.pontszamok), 2)}
                        for k in ki_k],
            "recommended_call": legjobb.cimke,
            "calibrated": kal.megmerve,
        })
        return ki
    try:
        o = buntetes_vagy_sajat(allas, m.leosztasok, kalibracio=kal, mag=1,
                                hatarido=_szim_hatarido(keres))
    except (ValueError, ImportError) as e:
        ki["error"] = str(e)
        return ki
    ki["samples_used"] = len(o.a.pontszamok)
    if len(o.a.pontszamok) < min(SZIM_MIN_MINTA, len(m.leosztasok)):
        ki["error"] = (f"az időkeretben csak {len(o.a.pontszamok)} minta készült el "
                       f"(legalább {SZIM_MIN_MINTA} kell)")
        return ki
    ki.update({
        "penalty": {"contract": str(o.a.kontraktus),
                    "average_score": round(o.a.atlag)},
        "our_best": {"contract": str(o.b.kontraktus),
                     "average_score": round(o.b.atlag)},
        "imp_difference": round(o.imp_kulonbseg, 2),
        "mp_win_rate": round(o.nyeresi_arany, 3),
        "calibrated": o.kalibralva,
        "summary": o.osszefoglalo(),
    })
    # A szabály kapuz, a mérlegelés dönt (2026-10-02): ha a büntetés
    # IMP-ben jobb, és jelölt a büntető kontra — vagy a partner kontrája
    # után a BÜNTETŐ PASSZ —, az a licit; különben marad a szabály győztese.
    jeloltek = {j.licit for j in (getattr(d, "merlegelendo", None) or [])}
    ki["scoring"] = "MP" if parosverseny(keres.get("scoring")) else "IMP"
    jobb = (o.nyeresi_arany > 0.5) if parosverseny(keres.get("scoring")) \
        else (o.imp_kulonbseg > 0)
    ki["penalty_better"] = bool(jobb)
    if jobb:
        if "P" in jeloltek and allas.kontra_allas == "MI":
            ki["recommended_call"] = "P"
        elif "X" in jeloltek and allas.kontra_allas == "NINCS":
            ki["recommended_call"] = "X"
    return ki
