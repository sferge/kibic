"""
A RENDSZERSZERKESZTŐ jelzés-oldala (GET /szerkeszto, Jelzések lap).

Ugyanaz, mint a licit-oldal, a jelzésrendszerekre (schema/030_jelzesmenet.sql):

  * a jelzésrendszerek listája, állapot-összesítővel; melyik licitrendszer
    melyiket játssza;
  * egy jelzésrendszer adatai és SAJÁT hivatkozásai (beemelés, kizárás) —
    mint a licitnél a „Rendszer” doboz;
  * a hivatkozási fa és a feloldás: mit hoz be, mit ír felül, mit hagy ki,
    mit zár ki (a feloldás ugyanaz, mint a licité);
  * fejezetek és sorok emberi nyelven, jóváhagyás / jegelés / kiolvasztás /
    visszavonás soronként vagy fejezetenként;
  * megjegyzés sorhoz vagy fejezethez (a szerkeszto_megjegyzes táblába, a
    jelzésrendszer kódjával);
  * lapállás-próba: mit hív a kibic, melyik sor miatt, mi állt mögötte.

A sorok TARTALMA itt sem szerkeszthető: a YAML a kanonikus alak, a változás
megjegyzésben megy Claude-nak (mint a licitnél).
"""
from __future__ import annotations

import datetime as _dt

from .szerkeszto import MUVELETEK, SzerkesztoHiba, _megjegyzes_szam


def _rid(cur, kod: str) -> int:
    cur.execute("SELECT id FROM jelzesrendszer WHERE kod=%s", (kod,))
    r = cur.fetchone()
    if not r:
        raise SzerkesztoHiba(f"Nincs ilyen jelzésrendszer: {kod}")
    return r[0]


def _rendszerek(conn):
    from ..motor.jelzes_db import rendszerek_db
    try:
        return rendszerek_db(conn)
    except Exception as e:         # noqa: BLE001 — a 030 még nem futott le
        raise SzerkesztoHiba("A jelzésrendszerekhez futtasd a "
                             "schema/030_jelzesmenet.sql-t, utána a rendszerimportot") from e


def jelzes_rendszerek(conn) -> list[dict]:
    """A jelzésrendszerek, állapot-összesítővel; ki játssza őket."""
    rr = _rendszerek(conn)
    cur = conn.cursor()
    cur.execute("SELECT r.kod, m.allapot, COUNT(*) FROM jelzesmenet m"
                " JOIN jelzesrendszer r ON r.id = m.jelzesrendszer_id"
                " WHERE m.tipus='SZABALY' GROUP BY r.kod, m.allapot")
    szam: dict[str, dict] = {}
    for kod, allapot, db in cur.fetchall():
        szam.setdefault(kod, {})[allapot] = int(db)
    jatssza: dict[str, list[str]] = {}
    try:
        cur.execute("SELECT kod, jelzesek FROM rendszer WHERE aktiv=1 AND jelzesek IS NOT NULL")
        import json
        for kod, j in cur.fetchall():
            d = json.loads(j) if isinstance(j, (str, bytes)) else j
            if isinstance(d, dict) and d.get("rendszer"):
                jatssza.setdefault(d["rendszer"], []).append(kod)
    except Exception:              # noqa: BLE001 — a 029 nélkül
        pass
    sorrend = {"RENDSZER": 0, "ALAPRENDSZER": 1, "KONVENCIO": 2}
    return sorted(({"code": r.kod, "name": r.nev, "kind": r.fajta, "version": r.verzio,
                    "references": list(r.hivatkozasok), "counts": szam.get(r.kod, {}),
                    "played_by": sorted(jatssza.get(r.kod, []))}
                   for r in rr.values()),
                  key=lambda x: (sorrend.get(x["kind"], 9), x["code"]))


def jelzes_rendszer(conn, kod: str) -> dict:
    """Egy jelzésrendszer adatai és SAJÁT hivatkozásai (a licit `rendszer_info` párja)."""
    cur = conn.cursor()
    rid = _rid(cur, kod)
    rr = _rendszerek(conn)
    r = rr.get(kod)
    cur.execute("SELECT c.kod, c.fajta, m.hivatkozas_mod, m.kizart_fejezet, m.hivatkozas_aktiv"
                " FROM jelzesmenet m JOIN jelzesrendszer c ON c.id = m.hivatkozott_id"
                " WHERE m.jelzesrendszer_id=%s AND m.tipus='HIVATKOZAS' ORDER BY m.seq", (rid,))
    refs = [{"target": cel, "kind": fajta, "type": "KIZARAS" if mod == "KI" else "BEEMELES",
             "chapter": fej, "active": bool(aktiv)}
            for cel, fajta, mod, fej, aktiv in cur.fetchall()]
    lista = {x["code"]: x for x in jelzes_rendszerek(conn)}
    x = lista.get(kod, {})
    return {"code": kod, "name": r.nev if r else kod, "kind": r.fajta if r else None,
            "version": r.verzio if r else None, "source": r.forras if r else None,
            "description": r.leiras if r else None, "note": r.jegyzet if r else None,
            "references": refs, "played_by": x.get("played_by", []),
            "counts": x.get("counts", {})}


def jelzes_fa(conn, kod: str, szint: str = "TESZT") -> dict:
    """A feloldás: lánc, felülírások, törlések, kizárások."""
    from ..motor.jelzes import feloldas
    rr = _rendszerek(conn)
    if kod not in rr:
        raise SzerkesztoHiba(f"Nincs ilyen jelzésrendszer: {kod}")
    f = feloldas(kod, rr, szint)
    return {
        "system": kod, "rules": len(f.sorok),
        "chain": [{"code": k, "depth": m, "kind": rr[k].fajta, "name": rr[k].nev,
                   "references": list(rr[k].hivatkozasok),
                   "exclusions": [{"code": z.kod, "chapter": z.fejezet} for z in rr[k].kizarasok],
                   "source": rr[k].forras, "note": rr[k].jegyzet}
                  for k, m in f.lanc],
        "overridden": [{"key": k, "winner": ny, "loser": v} for k, ny, v in f.felulirt],
        "skipped": [{"key": k, "by": ki, "from": kie} for k, ki, kie in f.torolt],
        "excluded": [{"system": k, "chapter": fej, "by": ki} for k, fej, ki in f.kizart],
        "missing": list(f.hianyzo),
        # mint a licit fa: figyelmeztetések és tájékoztatások
        "warnings": ([f"HIÁNYZÓ jelzésrendszer: {k}" for k in f.hianyzo]
                     + [f"KÖRKÖRÖS hivatkozás (kimaradt): {x}" for x in f.korkoros]
                     + [f"HATÁSTALAN KIZÁRÁS: {ki}: {k}" + (f" / „{fej}”" if fej else "")
                        + " — nincs ilyen a hivatkozott fában"
                        for ki, k, fej in f.hatastalan_kizarasok]
                     + [f"KIVÉTEL ELV NÉLKÜL: {k} — nincs ilyen elv a feloldásban"
                        for k in f.kivetel_elv_nelkul]),
        "info": ([f"kizárva: {k}" + (f" / „{fej}”" if fej else "") + f" (kizárta: {ki})"
                  for k, fej, ki in f.kizart]
                 + [f"kihagyva: {k} ({kie}) — {ki} hagyta ki" for k, ki, kie in f.torolt]),
    }


def jelzes_fejezetek(conn, kod: str) -> list[dict]:
    cur = conn.cursor()
    rid = _rid(cur, kod)
    rr = _rendszerek(conn)
    jegyzet = rr[kod].fejezet_jegyzetek if kod in rr else {}
    cur.execute("SELECT fejezet, allapot, COUNT(*), MIN(seq) FROM jelzesmenet"
                " WHERE jelzesrendszer_id=%s AND tipus='SZABALY'"
                " GROUP BY fejezet, allapot", (rid,))
    ki: dict[str, dict] = {}
    for fej, allapot, db, seq in cur.fetchall():
        f = ki.setdefault(fej or "", {"chapter": fej or "", "counts": {}, "total": 0,
                                      "seq": seq})
        f["counts"][allapot] = int(db)
        f["total"] += int(db)
        f["seq"] = min(f["seq"], seq)
    for f in ki.values():
        f["note"] = jegyzet.get(f["chapter"])
    return sorted(ki.values(), key=lambda x: x["seq"])


def jelzes_sorok(conn, kod: str, fejezet: str | None = None) -> list[dict]:
    """
    A jelzésrendszer SAJÁT sorai. Ha a rendszer másra épül, minden sornál
    jelzi, hogy egy örökölt sort ír-e felül (és kiét).
    """
    from ..motor.jelzes import feloldas
    cur = conn.cursor()
    rid = _rid(cur, kod)
    sql = ("SELECT id, fejezet, seq, fajta, terulet, kulcs, szoveg, allapot, jovahagyta,"
           " megjegyzes, jegyzet FROM jelzesmenet WHERE jelzesrendszer_id=%s"
           " AND tipus='SZABALY'")
    arg: list = [rid]
    if fejezet is not None:
        sql += " AND COALESCE(fejezet,'')=%s"
        arg.append(fejezet)
    cur.execute(sql + " ORDER BY seq, id", arg)
    nevek = ("id", "chapter", "seq", "kind", "area", "key", "text", "state", "approved_by",
             "comment", "note")
    ki = [dict(zip(nevek, r)) for r in cur.fetchall()]
    # mit ír felül: a hivatkozott rendszerek feloldott kulcsai (kártya-szint)
    rr = _rendszerek(conn)
    orokolt: dict[str, str] = {}
    for h in (rr[kod].hivatkozasok if kod in rr else []):
        if h in rr:
            for s in feloldas(h, rr, "KARTYA").sorok:
                orokolt.setdefault(s.kulcs, s.eredet)
    megj = _megjegyzes_szam(cur, kod)
    for s in ki:
        s["overrides"] = orokolt.get(s["key"]) if s["kind"] != "KIHAGYAS" else None
        s["skips"] = orokolt.get(s["key"]) if s["kind"] == "KIHAGYAS" else None
        s["comments"] = megj.get(s["key"], 0)
    return ki


def jelzes_feloldott(conn, kod: str, szint: str = "TESZT") -> dict:
    """A feloldott sorok, ahonnan jönnek — ezekkel dolgozik a kibic."""
    from ..motor.jelzes import SZINTEK, feloldas, sor_szoveg
    if szint not in SZINTEK:
        raise SzerkesztoHiba(f"Ismeretlen szint: {szint}")
    rr = _rendszerek(conn)
    if kod not in rr:
        raise SzerkesztoHiba(f"Nincs ilyen jelzésrendszer: {kod}")
    f = feloldas(kod, rr, szint)
    return {"system": kod, "level": szint,
            "rules": [{"key": s.kulcs, "kind": s.fajta, "area": s.terulet, "chapter": s.fejezet,
                       "source": s.eredet, "depth": s.melyseg, "state": s.allapot,
                       "text": sor_szoveg(s)} for s in f.sorok]}


def jelzes_proba(conn, kod: str, lap: str, helyzet: str = "INDITAS",
                 szint: str = "TESZT", kontextus: list[str] | None = None) -> dict:
    """Mit hív a kibic ebből a lapállásból (szín és szan ellen), és miért."""
    from ..motor.jelzes import (FELVETELEK, HELYZETEK, SZINTEK, JelzesHiba, jelzesek,
                                lapok, szep, szep_szin)
    if helyzet not in HELYZETEK or szint not in SZINTEK:
        raise SzerkesztoHiba("Ismeretlen helyzet vagy szint")
    try:
        lapsor = lapok(lap)
    except JelzesHiba as e:
        raise SzerkesztoHiba(str(e)) from e
    if not lapsor:
        raise SzerkesztoHiba("Üres lapállás")
    j = jelzesek(kod, _rendszerek(conn), szint)
    ki = {"system": kod, "holding": szep_szin(lapsor), "situation": helyzet,
          "level": szint, "results": []}
    for f in FELVETELEK:
        jel = j.jeloltek(lapsor, f, helyzet, kontextus or ())
        if not jel and helyzet == "PARTNER_SZINE":
            jel = j.jeloltek(lapsor, f, "INDITAS", kontextus or ())
        valasztott, _ = j.indito_lap(lapsor, f, helyzet, kontextus or ())
        ki["results"].append({
            "contract": f, "card": szep(valasztott) if valasztott else None,
            "candidates": [{"key": s.kulcs, "source": s.eredet, "state": s.allapot,
                            "specificity": s.konkretsag, "pattern": s.minta.szoveg,
                            "note": s.megjegyzes} for s in jel]})
    return ki


def jelzes_allapot_muvelet(conn, kod: str, muvelet: str, ids: list[int] | None = None,
                           fejezet: str | None = None, ki: str = "") -> int:
    """Mint a licitnél: soronként (`ids`) vagy egy egész fejezetre."""
    if muvelet not in MUVELETEK:
        raise SzerkesztoHiba(f"Ismeretlen művelet: {muvelet}")
    if not ids and fejezet is None:
        raise SzerkesztoHiba("Sor(ok) vagy fejezet kell")
    uj, honnan = MUVELETEK[muvelet]
    cur = conn.cursor()
    rid = _rid(cur, kod)
    if uj == "ELFOGADOTT":
        sql = "UPDATE jelzesmenet SET allapot=%s, jovahagyta=%s, jovahagyva=%s"
        arg: list = [uj, (ki or "szerkesztő")[:60],
                     _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    else:
        sql = "UPDATE jelzesmenet SET allapot=%s"
        arg = [uj]
    sql += (" WHERE jelzesrendszer_id=%s AND tipus='SZABALY' AND allapot IN ("
            + ",".join(["%s"] * len(honnan)) + ")")
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
