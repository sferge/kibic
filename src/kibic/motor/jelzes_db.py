"""
A jelzésrendszerek az adatbázisból (schema/030_jelzesmenet.sql, 031).

    jelzesrendszer   egy sor rendszerenként: kód, név, fajta, jegyzetek
    jelzesmenet      a sorok, mint a licitmenet:
                       tipus = HIVATKOZAS: hivatkozás (BE) vagy kizárás (KI,
                         esetleg egy fejezetre), `seq` sorrendben;
                       tipus = SZABALY: fajta (SZABALY/ELV/KIVETEL/KIHAGYAS),
                         terület, kulcs, `adat` (JSON), állapot, jóváhagyó

A YAML a kanonikus alak (rendszerek/jelzesek/); a tábla abból származik,
egyetlen dolog él csak itt: a JÓVÁHAGYÁS (állapot, jóváhagyó).
"""
from __future__ import annotations

import json

from .jelzes import JelzesRendszer, JSor, Kizaras


def _json(x):
    if x is None:
        return None
    return json.loads(x) if isinstance(x, (str, bytes, bytearray)) else x


def rendszerek_db(conn, csak_aktiv: bool = True) -> dict[str, JelzesRendszer]:
    cur = conn.cursor()
    cur.execute("SELECT id, kod, nev, fajta, verzio, forras, leiras, jegyzet,"
                " fejezet_jegyzetek FROM jelzesrendszer"
                + (" WHERE aktiv = 1" if csak_aktiv else ""))
    ki: dict[str, JelzesRendszer] = {}
    idk: dict[int, JelzesRendszer] = {}
    for (rid, kod, nev, fajta, verzio, forras, leiras, jegyzet, fj) in cur.fetchall():
        r = JelzesRendszer(kod=kod, nev=nev, fajta=fajta, verzio=verzio, forras=forras,
                           leiras=leiras, jegyzet=jegyzet,
                           fejezet_jegyzetek=_json(fj) or {}, fajl=f"db:{kod}")
        ki[kod] = r
        idk[rid] = r
    if not idk:
        return ki
    cur.execute("SELECT id, kod FROM jelzesrendszer")
    kodok = {i: k for i, k in cur.fetchall()}
    cur.execute("SELECT jelzesrendszer_id, tipus, fajta, terulet, kulcs, adat, fejezet, seq,"
                " allapot, megjegyzes, jegyzet, jovahagyta, hivatkozott_id, hivatkozas_mod,"
                " hivatkozas_aktiv, kizart_fejezet FROM jelzesmenet ORDER BY seq, id")
    for (rid, tipus, fajta, terulet, kulcs, adat, fejezet, seq, allapot, megj, jegyzet, jov,
         hid, hmod, haktiv, kfej) in cur.fetchall():
        r = idk.get(rid)
        if r is None:
            continue
        if tipus == "HIVATKOZAS":
            cel = kodok.get(hid)
            if cel is None or not haktiv:
                continue
            if hmod == "KI":
                r.kizarasok.append(Kizaras(kod=cel, fejezet=kfej))
            elif cel not in r.hivatkozasok:
                r.hivatkozasok.append(cel)
            continue
        r.sorok.append(JSor(fajta=fajta, terulet=terulet, kulcs=kulcs, adat=_json(adat) or {},
                            fejezet=fejezet, seq=seq, allapot=allapot, megjegyzes=megj,
                            jegyzet=jegyzet, eredet=r.kod, jovahagyta=jov))
    return ki
