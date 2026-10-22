"""
RENDSZERSZERKESZTŐ — a böngészős műhely adatrétege (GET /szerkeszto).

Amit a felület tud:
  * a rendszerek listája, állapot-összesítővel (hány szabály javasolt,
    elfogadott, felülvizsgálandó, jegelt);
  * egy rendszer feloldási fája (mit hivatkoz be, mit zár ki, mit cserélt
    téma szerint, mit vett ki módosítás);
  * fejezetek és szabályok emberi nyelven;
  * jóváhagyás / jegelés / visszaállítás — szabályonként vagy fejezetenként
    (a `rendszerimport --jovahagy` parancs helyett);
  * megjegyzések szabályhoz vagy fejezethez, amelyek az adatbázisba kerülnek
    (azonnal, nem piszkozatként), és exportálhatók Claude-nak.

A próbakéz a meglévő `/v1/kibic/licit` végpontot hívja (teszt mód + tanító
nyom), ahhoz itt nem kell semmi.

Minden függvény kapcsolatot kap, és tiszta adatot ad vissza: a HTTP-réteg
(api.py) csak szállít. A lekérdezések `%s` jelölésűek (pymysql).
"""
from __future__ import annotations

import datetime as _dt
import json
import re

ALLAPOTOK = ("JAVASOLT", "ELFOGADOTT", "FELULVIZSGALANDO", "JEGELT", "ELVETETT")

# Melyik művelet melyik állapotból hová visz.
MUVELETEK = {
    "jovahagy":  ("ELFOGADOTT", ("JAVASOLT", "FELULVIZSGALANDO")),
    "jegel":     ("JEGELT", ("JAVASOLT", "FELULVIZSGALANDO", "ELFOGADOTT")),
    "kiolvaszt": ("JAVASOLT", ("JEGELT",)),
    "visszavon": ("JAVASOLT", ("ELFOGADOTT",)),
}


class SzerkesztoHiba(ValueError):
    pass


def _rendszer_id(cur, kod: str) -> int:
    cur.execute("SELECT id FROM rendszer WHERE kod=%s", (kod,))
    r = cur.fetchone()
    if not r:
        raise SzerkesztoHiba(f"Nincs ilyen rendszer: {kod}")
    return r[0]


def _meta(cur) -> dict[str, dict]:
    """kód -> {nev, fajta, tema, alapja, viszony, csalad} (a 019/020 nélkül is)."""
    for oszlopok in ("kod, nev, fajta, tema, alapja, viszony, csalad",
                     "kod, nev, fajta, tema, NULL, NULL, csalad",
                     "kod, nev, fajta, NULL, NULL, NULL, csalad",
                     "kod, nev, fajta, tema, alapja, viszony, NULL",
                     "kod, nev, fajta, NULL, NULL, NULL, NULL"):
        try:
            cur.execute(f"SELECT {oszlopok} FROM rendszer WHERE aktiv=1")
            break
        except Exception:          # noqa: BLE001 — régebbi séma
            continue
    return {r[0]: {"code": r[0], "name": r[1], "kind": r[2], "theme": r[3],
                   "base": r[4], "relation": r[5], "family": r[6]}
            for r in cur.fetchall()}


def _alaprendszerek(cur, meta: dict[str, dict]) -> dict[str, list[str]]:
    """RENDSZER kód -> alaprendszerei (katalogus.alaprendszer_terkep)."""
    from .katalogus import alaprendszer_terkep
    try:
        cur.execute("SELECT r.kod, c.kod, lm.hivatkozas_aktiv FROM licitmenet lm"
                    " JOIN rendszer r ON r.id = lm.rendszer_id"
                    " JOIN rendszer c ON c.id = lm.hivatkozott_id"
                    " WHERE lm.tipus = 'HIVATKOZAS' AND lm.hivatkozas_mod = 'BE'"
                    " AND COALESCE(lm.fejezet, '') <> 'Alapja'")
        hiv = [(a, b, bool(c)) for a, b, c in cur.fetchall()]
    except Exception:              # noqa: BLE001 — régebbi séma
        return {}
    return alaprendszer_terkep({k: m["kind"] for k, m in meta.items()}, hiv)


def rendszerek(conn) -> list[dict]:
    """Az összes aktív rendszer, szabály-állapot összesítővel."""
    cur = conn.cursor()
    meta = _meta(cur)
    cur.execute("SELECT r.kod, lm.allapot, COUNT(*) FROM licitmenet lm"
                " JOIN rendszer r ON r.id = lm.rendszer_id"
                " WHERE lm.tipus='SZABALY' GROUP BY r.kod, lm.allapot")
    for kod, allapot, db in cur.fetchall():
        if kod in meta:
            meta[kod].setdefault("counts", {})[allapot] = int(db)
    # a hierarchia: RENDSZERCSALÁD → ALAPRENDSZER → RENDSZER
    for kod, alapok in _alaprendszerek(cur, meta).items():
        meta[kod]["base_system"] = alapok[0] if len(alapok) == 1 else None
        if len(alapok) != 1:
            meta[kod]["problem"] = ("nincs alaprendszere" if not alapok else
                                    "több alaprendszere van: " + ", ".join(alapok))
    sorrend = {"RENDSZER": 0, "GYUJTEMENY": 1, "ALAPRENDSZER": 2,
               "LICITRENDSZER": 2, "KONVENCIOKARTYA": 0, "RENDSZERCSALAD": 3,
               "KONVENCIO": 4, "ELV_SABLON": 5}
    return sorted(meta.values(),
                  key=lambda m: (sorrend.get(m["kind"], 9), m["code"]))


def fa(conn, kod: str, teszt: bool = True) -> dict:
    """A feloldási lánc a rendszer-adatokkal és a feloldás megjegyzéseivel."""
    from ..motor.feloldas import feloldas
    f = feloldas(conn, kod, teszt=teszt)
    meta = _meta(conn.cursor())
    return {
        "system": kod,
        "rules": len(f.sorok),
        "chain": [dict(meta.get(k, {"code": k}), depth=m) for k, m in f.lanc],
        "info": f.tajekoztatasok,
        "warnings": f.figyelmeztetesek,
        "order_overrides": f.sorrendi_felulirasok[:50],
    }


def _jegyzetek(cur, kod: str) -> tuple[str | None, dict]:
    """(a rendszer jegyzete, {fejezet: jegyzet}) — a 022 nélkül üres."""
    try:
        cur.execute("SELECT jegyzet, fejezet_jegyzetek FROM rendszer WHERE kod=%s",
                    (kod,))
    except Exception:              # noqa: BLE001 — a 022 még nem futott le
        return None, {}
    r = cur.fetchone()
    if not r:
        return None, {}
    fj = r[1]
    if isinstance(fj, (str, bytes)):
        try:
            fj = json.loads(fj)
        except ValueError:
            fj = {}
    return r[0], (fj or {})


def rendszer_info(conn, kod: str) -> dict:
    """Egy rendszer adatai, jegyzete és SAJÁT hivatkozásai (beemelés,
    kizárás, alap) — nem a feloldás, hanem ami közvetlenül benne van."""
    cur = conn.cursor()
    rid = _rendszer_id(cur, kod)
    meta = _meta(cur).get(kod, {"code": kod})
    jegyzet, _ = _jegyzetek(cur, kod)
    try:
        cur.execute(
            "SELECT r.kod, r.fajta, lm.hivatkozas_mod, lm.kizart_fejezet,"
            " lm.hivatkozas_aktiv, lm.fejezet FROM licitmenet lm"
            " JOIN rendszer r ON r.id = lm.hivatkozott_id"
            " WHERE lm.rendszer_id=%s AND lm.tipus='HIVATKOZAS' ORDER BY lm.seq",
            (rid,))
        sorok = cur.fetchall()
    except Exception:              # noqa: BLE001 — a 019 előtt
        cur.execute(
            "SELECT r.kod, r.fajta, 'BE', NULL, lm.hivatkozas_aktiv, lm.fejezet"
            " FROM licitmenet lm JOIN rendszer r ON r.id = lm.hivatkozott_id"
            " WHERE lm.rendszer_id=%s AND lm.tipus='HIVATKOZAS' ORDER BY lm.seq",
            (rid,))
        sorok = cur.fetchall()
    refs = []
    beall: dict = {}
    try:                           # 028: az elv-sablon példányok beállítása
        cur.execute("SELECT r.kod, lm.hivatkozas_beallitas FROM licitmenet lm"
                    " JOIN rendszer r ON r.id = lm.hivatkozott_id"
                    " WHERE lm.rendszer_id=%s AND lm.tipus='HIVATKOZAS'"
                    "   AND lm.hivatkozas_beallitas IS NOT NULL", (rid,))
        for k_, b_ in cur.fetchall():
            beall[k_] = json.loads(b_) if isinstance(b_, (str, bytes)) else b_
    except Exception:              # noqa: BLE001 — a 028 előtt
        pass
    for cel, fajta, mod, fej, aktiv, lm_fej in sorok:
        tipus = ("ALAP" if lm_fej == "Alapja" else
                 "KIZARAS" if mod == "KI" else "BEEMELES")
        refs.append({"target": cel, "kind": fajta, "type": tipus,
                     "chapter": fej, "active": bool(aktiv),
                     "settings": beall.get(cel) if tipus == "BEEMELES" else None})
    if meta.get("kind") == "ELV_SABLON":
        try:
            cur.execute("SELECT sablon FROM rendszer WHERE kod=%s", (kod,))
            r_ = cur.fetchone()
            sb = r_[0] if r_ else None
            meta = dict(meta, principle=json.loads(sb) if isinstance(sb, (str, bytes)) else sb)
        except Exception:          # noqa: BLE001
            pass
    if meta.get("kind") == "RENDSZER":
        alapok = _alaprendszerek(cur, _meta(cur)).get(kod) or []
        meta = dict(meta, base_system=alapok[0] if len(alapok) == 1 else None)
        if len(alapok) != 1:
            meta["problem"] = ("nincs alaprendszere" if not alapok else
                               "több alaprendszere van: " + ", ".join(alapok))
    return dict(meta, note=jegyzet, references=refs)


def fejezetek(conn, kod: str) -> list[dict]:
    cur = conn.cursor()
    rid = _rendszer_id(cur, kod)
    _, fej_jegyzet = _jegyzetek(cur, kod)
    cur.execute("SELECT fejezet, allapot, COUNT(*), MIN(seq) FROM licitmenet"
                " WHERE rendszer_id=%s AND tipus='SZABALY'"
                " GROUP BY fejezet, allapot", (rid,))
    ki: dict[str, dict] = {}
    for fej, allapot, db, seq in cur.fetchall():
        f = ki.setdefault(fej or "", {"chapter": fej or "", "counts": {},
                                      "total": 0, "seq": seq})
        f["counts"][allapot] = int(db)
        f["total"] += int(db)
        f["seq"] = min(f["seq"], seq)
    for f in ki.values():
        f["note"] = fej_jegyzet.get(f["chapter"])
    return sorted(ki.values(), key=lambda x: x["seq"])


_SZABALY_OSZLOPOK = (
    "id, fejezet, alfejezet, minta, kulcs, prioritas, allapot,"
    " feltetel_szoveg, magyarazat, alert, forsz, ha_feltetel_szoveg,"
    " nyers_szoveg, szabaly_fajta, dontesi_mod, jovahagyta, dok_fejezet")


def szabalyok(conn, kod: str, fejezet: str | None = None) -> list[dict]:
    cur = conn.cursor()
    rid = _rendszer_id(cur, kod)
    sql = (f"SELECT {_SZABALY_OSZLOPOK} FROM licitmenet"
           " WHERE rendszer_id=%s AND tipus='SZABALY'")
    arg: list = [rid]
    if fejezet is not None:
        sql += " AND COALESCE(fejezet,'')=%s"
        arg.append(fejezet)
    nevek = [x.strip() for x in _SZABALY_OSZLOPOK.split(",")]
    try:
        cur.execute(sql.replace("SELECT " + _SZABALY_OSZLOPOK,
                                "SELECT " + _SZABALY_OSZLOPOK + ", jegyzet")
                    + " ORDER BY seq", arg)
        nevek = nevek + ["jegyzet"]
    except Exception:              # noqa: BLE001 — a 022 még nem futott le
        cur.execute(sql + " ORDER BY seq", arg)
    ki = [dict(zip(nevek, r)) for r in cur.fetchall()]
    megj = _megjegyzes_szam(cur, kod)
    for s in ki:
        s["alert"] = bool(s["alert"])
        s["comments"] = megj.get(s["kulcs"], 0)
        s["row_kind"] = ("LEHETOSEG" if "~" in (s["kulcs"] or "") else
                         s.get("szabaly_fajta") or "SZABALY")
    # Ugyanaz a folytatólagos sorrend, mint a feloldott nézetben; azonos
    # mintán belül a kártya sorrendje marad (a rendezés stabil).
    osz = osszevont_nyitasok(s["minta"] for s in ki)
    ki.sort(key=lambda s: menet_kulcs(s["minta"], osz))
    return ki


# --- Állapot-módosítás ---------------------------------------------------

def allapot_muvelet(conn, kod: str, muvelet: str, ids: list[int] | None = None,
                    fejezet: str | None = None, ki: str = "") -> int:
    """
    `muvelet`: jovahagy / jegel / kiolvaszt / visszavon. Vagy a megadott
    szabályokra (`ids`), vagy egy egész fejezetre. Egy egész rendszert
    egyszerre nem lehet: az túl nagy, véletlen kattintás lenne.
    """
    if muvelet not in MUVELETEK:
        raise SzerkesztoHiba(f"Ismeretlen művelet: {muvelet}")
    if not ids and fejezet is None:
        raise SzerkesztoHiba("Szabály(ok) vagy fejezet kell")
    uj, honnan = MUVELETEK[muvelet]
    cur = conn.cursor()
    rid = _rendszer_id(cur, kod)
    helyek = ",".join(["%s"] * len(honnan))
    if uj == "ELFOGADOTT":
        sql = "UPDATE licitmenet SET allapot=%s, jovahagyta=%s, jovahagyva=%s"
        arg: list = [uj, (ki or "szerkesztő")[:60],
                     _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    else:
        sql = "UPDATE licitmenet SET allapot=%s"
        arg = [uj]
    sql += (f" WHERE rendszer_id=%s AND tipus='SZABALY'"
            f" AND allapot IN ({helyek})")
    arg += [rid, *honnan]
    if ids:
        sql += " AND id IN (" + ",".join(["%s"] * len(ids)) + ")"
        arg += [int(i) for i in ids]
    else:
        sql += " AND COALESCE(fejezet,'')=%s"
        arg.append(fejezet)
    cur.execute(sql, arg)
    n = cur.rowcount
    conn.commit()
    return n


# --- Megjegyzések ----------------------------------------------------------

def _megjegyzes_szam(cur, kod: str) -> dict[str, int]:
    try:
        cur.execute("SELECT kulcs, COUNT(*) FROM szerkeszto_megjegyzes"
                    " WHERE rendszer_kod=%s AND allapot='NYITOTT'"
                    " GROUP BY kulcs", (kod,))
    except Exception:              # noqa: BLE001 — a 021 még nem futott le
        return {}
    return {k: int(n) for k, n in cur.fetchall() if k}


def megjegyzes_ment(conn, adat: dict) -> int:
    szoveg = str(adat.get("text") or "").strip()
    if not szoveg:
        raise SzerkesztoHiba("Üres megjegyzés")
    kod = str(adat.get("system") or "").strip()
    if not kod:
        raise SzerkesztoHiba("A 'system' kötelező")
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO szerkeszto_megjegyzes (rendszer_kod, fejezet, kulcs,"
            " minta, licitmenet_id, szoveg, szerzo) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (kod, adat.get("chapter"), adat.get("key"), adat.get("pattern"),
             adat.get("rule_id"), szoveg[:10000], (adat.get("author") or "")[:60]))
    except Exception as e:         # noqa: BLE001
        raise SzerkesztoHiba("A megjegyzésekhez futtasd a "
                             "schema/021_szerkeszto.sql-t") from e
    conn.commit()
    return cur.lastrowid


def megjegyzesek(conn, kod: str | None = None, kulcs: str | None = None,
                 csak_nyitott: bool = True) -> list[dict]:
    cur = conn.cursor()
    sql = ("SELECT id, rendszer_kod, fejezet, kulcs, minta, szoveg, szerzo,"
           " allapot, letrehozva FROM szerkeszto_megjegyzes WHERE 1=1")
    arg: list = []
    if kod:
        sql += " AND rendszer_kod=%s"
        arg.append(kod)
    if kulcs is not None:
        sql += " AND COALESCE(kulcs,'')=%s"
        arg.append(kulcs)
    if csak_nyitott:
        sql += " AND allapot='NYITOTT'"
    try:
        cur.execute(sql + " ORDER BY id", arg)
    except Exception:              # noqa: BLE001 — a 021 még nem futott le
        return []
    return [{"id": r[0], "system": r[1], "chapter": r[2], "key": r[3],
             "pattern": r[4], "text": r[5], "author": r[6], "state": r[7],
             "created": str(r[8])} for r in cur.fetchall()]


def megjegyzes_lezar(conn, mid: int) -> None:
    cur = conn.cursor()
    cur.execute("UPDATE szerkeszto_megjegyzes SET allapot='LEZART' WHERE id=%s",
                (int(mid),))
    conn.commit()


def export(conn) -> dict:
    """Egy fájlba minden, amit Claude-nak látnia kell: a nyitott
    megjegyzések és a rendszerek állapota."""
    ki = {
        "exported": _dt.datetime.now().isoformat(timespec="seconds"),
        "comments": megjegyzesek(conn),
        "systems": [{"code": r["code"], "kind": r["kind"],
                     "counts": r.get("counts", {})} for r in rendszerek(conn)],
    }
    try:                           # a jelzésrendszerek (030), ha vannak
        from .jelzes_szerk import jelzes_rendszerek
        ki["signal_systems"] = [{"code": r["code"], "kind": r["kind"],
                                 "counts": r["counts"]} for r in jelzes_rendszerek(conn)]
    except Exception:              # noqa: BLE001
        pass
    return ki


def export_json(conn) -> str:
    return json.dumps(export(conn), ensure_ascii=False, indent=1)


# --- Feloldott nézet: egy RENDSZER összes szabálya, forrással -------------

def feloldott(conn, kod: str, elotag: str | None = None,
              csak_nyitas: bool = False, teszt: bool = True) -> dict:
    """
    A rendszer szabályai a FELOLDÁS UTÁN — vagyis azok, amelyekkel a kibic
    ténylegesen licitál, bármelyik alaprendszerből vagy konvencióból
    jönnek. Szűrés: nyitások (egyetlen licit), vagy a minta eleje
    (pl. "1NT-" = minden az 1NT nyitás után).
    """
    from ..motor.feloldas import feloldas
    from ..motor.licital import licit_rang
    f = feloldas(conn, kod, teszt=teszt)
    ki = []
    for s in f.sorok:
        m = s.minta or ""
        if csak_nyitas and ("-" in m or "(" in m or " " in m or m.startswith("..")):
            continue
        if elotag and not elotag_illik(elotag, m):
            continue
        ki.append({
            "minta": m, "kulcs": s.kulcs, "prioritas": s.prioritas,
            "magyarazat": s.magyarazat, "feltetel_szoveg": s.feltetel_szoveg,
            "ha_feltetel_szoveg": s.ha_feltetel_szoveg, "alert": bool(s.alert),
            "forsz": s.forsz, "dontesi_mod": s.dontesi_mod,
            "szabaly_fajta": s.szabaly_fajta, "fejezet": s.fejezet,
            "source": s.rendszer_kod, "id": s.licitmenet_id,
            "row_kind": "LEHETOSEG" if "~" in (s.kulcs or "") else s.szabaly_fajta,
        })
    osz = osszevont_nyitasok(x["minta"] for x in ki)
    ki.sort(key=lambda x: (menet_kulcs(x["minta"], osz), x["minta"],
                           -(x["prioritas"] or 0)))
    return {"system": kod, "rules": ki, "total": len(f.sorok)}


# --- Keresés a feloldott nézetben: a minta ILLESZKEDIK a beírt menetre ----

def _kereses_norm(s: str) -> str:
    """ "1s-1n" -> "1S-1N": a színbetűk nagybetűsek; az `m` (minor) marad."""
    s = (s or "").strip()
    s = re.sub(r"(?<=[1-7n+])(nt|[cdhsn])", lambda x: x.group(1).upper(), s)
    return re.sub(r"\b(p|x|xx)\b", lambda x: x.group(1).upper(), s)


def _szin_halmaz(szin: str | None, kotes: dict | None = None) -> set | None:
    """Egy token lehetséges színei (None: nem színlicit)."""
    from ..motor.minta import MINOROK, NEMESEK, SZINEK, VALTOZOK
    if szin is None:
        return None
    if szin == "NT":
        return {"NT"}
    if szin in SZINEK:
        return {szin}
    kotes = kotes or {}
    if szin in VALTOZOK:
        return {kotes[szin]} if szin in kotes else set(VALTOZOK[szin])
    if szin == "oM":
        return set(NEMESEK) - {kotes["M"]} if "M" in kotes else set(NEMESEK)
    if szin == "om":
        return set(MINOROK) - {kotes["m"]} if "m" in kotes else set(MINOROK)
    return set(SZINEK)                     # Q, I1, V2 …: bármelyik szín


def elotag_illik(kereses: str, minta: str) -> bool:
    """
    A feloldott nézet keresője: a szabály MINTÁJA illeszkedik-e a beírt
    menet elejére. Nem betűre hasonlít, hanem licitre: az "1S-1N" megtalálja
    az "1M-1NT"-t is (M = bármelyik nemes), az "1M" az 1♥, 1♠ és 1M
    kezdetűeket, az "1m-1H" az 1♣-1♥-et is. A változó kötése számít: az
    "1S-2H" nem hozza az "1M-2M"-et (az ott 1♠-2♠ volna).
    A végén kötőjel ("1NT-"): csak ami utána jön, maga az 1NT nem. Ha a
    keresés nem minta, betű szerinti előtag marad.
    """
    from ..motor.minta import MintaHiba, minta_parse
    k = _kereses_norm(kereses).strip()
    utana = k.endswith("-")                # "1NT-": csak ami UTÁNA jön
    k = k.rstrip("-").strip()
    if not k:
        return True
    try:
        q = minta_parse(k)
        r = minta_parse(minta)
    except (MintaHiba, Exception):        # noqa: BLE001
        # betű szerint, de az m (minor) és az M (nemes) NEM ugyanaz
        return (minta or "").startswith(_kereses_norm(kereses))
    if r.barmennyi or len(r.tokenek) < len(q.tokenek) + (1 if utana else 0):
        return False
    if len(q.tokenek) > 1 and q.paroslicit != r.paroslicit:
        return False
    kotes: dict = {}
    for qt, rt in zip(q.tokenek, r.tokenek):
        if qt.ellenfel != rt.ellenfel:
            return False
        if qt.helyettesito or rt.helyettesito:
            continue
        if bool(qt.hivas) != bool(rt.hivas):
            return False
        if qt.hivas:
            if qt.hivas != rt.hivas:
                return False
            continue
        if (qt.szint not in ("n", "+") and rt.szint not in ("n", "+")
                and qt.szint != rt.szint):
            return False
        kozos = _szin_halmaz(qt.szin) & _szin_halmaz(rt.szin, kotes)
        if not kozos:
            return False
        if rt.szin in ("M", "m", "A", "B", "E") and rt.szin not in kotes \
                and len(kozos) == 1:
            kotes[rt.szin] = next(iter(kozos))
    return True


# ♣, ♦, m (bármelyik minor), ♥, ♠, M (bármelyik nemes), egyéb változó, NT
_SZIN_SOR = {"C": 0, "D": 1, "m": 2, "om": 2, "H": 3, "S": 4, "M": 5, "oM": 5,
             "NT": 8}
_HIVAS_SOR = {"P": -3, "X": -2, "XX": -1}


def _token_rang(t) -> float:
    if t is None:
        return -3                          # hallgatólagos passz
    if t.helyettesito:
        return 95
    if t.hivas:
        return _HIVAS_SOR.get(t.hivas, 90)
    szint = int(t.szint) if (t.szint or "").isdigit() else 8
    return szint * 10 + _SZIN_SOR.get(t.szin or "", 6)


# Színcsaládok: az "1m" nyitás az 1♣ és az 1♦ közös ága, az "1M" az 1♥-é
# és az 1♠-é.
_CSALAD = {"C": "m", "D": "m", "m": "m", "H": "M", "S": "M", "M": "M"}
_CSALAD_RANG = {"m": 0, "M": 3}


def osszevont_nyitasok(mintak) -> frozenset:
    """
    Mely nyitásokat kell EGY ágként rendezni? Azokat, amelyekhez van
    változós ("1m…", "1M…") szabály is: {(1, "m")} esetén az 1♣, az 1♦ és
    az 1m ága összefésülődik, és a VÁLASZ dönt előbb, nem a nyitás színe:
    1♣-1♥, 1♦-1♥, 1m-1♥, 1♣-1♠ … 1m-1NT. Ahol nincs változós nyitás
    (pl. 2♣ erős, 2♦ gyenge), a két ág külön marad.
    """
    from ..motor.minta import minta_parse
    ki = set()
    for m in mintak:
        try:
            t = minta_parse(m).tokenek[0]
        except Exception:                  # noqa: BLE001
            continue
        if t.szin in ("m", "M") and (t.szint or "").isdigit():
            ki.add((t.szint, t.szin))
    return frozenset(ki)


def menet_kulcs(minta: str, osszevont: frozenset = frozenset()) -> tuple:
    """
    "Folytatólagos" sorrend: minden licitmenet után közvetlenül a
    folytatásai jönnek. Egy nyitáson belül előbb a teljes PÁROSLICIT
    (az ellenfél végig passzol), csak utána a KÜZDELMI menetek:
        1♥, 1♥–1♠, 1♥–1♠–2♣, 1♥–1NT, … | 1♥ (X) 1♠, 1♥ (1♠) X, …
    A küzdelmi részben az ellenfél licitje dönt előbb (kontra < rekontra
    < szín), azon belül a mi válaszunk. Előbb a mi nyitásaink, aztán a
    védekező menetek (az ellenfél nyitott), végül az elvek ("..").
    """
    from ..motor.minta import MintaHiba, minta_parse
    if ".." in (minta or ""):
        return (2, minta)
    try:
        m = minta_parse(minta)
    except (MintaHiba, Exception):         # noqa: BLE001
        return (3, minta)
    elso = m.tokenek[0] if m.tokenek else None
    csalad = _CSALAD.get(elso.szin or "") if elso is not None else None
    # Összevont ágban a nyitás a családja rangját kapja; a pontos szín
    # (♣ < ♦ < m) csak a legvégén dönt.
    osszefesul = csalad and (elso.szint, csalad) in osszevont
    vegso = _token_rang(elso) if osszefesul else 0

    def rang(t):
        if osszefesul and t is elso:
            return int(elso.szint) * 10 + _CSALAD_RANG[csalad]
        return _token_rang(t)

    kulcs: list = []
    fuggo = None
    kuzdelmi = 0
    for t in m.tokenek:
        if t.ellenfel:
            fuggo = t
            if t.hivas != "P":
                kuzdelmi = 1
            continue
        kulcs.append((rang(fuggo) if fuggo is not None else -3, rang(t)))
        fuggo = None
    if fuggo is not None:                  # az ellenfél licitjével zárul
        kulcs.append((rang(fuggo), -4))
    if elso is not None and elso.ellenfel:
        return (1, tuple(kulcs[:1]), 0, tuple(kulcs[1:]), vegso)
    return (0, tuple(kulcs[:1]), kuzdelmi, tuple(kulcs[1:]), vegso)
