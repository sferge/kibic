"""019: rendszer-fajták, kizárás (konvenció / gyűjtemény / fejezet), téma szerinti csere."""
import pytest

from kibic.impex.rendszer_yaml import (ForrasHiba, fajtak_ellenorzese,
                                       forras_dict, import_sorrend)
from kibic.motor.rendszercheck import feloldas_forrasokbol


def _konv(kod, minta, tema=None, fejezetek=None):
    r = {"kod": kod, "fajta": "KONVENCIO"}
    if tema:
        r["tema"] = tema
    return {"rendszer": r,
            "fejezetek": fejezetek or [{"fejezet": "Fő", "szabalyok": [
                {"minta": minta, "pont": "8+", "magyarazat": kod}]}]}


def _gyujt(forrasok):
    g = {}
    for i, d in enumerate(forrasok):
        forras_dict(d, f"f{i}.yaml", g)
    fajtak_ellenorzese(g, hierarchia=False)   # a hierarchia: test_hierarchia.py
    return g


def _mintak(f):
    return {s.minta for s in f.sorok}


ALAP = {"rendszer": {"kod": "ALAP", "fajta": "ALAPRENDSZER"},
        "fejezetek": [
            {"fejezet": "Az 1NT indulás", "szabalyok": [{"minta": "1NT", "pont": "15-17"}]},
            {"fejezet": "A 2♣ indulás", "szabalyok": [{"minta": "2C", "pont": "22+"}]}]}


def test_regi_fajtanevek_is_jok():
    g = _gyujt([{"rendszer": {"kod": "RA", "fajta": "LICITRENDSZER"}},
                {"rendszer": {"kod": "RB", "fajta": "KONVENCIOKARTYA"},
                 "hivatkozasok": ["RA"]}])
    assert (g["RA"].fajta, g["RB"].fajta) == ("ALAPRENDSZER", "RENDSZER")


@pytest.mark.parametrize("dok, resz", [
    ({"rendszer": {"kod": "RR", "fajta": "RENDSZER"},
      "szabalyok": [{"minta": "1C", "pont": "12+"}]}, "csak hivatkozásokból"),
    ({"rendszer": {"kod": "KK", "fajta": "KONVENCIO"}, "hivatkozasok": ["X"]},
     "nem hivatkozhat"),
    ({"rendszer": {"kod": "AA", "fajta": "ALAPRENDSZER"}, "kizarasok": ["X"]},
     "kizárás csak"),
    ({"rendszer": {"kod": "GG", "fajta": "GYUJTEMENY", "tema": "t"}}, "tema"),
])
def test_fajta_szabalyok(dok, resz):
    with pytest.raises(ForrasHiba, match=resz):
        _gyujt([dok])


def test_konvencio_kizarasa_gyujtemenybol():
    g = _gyujt([ALAP, _konv("STAY", "1NT-2C"), _konv("MULTI", "(1NT) 2C"),
                {"rendszer": {"kod": "CSOMAG", "fajta": "GYUJTEMENY"},
                 "hivatkozasok": ["STAY", "MULTI"]},
                {"rendszer": {"kod": "PAR", "fajta": "RENDSZER"},
                 "hivatkozasok": ["ALAP", {"kod": "CSOMAG", "kiveve": ["MULTI"]}]}])
    f, _ = feloldas_forrasokbol(g, "PAR")
    assert "1NT-2C" in _mintak(f) and "(1NT) 2C" not in _mintak(f)
    assert "MULTI" not in {k for k, _ in f.lanc}
    assert any("MULTI" in x for x in f.kizart) and not f.figyelmeztetesek


def test_fejezet_kizarasa():
    g = _gyujt([ALAP, {"rendszer": {"kod": "PAR", "fajta": "RENDSZER"},
                       "hivatkozasok": ["ALAP"],
                       "kizarasok": [{"kod": "ALAP", "fejezet": "A 2♣ indulás"}]}])
    f, _ = feloldas_forrasokbol(g, "PAR")
    assert _mintak(f) == {"1NT"}
    assert any("2♣" in x for x in f.kizart)


def test_hatastalan_kizaras_figyelmeztet():
    g = _gyujt([ALAP, {"rendszer": {"kod": "PAR", "fajta": "RENDSZER"},
                       "hivatkozasok": ["ALAP"],
                       "kizarasok": [{"kod": "ALAP", "fejezet": "Nincs ilyen"}, "SEHOL"]}])
    f, _ = feloldas_forrasokbol(g, "PAR")
    assert len(f.hatastalan_kizarasok) == 2
    assert all(x.startswith("HATÁSTALAN") for x in f.figyelmeztetesek)


def test_kizaras_csak_a_sajat_fajaban_hat():
    # A CSOMAG kizárja a STAY-t — de a PAR közvetlenül is beemeli: az él.
    g = _gyujt([_konv("STAY", "1NT-2C"),
                {"rendszer": {"kod": "CSOMAG", "fajta": "GYUJTEMENY"},
                 "hivatkozasok": ["STAY"], "kizarasok": ["STAY"]},
                {"rendszer": {"kod": "PAR", "fajta": "RENDSZER"},
                 "hivatkozasok": ["STAY", "CSOMAG"]}])
    f, _ = feloldas_forrasokbol(g, "PAR")
    assert "1NT-2C" in _mintak(f)


def test_tema_szerinti_csere_a_kozvetlen_nyer():
    g = _gyujt([_konv("DONT", "(1NT) 2C", tema="1NT ellen"),
                _konv("MULTI", "(1NT) 2D", tema="1NT ellen"),
                {"rendszer": {"kod": "CSOMAG", "fajta": "GYUJTEMENY"},
                 "hivatkozasok": ["MULTI"]},
                {"rendszer": {"kod": "PAR", "fajta": "RENDSZER"},
                 "hivatkozasok": ["CSOMAG", "DONT"]}])
    f, _ = feloldas_forrasokbol(g, "PAR")
    assert _mintak(f) == {"(1NT) 2C"}               # a DONT közelebb van
    assert f.tema_csere and not f.tema_utkozes


def test_tema_utkozes_azonos_szinten():
    g = _gyujt([_konv("DONT", "(1NT) 2C", tema="1NT ellen"),
                _konv("MULTI", "(1NT) 2D", tema="1NT ellen"),
                {"rendszer": {"kod": "PAR", "fajta": "RENDSZER"},
                 "hivatkozasok": ["MULTI", "DONT"]}])
    f, _ = feloldas_forrasokbol(g, "PAR")
    assert _mintak(f) == {"(1NT) 2D"}               # a kártyán előbb álló
    assert f.tema_utkozes and f.figyelmeztetesek[0].startswith("TÉMA-ÜTKÖZÉS")


def test_import_sorrend_a_kizart_rendszert_is_elore_veszi():
    g = _gyujt([_konv("MULTI", "(1NT) 2C"),
                {"rendszer": {"kod": "PAR", "fajta": "RENDSZER"},
                 "kizarasok": ["MULTI"]}])
    s = import_sorrend(g)
    assert s.index("MULTI") < s.index("PAR")


# --- Ugyanez az adatbázis-úton (sqlite-tal utánozva) ---------------------

class _Conn:
    """sqlite, a pymysql %s-jelölésével."""
    def __init__(self):
        import sqlite3
        self.db = sqlite3.connect(":memory:")

    def cursor(self):
        c = self.db.cursor()

        class K:
            def execute(self, sql, arg=()):
                return c.execute(sql.replace("%s", "?"), arg)

            def fetchall(self):
                return c.fetchall()

            def fetchone(self):
                return c.fetchone()
        return K()


def _db():
    k = _Conn()
    c = k.db
    c.execute("CREATE TABLE rendszer (id INTEGER PRIMARY KEY, kod TEXT, fajta TEXT, tema TEXT)")
    c.execute("""CREATE TABLE licitmenet (id INTEGER PRIMARY KEY, rendszer_id INT,
        tipus TEXT, hivatkozott_id INT, hivatkozas_aktiv INT DEFAULT 1,
        hivatkozas_mod TEXT DEFAULT 'BE', kizart_fejezet TEXT, seq INT,
        allapot TEXT DEFAULT 'ELFOGADOTT', kulcs TEXT, minta TEXT, alfejezet TEXT,
        prioritas INT DEFAULT 50, specifikussag INT DEFAULT 100, feltetel TEXT,
        feltetel_szoveg TEXT, magyarazat TEXT, forsz TEXT, ismeretlen_jelzok TEXT,
        jelentes TEXT, ha_feltetel TEXT, ha_feltetel_szoveg TEXT, elvaras TEXT,
        magyarazat_en TEXT, dontesi_mod TEXT, szabaly_fajta TEXT, ag TEXT,
        alert INT, fejezet TEXT, dok_fejezet TEXT)""")
    for i, (kod, fajta, tema) in enumerate([
            ("PAR", "RENDSZER", None), ("CSOMAG", "GYUJTEMENY", None),
            ("ALAP", "ALAPRENDSZER", None), ("STAY", "KONVENCIO", None),
            ("MULTI", "KONVENCIO", "1NT ellen"), ("DONT", "KONVENCIO", "1NT ellen")],
            start=1):
        c.execute("INSERT INTO rendszer VALUES (?,?,?,?)", (i, kod, fajta, tema))

    def sz(rid, minta, fejezet, seq):
        c.execute("INSERT INTO licitmenet (rendszer_id, tipus, seq, kulcs, minta,"
                  " fejezet) VALUES (?,?,?,?,?,?)", (rid, "SZABALY", seq, minta, minta, fejezet))

    def hv(rid, hid, seq, mod="BE", fej=None):
        c.execute("INSERT INTO licitmenet (rendszer_id, tipus, hivatkozott_id, seq,"
                  " hivatkozas_mod, kizart_fejezet) VALUES (?,?,?,?,?,?)",
                  (rid, "HIVATKOZAS", hid, seq, mod, fej))
    sz(3, "1NT", "Az 1NT indulás", 10)
    sz(3, "2C", "A 2♣ indulás", 20)
    sz(4, "1NT-2C", "Fő", 10)
    sz(5, "(1NT) 2C", "Fő", 10)
    sz(6, "(1NT) 2D", "Fő", 10)
    hv(2, 4, 1)                                  # CSOMAG: STAY, MULTI
    hv(2, 5, 2)
    hv(1, 3, 1)                                  # PAR: ALAP, CSOMAG, DONT
    hv(1, 2, 2)
    hv(1, 6, 3)
    hv(1, 3, 901, "KI", "A 2♣ indulás")          # ... a 2♣ fejezet nélkül
    return k


def test_adatbazis_ut_kizaras_es_tema():
    from kibic.motor.feloldas import feloldas
    f = feloldas(_db(), "PAR")
    assert _mintak(f) == {"1NT", "1NT-2C", "(1NT) 2D"}
    assert f.tema_csere == ["„1NT ellen”: DONT marad, MULTI kimarad"]
    assert any("2♣" in x for x in f.kizart)
