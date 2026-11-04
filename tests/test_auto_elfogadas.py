"""Automatikus elfogadás: ütközésmentes JAVASOLT sor -> ELFOGADOTT (2026-11-04)."""
from kibic.cli.rendszerimport import uj_allapotok
from kibic.impex.rendszer_yaml import forras_dict
from kibic.motor.auto_elfogadas import utkozesmentes
from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol


def _rendszer(szabalyok):
    g = {}
    forras_dict({"rendszer": {"kod": "TAE", "fajta": "RENDSZER"},
                 "szabalyok": szabalyok}, "t.yaml", g)
    f, _ = feloldas_forrasokbol(g, "TAE")
    return f


def _id(f, minta):
    return next(s.licitmenet_id for s in f.sorok if s.minta == minta)


ALAP = [
    {"minta": "1S", "pont": "12-21", "hossz": {"S": "5+"}, "prioritas": 80},
    {"minta": "1H", "pont": "12-21", "hossz": {"H": "5+", "S": "0-4"}, "prioritas": 80},
]


def test_utkozes_nelkul_elfogadhato():
    f = _rendszer(ALAP + [
        {"minta": "1NT", "pont": "15-17", "elosztas": "BAL", "prioritas": 85}])
    uj = _id(f, "1NT")
    er = utkozesmentes({"TAE": (f.sorok, Parametertar(), f)}, {uj}, kez_db=60)
    assert er.elfogadhato == {uj} and not er.utkozo


def test_utkozo_sor_javasolt_marad():
    # azonos rangú, átfedő feltétel, más licit: 5-5 nemessel 1S vagy 1H
    f = _rendszer([
        {"minta": "1S", "pont": "12-21", "hossz": {"S": "5+"}, "prioritas": 80},
        {"minta": "1H", "pont": "12-21", "hossz": {"H": "5+"}, "prioritas": 80}])
    uj = _id(f, "1H")
    er = utkozesmentes({"TAE": (f.sorok, Parametertar(), f)}, {uj}, kez_db=400)
    assert uj in er.utkozo and uj not in er.elfogadhato
    assert "1S / 1H" in er.utkozo[uj][0] or "1H / 1S" in er.utkozo[uj][0]


def test_csak_az_uj_sor_jelolt():
    from kibic.impex.rendszer_yaml import forras_dict as fd
    g = {}
    fd({"rendszer": {"kod": "TAJ", "fajta": "KONVENCIO"}, "szabalyok": ALAP}, "t.yaml", g)
    sorok = g["TAJ"].sorok
    regi = [(s.minta, s.kulcs, s.feltetel, s.jelentes, s.ha_feltetel,
             "JAVASOLT", None, None) for s in sorok[:1]]
    ujak: list[int] = []
    ki = uj_allapotok(sorok, regi, ujak)
    assert [x[0] for x in ki] == ["JAVASOLT", "JAVASOLT"]
    assert ujak == [1]       # a változatlan (esetleg visszaállított) sor nem jelölt
