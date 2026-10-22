"""ELV-SABLON az ADATBÁZIS útján (2026-10-05): YAML -> rendszerimport -> feloldás.

Az éles szolgáltatás az adatbázisból old fel (motor/feloldas.feloldas), ezért
a példányosításnak (hivatkozas_beallitas, rendszer.sablon) ott is működnie kell.
MySQL nincs a tesztkörnyezetben: egy kis memóriabeli utánzat válaszol pontosan
azokra az SQL-utasításokra, amelyeket az import és a feloldás kiad.
"""
import json
import re
from pathlib import Path

import pytest

YAML = Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"


def _ertekek(szoveg: str, args: list):
    """A VALUES (...) elemei: %s -> a következő argumentum, különben literál."""
    ki, i = [], 0
    for tok in re.findall(r"%s|'(?:[^']|'')*'|[^,\s]+", szoveg):
        if tok == "%s":
            ki.append(args[i])
            i += 1
        elif tok.startswith("'"):
            ki.append(tok[1:-1])
        else:
            ki.append(int(tok) if tok.isdigit() else tok)
    return ki


class FakeDB:
    def __init__(self):
        self.rendszer: list[dict] = []
        self.licitmenet: list[dict] = []

    def cursor(self):
        return FakeCur(self)


class FakeCur:
    def __init__(self, db):
        self.db, self.eredmeny = db, []

    def fetchone(self):
        return self.eredmeny[0] if self.eredmeny else None

    def fetchall(self):
        return list(self.eredmeny)

    def _r(self, **felt):
        return [r for r in self.db.rendszer if all(r.get(k) == v for k, v in felt.items())]

    def execute(self, sql, args=()):
        sql = " ".join(sql.split())
        a = list(args or ())
        db = self.db
        self.eredmeny = []
        if sql.startswith("INSERT INTO rendszer ("):
            kod = a[0]
            r = (self._r(kod=kod) or [None])[0]
            if r is None:
                r = {"id": len(db.rendszer) + 1}
                db.rendszer.append(r)
            r.update(dict(zip(["kod", "nev", "nev_en", "fajta", "csalad", "leiras",
                               "leiras_en", "verzio"], a)))
        elif sql == "SELECT id FROM rendszer WHERE kod=%s":
            self.eredmeny = [(r["id"],) for r in self._r(kod=a[0])]
        elif sql == "SELECT kod FROM rendszer WHERE id=%s":
            self.eredmeny = [(r["kod"],) for r in self._r(id=a[0])]
        elif sql.startswith("UPDATE rendszer SET"):
            mezok = re.findall(r"(\w+)=%s", sql.split(" WHERE ")[0])
            r = self._r(id=a[-1])[0]
            r.update(dict(zip(mezok, a[:-1])))
        elif sql.startswith("SELECT COUNT(*), SUM(dok_fejezet LIKE"):
            self.eredmeny = [(0, 0)]
        elif sql.startswith("SELECT minta, kulcs, feltetel, jelentes"):
            self.eredmeny = []
        elif sql.startswith("DELETE FROM rendszer_parameter"):
            pass
        elif sql == "SELECT id FROM parameter WHERE kod=%s":
            self.eredmeny = [(1,)]
        elif sql.startswith("INSERT INTO rendszer_parameter"):
            pass
        elif sql.startswith("DELETE FROM licitmenet WHERE rendszer_id=%s"):
            db.licitmenet = [x for x in db.licitmenet if x["rendszer_id"] != a[0]]
        elif sql.startswith("INSERT INTO licitmenet ("):
            m = re.match(r"INSERT INTO licitmenet \((.*?)\) VALUES \((.*)\)$", sql)
            oszlopok = [x.strip() for x in m.group(1).split(",")]
            sor = dict(zip(oszlopok, _ertekek(m.group(2), a)))
            sor.setdefault("hivatkozas_mod", "BE")
            sor["seq"] = int(sor.get("seq") or 0)
            db.licitmenet.append(sor)
        elif "FROM licitmenet WHERE rendszer_id=%s AND tipus='SZABALY' AND allapot IN" in sql:
            oszlopok = [x.strip() for x in sql[len("SELECT "):sql.index(" FROM")].split(",")]
            sorok = sorted((x for x in db.licitmenet if x["rendszer_id"] == a[0]
                            and x.get("tipus", "SZABALY") == "SZABALY"
                            and x.get("allapot") in a[1:]), key=lambda x: x["seq"])
            self.eredmeny = [tuple(x.get("dok_fejezet") if o == "dok_fejezet"
                                   else x.get(o) for o in oszlopok) for x in sorok]
        elif sql.startswith("SELECT hivatkozott_id, hivatkozas_beallitas FROM licitmenet"):
            self.eredmeny = [(x["hivatkozott_id"], x.get("hivatkozas_beallitas"))
                             for x in db.licitmenet if x["rendszer_id"] == a[0]
                             and x.get("tipus") == "HIVATKOZAS" and x.get("hivatkozas_aktiv") == 1
                             and x.get("hivatkozas_beallitas")]
        elif sql.startswith("SELECT hivatkozott_id FROM licitmenet"):
            self.eredmeny = [(x["hivatkozott_id"],) for x in sorted(
                db.licitmenet, key=lambda x: x["seq"])
                if x["rendszer_id"] == a[0] and x.get("tipus") == "HIVATKOZAS"
                and x.get("hivatkozas_aktiv") == 1 and x.get("hivatkozas_mod") == "BE"]
        elif sql.startswith("SELECT r.kod, lm.kizart_fejezet FROM licitmenet lm"):
            self.eredmeny = [(self._r(id=x["hivatkozott_id"])[0]["kod"], x.get("kizart_fejezet"))
                             for x in db.licitmenet if x["rendszer_id"] == a[0]
                             and x.get("tipus") == "HIVATKOZAS" and x.get("hivatkozas_mod") == "KI"]
        elif sql == "SELECT sablon FROM rendszer WHERE kod=%s AND fajta='ELV_SABLON'":
            self.eredmeny = [(r.get("sablon"),) for r in self._r(kod=a[0], fajta="ELV_SABLON")]
        elif sql == "SELECT alapja FROM rendszer WHERE kod=%s":
            self.eredmeny = [(r.get("alapja"),) for r in self._r(kod=a[0])]
        elif sql == "SELECT tema, fajta FROM rendszer WHERE kod=%s":
            self.eredmeny = [(r.get("tema"), r.get("fajta")) for r in self._r(kod=a[0])]
        else:
            raise AssertionError(f"ismeretlen SQL a tesztben: {sql[:120]}")


@pytest.fixture(scope="module")
def db():
    pytest.importorskip("yaml")
    from kibic.cli.rendszerimport import rendszer_ir
    from kibic.impex.rendszer_yaml import betolt, import_sorrend
    forrasok = betolt([YAML])
    d = FakeDB()
    d.rendszer.append({"id": 1, "kod": "FESU", "fajta": "KONVENCIO"})   # csak SQL-ből jön
    cur = d.cursor()
    for kod in import_sorrend(forrasok):
        rendszer_ir(cur, forrasok[kod])
    return d, forrasok


def test_import_irja_a_sablont_es_a_beallitast(db):
    d, _ = db
    sb = [r for r in d.rendszer if r["kod"] == "FOGASMUTATAS"][0]
    assert sb["fajta"] == "ELV_SABLON" and "FOGÁST" in json.loads(sb["sablon"])["szoveg"]
    elv = [r for r in d.rendszer if r["kod"] == "MOHA_STAND_ELV"][0]
    h = [x for x in d.licitmenet if x["rendszer_id"] == elv["id"]
         and x.get("hivatkozas_beallitas")]
    beall = [json.loads(x["hivatkozas_beallitas"]) for x in h]
    assert {"ervenyes": ["1M-2m-2M"]} in beall          # FOGASMUTATAS
    assert {"ervenyes": ["1M-1NT"]} in beall            # LIMITALT_UJ_SZIN (2026-10-19)


def test_db_feloldas_egyezik_a_yamlossal(db):
    """Az adatbázisból feloldva ugyanazok a sorok és ugyanaz a példány."""
    from kibic.motor.feloldas import feloldas
    from kibic.motor.rendszercheck import feloldas_forrasokbol
    d, forrasok = db
    f_db = feloldas(d, "MOHA_STAND_ELV", teszt=True)
    f_y = feloldas_forrasokbol(forrasok, "MOHA_STAND_ELV")[0]
    kulcsok = lambda f: sorted((s.rendszer_kod, s.kulcs, s.minta) for s in f.sorok)  # noqa: E731
    assert kulcsok(f_db) == kulcsok(f_y)
    sb = [s for s in f_db.sorok if s.rendszer_kod == "FOGASMUTATAS"]
    assert sb and all("ELV_KONTEXTUS" in json.dumps(s.ha_feltetel) for s in sb)
    assert f_db.elv_teruletek == f_y.elv_teruletek
    assert sum(1 for s in f_db.sorok if s.elnyomo) == sum(1 for s in f_y.sorok if s.elnyomo)
