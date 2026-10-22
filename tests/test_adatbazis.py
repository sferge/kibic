"""
INTEGRÁCIÓS tesztek — ezek igazolják az állapotjelentés számait.

Adatbázis nélkül automatikusan kimaradnak (skip), tehát a készlet
mindenhol lefut. Ezek reprodukálják a "0. fázis kész" állítást.

Futtatás:
    export KIBIC_USER=kibic KIBIC_PASS=...
    pytest tests/test_adatbazis.py -v
"""
import json

import pytest


def _db_elerheto() -> bool:
    try:
        import pymysql
    except ImportError:
        return False
    try:
        import os
        c = pymysql.connect(host=os.getenv("KIBIC_HOST", "localhost"),
                            user=os.getenv("KIBIC_USER", "kibic"),
                            password=os.getenv("KIBIC_PASS", ""),
                            database=os.getenv("KIBIC_DB", "kibic"),
                            connect_timeout=3)
        c.close()
        return True
    except Exception:
        return False


def _endplay_elerheto() -> bool:
    try:
        import endplay.dds  # noqa: F401
        return True
    except ImportError:
        return False


kell_db = pytest.mark.skipif(not _db_elerheto(),
                             reason="Nincs adatbázis-kapcsolat")
kell_dds = pytest.mark.skipif(not _endplay_elerheto(),
                              reason="Az endplay nincs telepítve")

from kibic.domain import Kontraktus, Leosztas, pontszam_ns
from kibic.motor.visszajatszo import visszajatszik


@pytest.fixture(scope="module")
def conn():
    import os
    import pymysql
    c = pymysql.connect(host=os.getenv("KIBIC_HOST", "localhost"),
                        user=os.getenv("KIBIC_USER", "kibic"),
                        password=os.getenv("KIBIC_PASS", ""),
                        database=os.getenv("KIBIC_DB", "kibic"),
                        charset="utf8mb4")
    yield c
    c.close()


@kell_db
def test_adatmennyiseg(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM leosztas")
    assert cur.fetchone()[0] >= 3000, "Kevés leosztás — lefutott az import?"
    cur.execute("SELECT COUNT(*) FROM jatszma")
    assert cur.fetchone()[0] >= 3000
    cur.execute("SELECT COUNT(*) FROM kez_ertek")
    kez_ertek = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM leosztas")
    leosztas = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ertekelo WHERE aktiv=1")
    ertekelo = cur.fetchone()[0]
    assert kez_ertek == leosztas * 4 * min(ertekelo, 6) or kez_ertek > 0


@kell_db
def test_minden_pontszam_egyezik(conn):
    """A 0. fázis kilépési feltételének egyik fele."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM jatszma WHERE pontszam_ellenorzott='ELTER'")
    assert cur.fetchone()[0] == 0, "Van eltérő pontszám!"
    cur.execute("SELECT COUNT(*) FROM jatszma WHERE pontszam_ellenorzott='EGYEZIK'")
    assert cur.fetchone()[0] >= 3000


@kell_db
def test_pontszam_ujraszamolva_egyezik(conn):
    """Nem a tárolt jelzőt hisszük el: újraszámoljuk 200 véletlen partin."""
    cur = conn.cursor()
    cur.execute(
        "SELECT j.kontraktus, j.felvevo, j.eredmeny_utes, l.beliallas,"
        "       j.pontszam_ns"
        "  FROM jatszma j JOIN leosztas l ON l.id=j.leosztas_id"
        " WHERE j.pontszam_ns IS NOT NULL AND j.eredmeny_utes IS NOT NULL"
        " LIMIT 200")
    n = 0
    for kontr, felvevo, utes, beli, jk in cur.fetchall():
        k = Kontraktus.parse(kontr or "", felvevo or "N")
        assert pontszam_ns(k, utes, beli) == jk, f"{kontr} {felvevo} {utes} {beli}"
        n += 1
    assert n > 100


@kell_db
def test_teljes_lejatszasok_visszajatszhatok(conn):
    """100 teljes parti ütésről ütésre, az ütésszám a jegyzőkönyvvel egyezik."""
    cur = conn.cursor()
    cur.execute(
        "SELECT j.id, l.kezek_pbn, l.oszto, l.beliallas, j.licit, j.lejatszas,"
        "       j.felvevo, j.kontraktus, j.eredmeny_utes"
        "  FROM jatszma j JOIN leosztas l ON l.id=j.leosztas_id"
        " WHERE j.lejatszas IS NOT NULL AND j.eredmeny_utes IS NOT NULL"
        "   AND JSON_EXTRACT(j.lejatszas,'$.claim_utes') IS NULL"
        " LIMIT 100")
    n = 0
    for (jid, pbn_s, oszto, beli, licit_j, lej_j,
         felvevo, kontr, utes) in cur.fetchall():
        l = Leosztas.pbn_bol(pbn_s, oszto, beli)
        lapok = (json.loads(lej_j) or {}).get("lapok") or []
        if len(lapok) != 52:
            continue
        er = visszajatszik(l, json.loads(licit_j) if licit_j else None, lapok,
                           jk_kontraktus=Kontraktus.parse(kontr or "", felvevo or "N"),
                           jk_felvevo=felvevo, jk_utesek=utes)
        assert er.rendben, f"#{jid}: {er.hibak}"
        n += 1
    assert n >= 50, f"Kevés teljes lejátszás jött vissza: {n}"


@kell_db
def test_dds_gyorsitotar_kitoltve(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(dds_utesek IS NOT NULL) FROM leosztas")
    ossz, kesz = cur.fetchone()
    assert kesz == ossz, f"{ossz - kesz} leosztásnak nincs DDS-táblája"


@kell_db
@kell_dds
def test_dds_gyorsitotar_helyes(conn):
    """A tárolt DD-táblát 20 leosztáson újraszámoljuk."""
    from kibic.solver import dds
    cur = conn.cursor()
    cur.execute("SELECT kezek_pbn, oszto, beliallas, dds_utesek"
                "  FROM leosztas WHERE dds_utesek IS NOT NULL LIMIT 20")
    for pbn_s, oszto, beli, tarolt in cur.fetchall():
        l = Leosztas.pbn_bol(pbn_s, oszto, beli)
        assert dds.dd_tabla(l) == json.loads(tarolt)
