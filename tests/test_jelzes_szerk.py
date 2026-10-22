"""A szerkesztő jelzés-oldala — sqlite-tal utánzott adatbázison, a valódi YAML-okkal."""
import sqlite3

import pytest

from kibic.motor.jelzes import rendszerek_betolt
from kibic.motor.kartya import JELZES_KONYVTAR
from kibic.szolgaltatas import jelzes_szerk as js
from kibic.szolgaltatas import szerkeszto as sz
from kibic.szolgaltatas.szerkeszto import SzerkesztoHiba


class _Conn:
    def __init__(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)

    def cursor(self):
        c = self.db.cursor()

        class K:
            def execute(self, sql, arg=()):
                if " ON DUPLICATE KEY UPDATE" in sql:     # MySQL upsert -> sqlite
                    sql = sql.split(" ON DUPLICATE KEY UPDATE")[0].replace(
                        "INSERT INTO", "INSERT OR IGNORE INTO")
                return c.execute(sql.replace("%s", "?"), list(arg))

            def fetchall(self):
                return c.fetchall()

            def fetchone(self):
                return c.fetchone()

            @property
            def rowcount(self):
                return c.rowcount

            @property
            def lastrowid(self):
                return c.lastrowid
        return K()

    def commit(self):
        self.db.commit()


def adatbazis() -> _Conn:
    """A valódi YAML-ok egy sqlite-adatbázisban (a próbaszerverhez is)."""
    k = _Conn()
    c = k.db
    c.execute("CREATE TABLE rendszer (id INTEGER PRIMARY KEY, kod TEXT, nev TEXT,"
              " fajta TEXT, aktiv INT DEFAULT 1, jelzesek TEXT)")
    # a 030 + 031 szerkezete
    c.execute("""CREATE TABLE jelzesrendszer (id INTEGER PRIMARY KEY, kod TEXT UNIQUE,
        nev TEXT, fajta TEXT, verzio TEXT, forras TEXT, leiras TEXT, jegyzet TEXT,
        fejezet_jegyzetek TEXT, aktiv INT DEFAULT 1)""")
    c.execute("""CREATE TABLE jelzesmenet (id INTEGER PRIMARY KEY, jelzesrendszer_id INT,
        fejezet TEXT, seq INT, tipus TEXT DEFAULT 'SZABALY', fajta TEXT, terulet TEXT,
        hivatkozott_id INT, hivatkozas_mod TEXT, hivatkozas_aktiv INT DEFAULT 1,
        kizart_fejezet TEXT, kulcs TEXT, adat TEXT, szoveg TEXT,
        allapot TEXT DEFAULT 'JAVASOLT', jovahagyta TEXT, jovahagyva TEXT,
        megjegyzes TEXT, jegyzet TEXT)""")
    c.execute("""CREATE TABLE szerkeszto_megjegyzes (id INTEGER PRIMARY KEY,
        rendszer_kod TEXT, fejezet TEXT, kulcs TEXT, minta TEXT,
        licitmenet_id INT, szoveg TEXT, szerzo TEXT,
        allapot TEXT DEFAULT 'NYITOTT', letrehozva TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("INSERT INTO rendszer (kod, nev, fajta, jelzesek) VALUES"
              " ('KIBIC_STAND','Kibic','RENDSZER','{\"rendszer\": \"MOHA_STAND\"}')")
    # a VALÓDI import írja be (cli/rendszerimport.py), mint élesben
    from kibic.cli.rendszerimport import jelzesrendszer_fej, jelzesrendszer_ir
    rr = rendszerek_betolt([JELZES_KONYVTAR])
    cur = k.cursor()
    for r in rr.values():
        jelzesrendszer_fej(cur, r)
    for r in rr.values():
        jelzesrendszer_ir(cur, r)
    c.commit()
    return k


@pytest.fixture()
def conn():
    return adatbazis()


def test_lista_es_ki_jatssza(conn):
    r = {x["code"]: x for x in js.jelzes_rendszerek(conn)}
    assert set(r) >= {"SZEGEDI_MRAZ", "MOHA_STAND"}
    assert r["MOHA_STAND"]["references"] == ["SZEGEDI_MRAZ"]
    assert r["MOHA_STAND"]["played_by"] == ["KIBIC_STAND"]
    assert r["SZEGEDI_MRAZ"]["kind"] == "ALAPRENDSZER"
    assert r["SZEGEDI_MRAZ"]["counts"].get("ELFOGADOTT", 0) > 10
    # a hivatkozás sor (mint a licitmenetben), de nem számít szabálynak
    assert sum(r["MOHA_STAND"]["counts"].values()) == len(
        rendszerek_betolt([JELZES_KONYVTAR])["MOHA_STAND"].sorok)


def test_rendszer_info(conn):
    i = js.jelzes_rendszer(conn, "MOHA_STAND")
    assert i["references"] == [{"target": "SZEGEDI_MRAZ", "kind": "ALAPRENDSZER",
                                "type": "BEEMELES", "chapter": None, "active": True}]
    assert i["kind"] == "RENDSZER" and i["played_by"] == ["KIBIC_STAND"]
    assert js.jelzes_rendszer(conn, "SZEGEDI_MRAZ")["references"] == []
    # a RENDSZER előre jön
    assert [x["code"] for x in js.jelzes_rendszerek(conn)][0] == "MOHA_STAND"


def test_fa(conn):
    f = js.jelzes_fa(conn, "MOHA_STAND")
    assert [x["code"] for x in f["chain"]] == ["MOHA_STAND", "SZEGEDI_MRAZ"]
    assert any(x["key"] == "MODSZER/SMITH" and x["winner"] == "MOHA_STAND"
               for x in f["overridden"])
    assert any(x["key"] == "ELV/PARTNER_SZUKSEGLETE" for x in f["skipped"])
    assert not f["warnings"] and any(x.startswith("kihagyva:") for x in f["info"])
    assert not f["missing"]
    with pytest.raises(SzerkesztoHiba):
        js.jelzes_fa(conn, "NINCS")


def test_fejezetek_sorok(conn):
    fej = js.jelzes_fejezetek(conn, "SZEGEDI_MRAZ")
    nevek = [x["chapter"] for x in fej]
    assert nevek[0] == "Indítás szín ellen" and "Jelzési rács" in nevek
    sorok = js.jelzes_sorok(conn, "MOHA_STAND")
    smith = next(s for s in sorok if s["key"] == "MODSZER/SMITH")
    assert smith["overrides"] == "SZEGEDI_MRAZ" and smith["text"]
    kihagy = next(s for s in sorok if s["kind"] == "KIHAGYAS")
    assert kihagy["skips"] == "SZEGEDI_MRAZ" and kihagy["overrides"] is None
    assert {s["area"] for s in sorok if s["kind"] != "KIHAGYAS"} <= {
        "INDITAS", "HIVAS", "SZINADAS", "JELZES", "MODSZER", "KULONLEGES", "LICIT"}
    sm = js.jelzes_sorok(conn, "SZEGEDI_MRAZ", "Módszerek")
    assert sm and all(s["chapter"] == "Módszerek" and s["overrides"] is None for s in sm)


def test_feloldott(conn):
    f = js.jelzes_feloldott(conn, "MOHA_STAND", "KARTYA")
    kulcsok = {r["key"]: r for r in f["rules"]}
    assert kulcsok["MODSZER/SMITH"]["source"] == "MOHA_STAND"
    assert "ELV/PARTNER_SZUKSEGLETE" not in kulcsok
    assert any(r["source"] == "SZEGEDI_MRAZ" for r in f["rules"])
    with pytest.raises(SzerkesztoHiba):
        js.jelzes_feloldott(conn, "MOHA_STAND", "ROSSZ")


def test_proba(conn):
    p = js.jelzes_proba(conn, "MOHA_STAND", "KQ72")
    ered = {x["contract"]: x for x in p["results"]}
    assert ered["SZIN"]["card"] and ered["SZIN"]["candidates"]
    assert ered["SZIN"]["candidates"][0]["specificity"] >= ered["SZIN"]["candidates"][-1]["specificity"]
    with pytest.raises(SzerkesztoHiba):
        js.jelzes_proba(conn, "MOHA_STAND", "")
    with pytest.raises(SzerkesztoHiba):
        js.jelzes_proba(conn, "MOHA_STAND", "KQ72", helyzet="ROSSZ")


def test_allapot_muveletek(conn):
    sor = next(s for s in js.jelzes_sorok(conn, "SZEGEDI_MRAZ") if s["state"] == "JAVASOLT")
    assert js.jelzes_allapot_muvelet(conn, "SZEGEDI_MRAZ", "jovahagy", [sor["id"]], ki="Teszt") == 1
    uj = next(s for s in js.jelzes_sorok(conn, "SZEGEDI_MRAZ") if s["id"] == sor["id"])
    assert uj["state"] == "ELFOGADOTT" and uj["approved_by"] == "Teszt"
    # a jóváhagyott sor élesben is él
    assert any(r["key"] == sor["key"] for r in
               js.jelzes_feloldott(conn, "SZEGEDI_MRAZ", "ELES")["rules"])
    assert js.jelzes_allapot_muvelet(conn, "SZEGEDI_MRAZ", "visszavon", [sor["id"]]) == 1
    # egész fejezet jegelése, majd kiolvasztás
    n = js.jelzes_allapot_muvelet(conn, "MOHA_STAND", "jegel", fejezet="Elvek")
    assert n > 0
    assert all(s["state"] == "JEGELT" for s in js.jelzes_sorok(conn, "MOHA_STAND", "Elvek"))
    assert js.jelzes_allapot_muvelet(conn, "MOHA_STAND", "kiolvaszt", fejezet="Elvek") == n
    with pytest.raises(SzerkesztoHiba):
        js.jelzes_allapot_muvelet(conn, "MOHA_STAND", "rossz", [1])
    with pytest.raises(SzerkesztoHiba):
        js.jelzes_allapot_muvelet(conn, "MOHA_STAND", "jovahagy")


def test_megjegyzes_szamlalo(conn):
    sz.megjegyzes_ment(conn, {"text": "Szanban nagy lap legyen", "system": "MOHA_STAND",
                              "chapter": "Módszerek", "key": "MODSZER/SMITH"})
    smith = next(s for s in js.jelzes_sorok(conn, "MOHA_STAND") if s["key"] == "MODSZER/SMITH")
    assert smith["comments"] == 1
    assert sz.megjegyzesek(conn, "MOHA_STAND")[0]["key"] == "MODSZER/SMITH"


def test_hianyzo_tabla():
    k = _Conn()
    with pytest.raises(SzerkesztoHiba):
        js.jelzes_rendszerek(k)


def test_api_utvonalak(conn, monkeypatch):
    """Az útvonalak be vannak kötve, és a függvényeik működnek. HTTP-kliens
    nélkül (a TestClient-hez httpx kellene; az nincs minden környezetben)."""
    from fastapi import HTTPException

    from kibic.szolgaltatas import api
    conn.close = lambda: None
    monkeypatch.setattr(api, "_db_kapcsolat", lambda: conn)
    utak = {getattr(r, "path", None) for r in api.app.routes}
    for ut in ("rendszerek", "rendszer", "fa", "fejezetek", "sorok", "feloldott", "proba",
               "allapot"):
        assert f"/v1/kibic/szerk/jelzes/{ut}" in utak, ut
    assert api.szerk_jelzes_rendszerek()[0]["code"] == "MOHA_STAND"
    assert api.szerk_jelzes_fa("MOHA_STAND")["chain"]
    assert api.szerk_jelzes_rendszer("MOHA_STAND")["references"]
    assert api.szerk_jelzes_fejezetek("MOHA_STAND")
    sorok = api.szerk_jelzes_sorok("MOHA_STAND", "Elvek")
    assert sorok and all(s["chapter"] == "Elvek" for s in sorok)
    assert api.szerk_jelzes_feloldott("MOHA_STAND", "ELES")["rules"]
    assert len(api.szerk_jelzes_proba("MOHA_STAND", "KQ72")["results"]) == 2
    with pytest.raises(HTTPException) as e:
        api.szerk_jelzes_proba("MOHA_STAND", "")
    assert e.value.status_code == 400
    v = api.szerk_jelzes_allapot({"system": "MOHA_STAND", "action": "jegel", "chapter": "Elvek"})
    assert v["changed"] == len(sorok)
    assert "Jelzések" in api.szerkeszto_oldal().body.decode("utf-8")
