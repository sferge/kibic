"""A rendszerszerkesztő adatrétege — sqlite-tal utánzott adatbázison."""
import sqlite3

import pytest

from kibic.szolgaltatas import szerkeszto as sz


class _Conn:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")

    def cursor(self):
        c = self.db.cursor()

        class K:
            def execute(self, sql, arg=()):
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


@pytest.fixture()
def conn():
    k = _Conn()
    c = k.db
    c.execute("CREATE TABLE rendszer (id INTEGER PRIMARY KEY, kod TEXT, nev TEXT,"
              " fajta TEXT, tema TEXT, alapja TEXT, viszony TEXT, aktiv INT DEFAULT 1)")
    c.execute("""CREATE TABLE licitmenet (id INTEGER PRIMARY KEY, rendszer_id INT,
        tipus TEXT, hivatkozott_id INT, hivatkozas_aktiv INT DEFAULT 1,
        hivatkozas_mod TEXT DEFAULT 'BE', kizart_fejezet TEXT, seq INT,
        allapot TEXT DEFAULT 'JAVASOLT', kulcs TEXT, minta TEXT, alfejezet TEXT,
        prioritas INT DEFAULT 50, specifikussag INT DEFAULT 100, feltetel TEXT,
        feltetel_szoveg TEXT, magyarazat TEXT, forsz TEXT DEFAULT 'NEM',
        ismeretlen_jelzok TEXT, jelentes TEXT, ha_feltetel TEXT,
        ha_feltetel_szoveg TEXT, elvaras TEXT, magyarazat_en TEXT,
        dontesi_mod TEXT, szabaly_fajta TEXT DEFAULT 'SZABALY', ag TEXT,
        alert INT DEFAULT 0, fejezet TEXT, dok_fejezet TEXT, nyers_szoveg TEXT,
        jovahagyta TEXT, jovahagyva TEXT)""")
    c.execute("""CREATE TABLE szerkeszto_megjegyzes (id INTEGER PRIMARY KEY,
        rendszer_kod TEXT, fejezet TEXT, kulcs TEXT, minta TEXT,
        licitmenet_id INT, szoveg TEXT, szerzo TEXT,
        allapot TEXT DEFAULT 'NYITOTT', letrehozva TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("INSERT INTO rendszer VALUES (1,'PAR','Pár','RENDSZER',NULL,NULL,NULL,1)")
    c.execute("INSERT INTO rendszer VALUES (2,'ALAP','Alap','ALAPRENDSZER',NULL,NULL,NULL,1)")
    c.execute("INSERT INTO licitmenet (rendszer_id, tipus, hivatkozott_id, seq)"
              " VALUES (1,'HIVATKOZAS',2,1)")
    for seq, (minta, fej) in enumerate([("1NT", "Az 1NT"), ("1NT-2C", "Az 1NT"),
                                        ("2C", "A 2♣")], start=1):
        c.execute("INSERT INTO licitmenet (rendszer_id, tipus, seq, kulcs, minta,"
                  " fejezet, magyarazat) VALUES (2,'SZABALY',?,?,?,?,?)",
                  (seq * 10, minta, minta, fej, minta + " magyarázat"))
    return k


def test_rendszerek_fejezetek_szabalyok(conn):
    r = {x["code"]: x for x in sz.rendszerek(conn)}
    assert r["ALAP"]["counts"] == {"JAVASOLT": 3} and r["PAR"]["kind"] == "RENDSZER"
    f = sz.fejezetek(conn, "ALAP")
    assert [x["chapter"] for x in f] == ["Az 1NT", "A 2♣"] and f[0]["total"] == 2
    s = sz.szabalyok(conn, "ALAP", "Az 1NT")
    assert [x["minta"] for x in s] == ["1NT", "1NT-2C"] and s[0]["comments"] == 0


def test_jovahagyas_fejezetre_es_kijeloltre(conn):
    assert sz.allapot_muvelet(conn, "ALAP", "jovahagy", fejezet="Az 1NT", ki="Sanyi") == 2
    s = sz.szabalyok(conn, "ALAP", "Az 1NT")
    assert {x["allapot"] for x in s} == {"ELFOGADOTT"} and s[0]["jovahagyta"] == "Sanyi"
    ketto = sz.szabalyok(conn, "ALAP", "A 2♣")[0]["id"]
    assert sz.allapot_muvelet(conn, "ALAP", "jegel", ids=[ketto]) == 1
    assert sz.allapot_muvelet(conn, "ALAP", "kiolvaszt", ids=[ketto]) == 1
    with pytest.raises(sz.SzerkesztoHiba):
        sz.allapot_muvelet(conn, "ALAP", "jovahagy")          # egész rendszert nem


def test_megjegyzes_azonnal_ment_es_exportal(conn):
    sz.megjegyzes_ment(conn, {"system": "ALAP", "chapter": "Az 1NT", "key": "1NT-2C",
                              "pattern": "1NT-2C", "text": "Garbage Stayman is?",
                              "author": "Sanyi"})
    assert sz.szabalyok(conn, "ALAP", "Az 1NT")[1]["comments"] == 1
    m = sz.megjegyzesek(conn, "ALAP")
    assert m[0]["text"] == "Garbage Stayman is?"
    e = sz.export(conn)
    assert e["comments"][0]["key"] == "1NT-2C" and e["systems"]
    sz.megjegyzes_lezar(conn, m[0]["id"])
    assert sz.megjegyzesek(conn, "ALAP") == []
    with pytest.raises(sz.SzerkesztoHiba):
        sz.megjegyzes_ment(conn, {"system": "ALAP", "text": "  "})


def test_fa(conn):
    f = sz.fa(conn, "PAR")
    assert [c["code"] for c in f["chain"]] == ["PAR", "ALAP"] and f["rules"] == 3


def test_feloldott_nezet_nyitasok_es_elotag(conn):
    v = sz.feloldott(conn, "PAR", csak_nyitas=True)
    assert [r["minta"] for r in v["rules"]] == ["1NT", "2C"]
    assert v["rules"][0]["source"] == "ALAP" and v["total"] == 3
    assert [r["minta"] for r in sz.feloldott(conn, "PAR", elotag="1nt-")["rules"]] == ["1NT-2C"]


def test_folytatolagos_sorrend():
    mintak = ["1NT", "1H-1NT", "1H (X) 1S", "1H-1S-2C", "1H", "1H-1S",
              "(1C) 1H", "2C", ".. (*) P", "1H (1S) X", "(1C) X",
              "1H (X) XX"]
    assert sorted(mintak, key=sz.menet_kulcs) == [
        "1H", "1H-1S", "1H-1S-2C", "1H-1NT",               # pároslicit
        "1H (X) XX", "1H (X) 1S", "1H (1S) X",             # küzdelmi
        "1NT", "2C", "(1C) X", "(1C) 1H", ".. (*) P"]


def test_fejezet_is_folytatolagos_sorrendben(conn):
    c = conn.db
    for seq, minta in [(40, "2NT"), (50, "1S"), (60, "1C"), (70, "1S-1NT")]:
        c.execute("INSERT INTO licitmenet (rendszer_id, tipus, seq, kulcs, minta,"
                  " fejezet) VALUES (2,'SZABALY',?,?,?,'Nyitások')", (seq, minta, minta))
    assert [s["minta"] for s in sz.szabalyok(conn, "ALAP", "Nyitások")] == [
        "1C", "1S", "1S-1NT", "2NT"]


def test_passzos_kompetitiv_alak_azonos_a_paroslicittel():
    from kibic.motor.minta import minta_norm, minta_parse
    assert minta_norm("1H (P) 1S") == "1H-1S"
    assert minta_norm("1H (P) 1S (P) 2C") == "1H-1S-2C"
    assert minta_parse("1H (P) 1S").paroslicit
    assert minta_norm("1H (P) 1S (2C) X") == "1H (P) 1S (2C) X"   # küzdelmi marad
    assert minta_norm("(1C) P (P) X") == "(1C) P (P) X"           # védekező marad
    assert sz.menet_kulcs("1H (P) 1S") == sz.menet_kulcs("1H-1S")


def test_szinsorrend_minor_es_nemes_valtozoval():
    mintak = ["1NT", "1M", "1S", "1H", "1m-1H", "1m", "1D", "1C-1NT", "1C",
              "1C-1M", "1C-1S", "1C-1H", "1C-1D"]
    assert sorted(mintak, key=sz.menet_kulcs) == [
        "1C", "1C-1D", "1C-1H", "1C-1S", "1C-1M", "1C-1NT",
        "1D", "1m", "1m-1H", "1H", "1S", "1M", "1NT"]


def test_minor_nyitasok_egy_agban_ha_van_1m_szabaly():
    mintak = ["1C-1NT", "1D-1NT", "1m-1H", "1m-1NT", "1C-1S", "1D-1S", "1C",
              "1D", "1m", "1C-1H", "1C-1H-1S", "1D-1H", "2C", "2D", "2C-2D",
              "2D-2NT", "1H"]
    osz = sz.osszevont_nyitasok(mintak)
    assert osz == {("1", "m")}
    assert sorted(mintak, key=lambda m: sz.menet_kulcs(m, osz)) == [
        "1C", "1D", "1m",
        "1C-1H", "1D-1H", "1m-1H", "1C-1H-1S",
        "1C-1S", "1D-1S",
        "1C-1NT", "1D-1NT", "1m-1NT",
        "1H",
        "2C", "2C-2D", "2D", "2D-2NT"]                # 2♣ és 2♦ külön ág marad


@pytest.mark.parametrize("kereses, minta, vart", [
    ("1S-1N", "1M-1NT", True),          # változós szabály is
    ("1s-1nt", "1M-1NT-2C", True),      # kisbetű, és a folytatás is
    ("1S-1N", "1H-1NT", False),
    ("1S-1N", "1S", False),             # rövidebb: nem ez a helyzet
    ("1M", "1H-1S", True),
    ("1M", "1S (X) XX", True),          # egyetlen licitnél a küzdelmi is
    ("1S-1NT", "1S (X) 1NT", False),    # több licitnél a pároslicit csak pároslicit
    ("1m-1H", "1C-1H-1S", True),
    ("1S-2H", "1M-2M", False),          # kötés: az 1♠-2♠ volna
    ("1S-2S", "1M-2M", True),
    ("1H-2S", "1M-2oM", True),
    ("1NT-", "1NT-2C", True),           # a régi előtag-keresés is megy
    ("(1C)", "(1C) X", True),
    ("1M", "1m-1H", False),             # M = nemes, m = minor: nem ugyanaz
    ("1m", "1H-1S", False),
    ("1m", "1D-1H", True),
])
def test_kereses_licit_szerint(kereses, minta, vart):
    assert sz.elotag_illik(kereses, minta) is vart
