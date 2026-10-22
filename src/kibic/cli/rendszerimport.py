"""
YAML-FORRÁSBÓL AZ ADATBÁZISBA: rendszerek és konvenciók betöltése.

    python -m kibic.cli.rendszerimport rendszerek/yaml/
    python -m kibic.cli.rendszerimport rendszerek/yaml/ --csak STAYMAN --probafutas
    python -m kibic.cli.rendszerimport --jovahagy STAYMAN --ki "sanyi"
    python -m kibic.cli.rendszerimport --jovahagy KIBICEGY_STAND --fejezet "Az 1NT indulás"
    python -m kibic.cli.rendszerimport --jegel KIBICEGY_STAND --minta "1NT-4S"
    python -m kibic.cli.rendszerimport --kiolvaszt KIBICEGY_STAND --minta "1NT-4S"

TESZT MÓD: a motor élesben csak az ELFOGADOTT sorokat használja; teszt
módban (KIBIC_TESZT_MOD=1, vagy a kérésben "test_mode": true) a JAVASOLT
és FELULVIZSGALANDO sorokat is. A JEGELT sort egyik mód sem használja.

A YAML a KANONIKUS alak; az adatbázis sorai ebből származnak, és egy
újraimport a rendszer MINDEN sorát újraírja. Egyetlen dolog él csak az
adatbázisban: a JÓVÁHAGYÁS. Ezt az import megőrzi:

  * ha egy sor tartalma (minta, kulcs, feltétel, jelentés, helyzet)
    VÁLTOZATLAN, az állapota és a jóváhagyója marad;
  * ha egy korábban ELFOGADOTT sor tartalma megváltozott, az új sor
    FELULVIZSGALANDO lesz — a motor nem használja, amíg újra jóvá nem
    hagyod;
  * minden új sor JAVASOLT;
  * a YAML `allapot:` kulcsa mindezt felülírja.

Védelem: egy olyan rendszerbe, amelynek vannak NEM YAML-ból jött sorai
(pl. a LICREN-import), csak `--kenyszer`-rel lehet importálni — különben
egy elírt kód letörölhetné a LICREN_STAND-ot.

KÁRTYAJELZÉSEK: a rendszerek/jelzesek/ jelzésrendszereit is betölti (a
`jelzesrendszer` / `jelzesmenet` táblákba, a jóváhagyás megőrzésével), és a
rendszerek `jelzesek:` profilját a `rendszer.jelzesek` oszlopba
(schema/029_jelzes.sql, 030_jelzesmenet.sql). Más könyvtár: --jelzesek UT;
kikapcsolva: --jelzesek ''.

Az import után a futó szolgáltatásnak szólni kell:
    curl -X POST http://localhost:9050/v1/kibic/ujratolt
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

from ..impex.rendszer_yaml import (ForrasHiba, RendszerForras, SzabalySor,
                                   betolt, import_sorrend)

YAML_JEL = "yaml:"          # a dok_fejezet oszlopban: honnan jött a sor


def _kapcsolat(a):
    try:
        import pymysql
    except ImportError:
        print("A pymysql csomag nem érhető el.", file=sys.stderr)
        sys.exit(2)
    return pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4",
                           autocommit=False)


def _kanon(x) -> str:
    """JSON összehasonlítható alakja (a MySQL szövegként is adhatja)."""
    if x is None:
        return "null"
    if isinstance(x, (str, bytes)):
        try:
            x = json.loads(x)
        except ValueError:
            return str(x)
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def alairas(minta, kulcs, feltetel, jelentes, ha) -> tuple:
    return (str(minta), str(kulcs), _kanon(feltetel), _kanon(jelentes),
            _kanon(ha))


def uj_allapotok(uj: list[SzabalySor], regi: list[tuple]
                 ) -> list[tuple[str, str | None, object]]:
    """
    A jóváhagyás megőrzése. `regi`: (minta, kulcs, feltetel, jelentes,
    ha_feltetel, allapot, jovahagyta, jovahagyva) sorok.
    Visszaad soronként: (allapot, jovahagyta, jovahagyva).

    Tiszta függvény, hogy adatbázis nélkül tesztelhető legyen.
    """
    alairt: dict[tuple, list[tuple]] = {}
    elfogadott_minta: set[tuple] = set()
    for (m, k, f, j, h, all_, ki, mikor) in regi:
        alairt.setdefault(alairas(m, k, f, j, h), []).append((all_, ki, mikor))
        if all_ == "ELFOGADOTT":
            elfogadott_minta.add((str(m), str(k)))
    ki_lista = []
    for s in uj:
        if s.allapot:
            ki_lista.append((s.allapot, None, None))
            continue
        a = alairas(s.minta, s.kulcs, s.feltetel, s.jelentes, s.ha_feltetel)
        if alairt.get(a):
            ki_lista.append(alairt[a].pop(0))
        elif (s.minta, s.kulcs) in elfogadott_minta:
            ki_lista.append(("FELULVIZSGALANDO", None, None))
        else:
            ki_lista.append(("JAVASOLT", None, None))
    return ki_lista


# --- Írás --------------------------------------------------------------

def _migracio_019(cur) -> None:
    """Az új fajtanevekhez, a témához és a kizáráshoz a 019 kell."""
    cur.execute("SHOW COLUMNS FROM licitmenet LIKE 'hivatkozas_mod'")
    if not cur.fetchone():
        raise SystemExit("Előbb futtasd a schema/019_rendszerfajtak.sql-t "
                         "(új rendszer-fajták, téma, kizárás).")
    cur.execute("SHOW COLUMNS FROM rendszer LIKE 'alapja'")
    if not cur.fetchone():
        raise SystemExit("Előbb futtasd a schema/020_modositott_konvencio.sql-t "
                         "(módosított konvenció, változat).")
    cur.execute("SHOW COLUMNS FROM licitmenet LIKE 'jegyzet'")
    if not cur.fetchone():
        raise SystemExit("Előbb futtasd a schema/022_jegyzet.sql-t (jegyzetek).")
    # A `minoseg:` kulcs a LAPMINOSEG értékelőt használja; nélküle a sor
    # CSENDBEN sosem illeszkedne (ismeretlen metrika).
    cur.execute("SELECT 1 FROM ertekelo WHERE kod='LAPMINOSEG' AND definicio IS NOT NULL")
    if not cur.fetchone():
        raise SystemExit("Előbb futtasd a schema/023_lapminoseg.sql-t (jó/rossz lap).")
    cur.execute("SHOW COLUMNS FROM rendszer LIKE 'fajta'")
    sor = cur.fetchone()
    if sor and "RENDSZERCSALAD" not in str(sor[1]):
        raise SystemExit("Előbb futtasd a schema/024_rendszercsalad.sql-t (rendszercsalád).")
    if sor and "ELV_SABLON" not in str(sor[1]):
        raise SystemExit("Előbb futtasd a schema/028_elv_sablon.sql-t (elv-sablon).")
    cur.execute("SHOW COLUMNS FROM licitmenet LIKE 'szabaly_fajta'")
    sor = cur.fetchone()
    if sor and "KIHAGYAS" not in str(sor[1]):
        raise SystemExit("Előbb futtasd a schema/031_jelzesmenet_szerkezet.sql-t "
                         "(TORLES -> KIHAGYAS, a jelzésmenet a licitmenet szerkezetével).")


def _migracio_030(cur) -> None:
    cur.execute("SHOW TABLES LIKE 'jelzesmenet'")
    ok = cur.fetchone()
    cur.execute("SHOW COLUMNS FROM rendszer LIKE 'jelzesek'")
    if not (ok and cur.fetchone()):
        raise SystemExit("Előbb futtasd a schema/029_jelzes.sql-t és a "
                         "schema/030_jelzesmenet.sql-t (kártyajelzések).")
    cur.execute("SHOW COLUMNS FROM jelzesmenet LIKE 'terulet'")
    sor = cur.fetchone()
    if sor and "SZINADAS" not in str(sor[1]):
        raise SystemExit("Előbb futtasd a schema/032_jelzes_szinadas.sql-t "
                         "(új jelzésterület: SZINADAS).")
    if not sor:
        raise SystemExit("Előbb futtasd a schema/031_jelzesmenet_szerkezet.sql-t "
                         "(a jelzésmenet a licitmenet szerkezetével).")


def jelzes_uj_allapotok(uj, regi: list[tuple]) -> list[tuple[str, str | None, object]]:
    """
    A jóváhagyás megőrzése a jelzésrendszer soraiban. `regi`: (fajta,
    kulcs, tartalom, allapot, jovahagyta, jovahagyva). Soronként:
    (allapot, jovahagyta, jovahagyva).

      * a YAML kimondott `allapot:`-a mindent felülír (mint a licitnél);
      * változatlan tartalmú sor: marad az állapota és a jóváhagyója
        (a szerkesztőben jóváhagyott vagy jegelt sor így megmarad);
      * ha egy ELFOGADOTT sor tartalma megváltozott: FELULVIZSGALANDO;
      * új sor: a YAML (rendszer szintű) alapállapota.
    """
    alairt: dict[tuple, list[tuple]] = {}
    elfogadott: set[tuple] = set()
    for (fajta, kulcs, tartalom, allapot, ki, mikor) in regi:
        alairt.setdefault((fajta, kulcs, tartalom), []).append((allapot, ki, mikor))
        if allapot == "ELFOGADOTT":
            elfogadott.add((fajta, kulcs))
    eredmeny = []
    for s in uj:
        if s.allapot_yamlbol:
            eredmeny.append((s.allapot, None, None))
            continue
        k = (s.fajta, s.kulcs, s.tartalom())
        if alairt.get(k):
            eredmeny.append(alairt[k].pop(0))
        elif (s.fajta, s.kulcs) in elfogadott:
            eredmeny.append(("FELULVIZSGALANDO", None, None))
        else:
            eredmeny.append((s.allapot, None, None))
    return eredmeny


def jelzesrendszer_fej(cur, r) -> int:
    """A jelzésrendszer fejsora (upsert) -> id. A hivatkozások előtt mindet."""
    cur.execute(
        "INSERT INTO jelzesrendszer (kod, nev, fajta, verzio, forras, leiras, jegyzet,"
        " fejezet_jegyzetek) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
        " ON DUPLICATE KEY UPDATE nev=VALUES(nev), fajta=VALUES(fajta), verzio=VALUES(verzio),"
        " forras=VALUES(forras), leiras=VALUES(leiras), jegyzet=VALUES(jegyzet),"
        " fejezet_jegyzetek=VALUES(fejezet_jegyzetek), aktiv=1",
        (r.kod, r.nev[:255], r.fajta, r.verzio[:20], (r.forras or "")[:255] or None,
         (r.leiras or "")[:1000] or None, r.jegyzet,
         json.dumps(r.fejezet_jegyzetek, ensure_ascii=False) if r.fejezet_jegyzetek else None))
    cur.execute("SELECT id FROM jelzesrendszer WHERE kod=%s", (r.kod,))
    return cur.fetchone()[0]


def jelzesrendszer_ir(cur, r) -> Counter:
    """
    Egy jelzésrendszer sorai, mint a licitmenetnél: elöl a HIVATKOZAS-sorok
    (BE: hivatkozás, KI: kizárás), utánuk a szabálysorok. A sorok teljes
    cseréje; a jóváhagyás marad, ha a sor tartalma nem változott.
    """
    from ..motor.jelzes import sor_szoveg
    rid = jelzesrendszer_fej(cur, r)
    cur.execute("SELECT fajta, kulcs, adat, allapot, jovahagyta, jovahagyva"
                " FROM jelzesmenet WHERE jelzesrendszer_id=%s AND tipus='SZABALY'", (rid,))
    regi = []
    for fajta, kulcs, adat, allapot, ki, mikor in cur.fetchall():
        d = json.loads(adat) if isinstance(adat, (str, bytes)) else adat
        regi.append((fajta, kulcs, json.dumps(d, ensure_ascii=False, sort_keys=True),
                     allapot, ki, mikor))
    allapotok = jelzes_uj_allapotok(r.sorok, regi)
    cur.execute("DELETE FROM jelzesmenet WHERE jelzesrendszer_id=%s", (rid,))

    def cel_id(kod: str) -> int:
        cur.execute("SELECT id FROM jelzesrendszer WHERE kod=%s", (kod,))
        x = cur.fetchone()
        if not x:
            raise SystemExit(f"HIBA: {r.kod}: ismeretlen jelzésrendszer: {kod}")
        return x[0]

    seq = 0
    for kod in r.hivatkozasok:
        seq += 1
        cur.execute(
            "INSERT INTO jelzesmenet (jelzesrendszer_id, fejezet, seq, tipus, fajta, kulcs, adat,"
            " szoveg, allapot, hivatkozott_id, hivatkozas_mod)"
            " VALUES (%s,'Hivatkozások',%s,'HIVATKOZAS','SZABALY',%s,'{}',%s,'ELFOGADOTT',%s,'BE')",
            (rid, seq, f"HIV/{kod}", f"Hivatkozik: {kod} (minden sorát behozza)", cel_id(kod)))
    for k in r.kizarasok:
        seq += 1
        cur.execute(
            "INSERT INTO jelzesmenet (jelzesrendszer_id, fejezet, seq, tipus, fajta, kulcs, adat,"
            " szoveg, allapot, hivatkozott_id, hivatkozas_mod, kizart_fejezet)"
            " VALUES (%s,'Kizárások',%s,'HIVATKOZAS','SZABALY',%s,'{}',%s,'ELFOGADOTT',%s,'KI',%s)",
            (rid, seq, f"KI/{k.kod}" + (f"/{k.fejezet}" if k.fejezet else ""),
             f"Kizárja: {k.kod}" + (f" / „{k.fejezet}”" if k.fejezet else ""),
             cel_id(k.kod), k.fejezet))
    stat: Counter = Counter()
    for s, (allapot, ki, mikor) in zip(r.sorok, allapotok):
        cur.execute(
            "INSERT INTO jelzesmenet (jelzesrendszer_id, fejezet, seq, tipus, fajta, terulet,"
            " kulcs, adat, szoveg, allapot, jovahagyta, jovahagyva, megjegyzes, jegyzet)"
            " VALUES (%s,%s,%s,'SZABALY',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (rid, s.fejezet, s.seq, s.fajta, s.terulet, s.kulcs[:200], s.tartalom(),
             sor_szoveg(s)[:600], allapot, ki, mikor, (s.megjegyzes or "")[:500] or None,
             s.jegyzet))
        stat[allapot] += 1
    return stat


def _rendszer_upsert(cur, r: RendszerForras) -> int:
    cur.execute(
        "INSERT INTO rendszer (kod, nev, nev_en, fajta, csalad, leiras,"
        " leiras_en, verzio) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
        " ON DUPLICATE KEY UPDATE nev=VALUES(nev), nev_en=VALUES(nev_en),"
        " fajta=VALUES(fajta), csalad=VALUES(csalad), leiras=VALUES(leiras),"
        " leiras_en=VALUES(leiras_en), verzio=VALUES(verzio)",
        (r.kod, r.nev[:255], r.nev_en, r.fajta, r.csalad,
         (r.leiras or "")[:1000] or None, r.leiras_en, r.verzio[:20]))
    cur.execute("SELECT id FROM rendszer WHERE kod=%s", (r.kod,))
    rid = cur.fetchone()[0]
    cur.execute("UPDATE rendszer SET tema=%s, alapja=%s, viszony=%s,"
                " jegyzet=%s, fejezet_jegyzetek=%s WHERE id=%s",
                (r.tema, r.alapja, r.viszony, r.jegyzet,
                 json.dumps(r.fejezet_jegyzetek, ensure_ascii=False)
                 if r.fejezet_jegyzetek else None, rid))
    cur.execute("UPDATE rendszer SET sablon=%s WHERE id=%s",
                (json.dumps(r.sablon, ensure_ascii=False) if r.sablon else None, rid))
    if r.jelzesek_ir:
        cur.execute("UPDATE rendszer SET jelzesek=%s WHERE id=%s",
                    (json.dumps(r.jelzesek, ensure_ascii=False) if r.jelzesek else None,
                     rid))
    if r.kartya:
        try:
            cur.execute("UPDATE rendszer SET kartya=%s WHERE id=%s",
                        (json.dumps(r.kartya, ensure_ascii=False), rid))
        except Exception as e:     # noqa: BLE001 — a 018 még nem futott le
            raise SystemExit(f"{r.kod}: a kártya-adatokhoz futtasd a "
                             f"schema/018_kartya.sql-t ({e})") from e
    return rid


def _vedelem(cur, rid: int, kod: str, kenyszer: bool) -> None:
    cur.execute(
        "SELECT COUNT(*), SUM(dok_fejezet LIKE %s) FROM licitmenet"
        " WHERE rendszer_id=%s AND tipus='SZABALY'", (YAML_JEL + "%", rid))
    osszes, yamlbol = cur.fetchone()
    osszes, yamlbol = int(osszes or 0), int(yamlbol or 0)
    if osszes and yamlbol < osszes and not kenyszer:
        raise SystemExit(
            f"A(z) {kod} rendszernek {osszes - yamlbol} NEM YAML-ból jött "
            f"sora van (pl. LICREN-import). Az import ezeket törölné. "
            f"Ha tényleg ezt akarod: --kenyszer")


def rendszer_ir(cur, r: RendszerForras, kenyszer: bool = False) -> Counter:
    rid = _rendszer_upsert(cur, r)
    _vedelem(cur, rid, r.kod, kenyszer)

    cur.execute(
        "SELECT minta, kulcs, feltetel, jelentes, ha_feltetel, allapot,"
        " jovahagyta, jovahagyva FROM licitmenet"
        " WHERE rendszer_id=%s AND tipus='SZABALY'", (rid,))
    allapotok = uj_allapotok(r.sorok, list(cur.fetchall()))

    # paraméterek
    cur.execute("DELETE FROM rendszer_parameter WHERE rendszer_id=%s", (rid,))
    for kod, ertek in r.parameterek.items():
        cur.execute("SELECT id FROM parameter WHERE kod=%s", (kod,))
        p = cur.fetchone()
        if not p:
            raise SystemExit(f"{r.kod}: ismeretlen paraméter: {kod} "
                             f"(futott a legújabb schema/0xx migráció? pl. 025_szabad_licit.sql)")
        cur.execute("INSERT INTO rendszer_parameter (rendszer_id,"
                    " parameter_id, ertek, megjegyzes) VALUES (%s,%s,%s,%s)",
                    (rid, p[0], ertek[:30], "yaml"))

    # a sorok teljes cseréje
    cur.execute("DELETE FROM licitmenet WHERE rendszer_id=%s", (rid,))
    if r.alapja:                      # a módosított konvenció behivatkozza az alapját
        cur.execute("SELECT id FROM rendszer WHERE kod=%s", (r.alapja,))
        aid = cur.fetchone()
        if not aid:
            raise SystemExit(f"{r.kod}: az alap konvenció nincs meg: {r.alapja}")
        cur.execute(
            "INSERT INTO licitmenet (rendszer_id, fejezet, seq, tipus,"
            " hivatkozott_id, hivatkozas_aktiv, allapot, nyers_szoveg,"
            " dok_fejezet) VALUES (%s,'Alapja',0,'HIVATKOZAS',%s,1,"
            " 'ELFOGADOTT',%s,%s)",
            (rid, aid[0], f"{r.alapja} ({(r.viszony or '').lower()})",
             (YAML_JEL + r.fajlok[0])[:120]))
    for h in r.hivatkozasok:
        cur.execute("SELECT id FROM rendszer WHERE kod=%s", (h.kod,))
        hid = cur.fetchone()
        if not hid:
            raise SystemExit(f"{r.kod}: a hivatkozott rendszer nincs meg: "
                             f"{h.kod} (előbb azt kell importálni)")
        b = h.beallitas
        cur.execute(
            "INSERT INTO licitmenet (rendszer_id, fejezet, seq, tipus,"
            " hivatkozott_id, hivatkozas_aktiv, hivatkozas_beallitas, allapot,"
            " nyers_szoveg, dok_fejezet) VALUES (%s,'Hivatkozások',%s,'HIVATKOZAS',"
            "%s,%s,%s,'ELFOGADOTT',%s,%s)",
            (rid, h.seq, hid[0], 1 if h.aktiv else 0,
             json.dumps(b, ensure_ascii=False) if b else None,
             f"{h.kod} beemelése" + (f" ({' / '.join(h.ervenyes)} után)" if h.ervenyes else ""),
             (YAML_JEL + r.fajlok[0])[:120]))
    for i, k in enumerate(r.kizarasok, start=1):
        cur.execute("SELECT id FROM rendszer WHERE kod=%s", (k.kod,))
        kid = cur.fetchone()
        if not kid:
            raise SystemExit(f"{r.kod}: a kizárt rendszer nincs meg: {k.kod}")
        cur.execute(
            "INSERT INTO licitmenet (rendszer_id, fejezet, seq, tipus,"
            " hivatkozott_id, hivatkozas_aktiv, hivatkozas_mod, kizart_fejezet,"
            " allapot, nyers_szoveg, dok_fejezet)"
            " VALUES (%s,'Kizárások',%s,'HIVATKOZAS',%s,1,'KI',%s,"
            " 'ELFOGADOTT',%s,%s)",
            (rid, 900 + i, kid[0], (k.fejezet or "")[:120] or None,
             f"{k.kod}" + (f" / {k.fejezet}" if k.fejezet else "") + " kizárása",
             (YAML_JEL + r.fajlok[0])[:120]))

    stat: Counter = Counter()
    for s, (allapot, ki, mikor) in zip(r.sorok, allapotok):
        cur.execute(
            "INSERT INTO licitmenet (rendszer_id, fejezet, alfejezet, seq,"
            " tipus, minta, kulcs, specifikussag, prioritas, jelentes,"
            " magyarazat, alert, forsz, dok_fejezet, nyers_szoveg, allapot,"
            " jovahagyta, jovahagyva, feltetel, feltetel_szoveg,"
            " ismeretlen_jelzok, dontesi_mod, ha_feltetel, ha_feltetel_szoveg, elvaras,"
            " magyarazat_en, szabaly_fajta, ag, jegyzet)"
            " VALUES (%s,%s,%s,%s,'SZABALY',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
            "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (rid, (s.fejezet or "")[:120] or None,
             (s.alfejezet or "")[:120] or None, s.seq, s.minta[:120],
             s.kulcs[:120], s.specifikussag, s.prioritas,
             json.dumps(s.jelentes, ensure_ascii=False), s.magyarazat,
             1 if s.alert else 0, s.forsz,
             (YAML_JEL + s.forras_hely.split(":")[0])[:120], s.nyers_szoveg,
             allapot, ki, mikor,
             json.dumps(s.feltetel, ensure_ascii=False), s.feltetel_szoveg,
             s.ismeretlen, s.dontesi_mod,
             json.dumps(s.ha_feltetel, ensure_ascii=False)
             if s.ha_feltetel else None, s.ha_feltetel_szoveg,
             s.elvaras, s.magyarazat_en, s.szabaly_fajta, s.ag, s.jegyzet))
        stat[allapot] += 1
    return stat


def allapot_allit(cur, kod: str, uj: str, honnan: tuple[str, ...],
                  ki: str | None = None, fejezet: str | None = None,
                  minta: str | None = None) -> int:
    """Egy rendszer (egy fejezetének / egy mintájának) sorai: honnan -> uj."""
    cur.execute("SELECT id FROM rendszer WHERE kod=%s", (kod,))
    r = cur.fetchone()
    if not r:
        raise SystemExit(f"Nincs ilyen rendszer: {kod}")
    helyek = ",".join(["%s"] * len(honnan))
    if uj == "ELFOGADOTT":
        sql = ("UPDATE licitmenet SET allapot=%s, jovahagyta=%s,"
               " jovahagyva=NOW()")
        arg: list = [uj, (ki or "")[:60]]
    else:
        sql = "UPDATE licitmenet SET allapot=%s"
        arg = [uj]
    sql += (f" WHERE rendszer_id=%s AND tipus='SZABALY'"
            f" AND allapot IN ({helyek})")
    arg += [r[0], *honnan]
    if fejezet:
        sql += " AND fejezet=%s"
        arg.append(fejezet)
    if minta:
        sql += " AND minta=%s"
        arg.append(minta)
    cur.execute(sql, arg)
    return cur.rowcount


def jovahagy(cur, kod: str, ki: str, fejezet: str | None,
             minta: str | None = None) -> int:
    return allapot_allit(cur, kod, "ELFOGADOTT",
                         ("JAVASOLT", "FELULVIZSGALANDO"), ki, fejezet, minta)


# --- Belépő ------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Rendszerek importja YAML-ból")
    ap.add_argument("utak", nargs="*", help="YAML-fájlok vagy könyvtárak")
    ap.add_argument("--csak", action="append",
                    help="Csak ezek a rendszerek (többször is megadható)")
    ap.add_argument("--probafutas", action="store_true",
                    help="Mindent lefuttat, de a végén visszagörget")
    ap.add_argument("--kenyszer", action="store_true",
                    help="Nem YAML-ból jött sorokat is felülír")
    ap.add_argument("--jovahagy", metavar="KOD",
                    help="A rendszer JAVASOLT/FELULVIZSGALANDO sorai -> ELFOGADOTT")
    ap.add_argument("--jegel", metavar="KOD",
                    help="A rendszer (--fejezet / --minta szerinti) sorai -> JEGELT: "
                         "a motor teszt módban sem használja őket")
    ap.add_argument("--kiolvaszt", metavar="KOD",
                    help="A JEGELT sorok -> JAVASOLT")
    ap.add_argument("--fejezet", help="--jovahagy/--jegel/--kiolvaszt mellett: csak ez a fejezet")
    ap.add_argument("--minta", help="--jovahagy/--jegel/--kiolvaszt mellett: csak ez a minta")
    ap.add_argument("--ki", default=os.getenv("USER", "kibic"),
                    help="--jovahagy mellett: a jóváhagyó neve")
    ap.add_argument("--jelzesek", default=None,
                    help="A jelzésrendszerek könyvtára (alap: rendszerek/jelzesek, "
                         "ha van; '' = kihagyja)")
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host", default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user", default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    muvelet = None
    if a.jovahagy:
        muvelet = (a.jovahagy, "ELFOGADOTT", ("JAVASOLT", "FELULVIZSGALANDO"))
    elif a.jegel:
        if not (a.fejezet or a.minta):
            ap.error("--jegel mellé --fejezet vagy --minta kell "
                     "(egy egész rendszert ne jegelj véletlenül)")
        muvelet = (a.jegel, "JEGELT", ("JAVASOLT", "FELULVIZSGALANDO", "ELFOGADOTT"))
    elif a.kiolvaszt:
        muvelet = (a.kiolvaszt, "JAVASOLT", ("JEGELT",))
    if muvelet:
        kod, uj, honnan = muvelet
        conn = _kapcsolat(a)
        try:
            n = allapot_allit(conn.cursor(), kod, uj, honnan, a.ki,
                              a.fejezet, a.minta)
            conn.commit()
        finally:
            conn.close()
        print(f"{kod}: {n} sor -> {uj}.")
        print("Ne felejtsd: POST /v1/kibic/ujratolt")
        return 0

    if not a.utak:
        ap.error("adj meg YAML-fájlt vagy könyvtárat (vagy --jovahagy KOD)")
    try:
        forrasok = betolt(a.utak)
        sorrend = import_sorrend(forrasok)
    except ForrasHiba as e:
        print(f"HIBA: {e}", file=sys.stderr)
        return 1
    if a.csak:
        sorrend = [k for k in sorrend if k in set(a.csak)]

    # kártyajelzések: a jelzésrendszerek és a profilok ellenőrzése MÉG az
    # adatbázis előtt (feloldás: hiányzó hivatkozás, körkörösség)
    from ..motor.jelzes import JelzesHiba, feloldas, profil_kod, rendszerek_betolt
    from ..motor.kartya import JELZES_KONYVTAR
    jutak = [a.jelzesek] if a.jelzesek else (
        [JELZES_KONYVTAR] if a.jelzesek is None and JELZES_KONYVTAR.is_dir() else [])
    if not jutak and a.jelzesek is None:
        # régen itt csendben kimaradt — és a szerkesztő Jelzések lapja üres maradt
        print(f"FIGYELEM: a jelzésrendszerek könyvtára nem található ({JELZES_KONYVTAR}); "
              "a jelzésrendszerek most NEM íródnak az adatbázisba. "
              "Add meg: --jelzesek rendszerek/jelzesek", file=sys.stderr)
    try:
        jrendszerek = rendszerek_betolt(jutak) if jutak else {}
        for jk in jrendszerek:
            f = feloldas(jk, jrendszerek, "TESZT")
            if f.hianyzo:
                raise JelzesHiba(f"{jk}: ismeretlen jelzésrendszer: {', '.join(f.hianyzo)}")
    except JelzesHiba as e:
        print(f"HIBA: {e}", file=sys.stderr)
        return 1
    if jutak:
        for kod in sorrend:
            jk = profil_kod((forrasok[kod].jelzesek or {}).get("rendszer"))
            if jk and jk not in jrendszerek:
                print(f"HIBA: {kod}: ismeretlen jelzésrendszer: {jk}", file=sys.stderr)
                return 1
            forrasok[kod].jelzesek_ir = True

    conn = _kapcsolat(a)
    try:
        cur = conn.cursor()
        _migracio_019(cur)
        if jutak:
            _migracio_030(cur)
            for jr in jrendszerek.values():   # előbb a fejek: a hivatkozások id-re mutatnak
                jelzesrendszer_fej(cur, jr)
            for jr in jrendszerek.values():
                stat = jelzesrendszer_ir(cur, jr)
                print(f"  {jr.kod:<22} JELZES/{jr.fajta:<13} {len(jr.sorok):>4} sor  "
                      + ", ".join(f"{k}: {v}" for k, v in sorted(stat.items())))
        for kod in sorrend:
            try:
                stat = rendszer_ir(cur, forrasok[kod], a.kenyszer)
            except Exception as e:                     # noqa: BLE001
                # melyik rendszernél akadt el (a tranzakció visszagörgetődik)
                print(f"HIBA a(z) {kod} importjánál: {e}", file=sys.stderr)
                if "szabaly_fajta" in str(e):
                    print("  (a licitmenet.szabaly_fajta ENUM-ból hiányzik egy érték — "
                          "lefutott a schema/031_jelzesmenet_szerkezet.sql?)", file=sys.stderr)
                raise
            r = forrasok[kod]
            kiz = f", {len(r.kizarasok)} kizárás" if r.kizarasok else ""
            print(f"  {kod:<22} {r.fajta:<13} {len(r.sorok):>4} sor, "
                  f"{len(r.hivatkozasok)} hivatkozás{kiz}  "
                  + ", ".join(f"{k}: {v}" for k, v in sorted(stat.items())))
        # A rendszerek (amit egy pár játszik) feloldása: mit zárt ki, mit
        # cserélt téma szerint — ezt látnia kell annak, aki importál.
        from ..motor.feloldas import feloldas
        for kod in sorrend:
            if forrasok[kod].fajta not in ("RENDSZER", "GYUJTEMENY"):
                continue
            f = feloldas(conn, kod, teszt=True)
            for x in f.tajekoztatasok:
                print(f"  {kod}: {x}")
            for x in f.figyelmeztetesek:
                print(f"  {kod}: FIGYELEM: {x}")
        if a.probafutas:
            conn.rollback()
            print("PRÓBAFUTÁS: semmi nem íródott be.")
        else:
            conn.commit()
            print("Kész. A futó szolgáltatásnak: POST /v1/kibic/ujratolt")
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
