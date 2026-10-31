"""A lejátszás mérése: lapankénti DD-veszteség a naplóból és valódi partikon."""
import importlib.util
import json

import pytest

from kibic.domain import Kontraktus, Lap, Leosztas, kovetkezo_ules
from kibic.motor import lejatszas_meres as lm
from kibic.solver.dds import LapErtekeles

VAN_DDS = importlib.util.find_spec("endplay") is not None

# W: KQJ52.873.K6.974 — 3NT, S a felvevő, N az asztal, W indul
LO = Leosztas.pbn_bol("N:A76.KQ5.AJ43.K82 T8.T962.T98.JT53 943.AJ4.Q752.AQ6 KQJ52.873.K6.974")
K3NT = Kontraktus(3, "NT", "", "S")


def _lejatszas(lo, felvevo, adu, db=52):
    """Mindenki a legkisebb szabályos lapját teszi."""
    kez = {u: set(lo.kezek[u].lapok) for u in "NESW"}
    hivo, ki, utes = kovetkezo_ules(felvevo), [], []
    u = hivo
    for _ in range(db):
        hivott = utes[0][1].szin if utes else None
        szinben = [l for l in kez[u] if l.szin == hivott]
        l = min(szinben or kez[u], key=lambda x: (x.rang, x.szin))
        kez[u].discard(l)
        utes.append((u, l))
        ki.append(str(l))
        if len(utes) == 4:
            u = lm._nyertes(utes, adu)
            utes = []
        else:
            u = kovetkezo_ules(u)
    return ki


LAPOK = _lejatszas(LO, "S", None)
PARTI = lm.Parti("proba#1", LO, K3NT, [{"ules": "S", "licit": "3NT"}, {"ules": "W", "licit": "P"},
                                      {"ules": "N", "licit": "P"}, {"ules": "E", "licit": "P"}],
                 LAPOK, "IMP", {"N": "a", "E": "b", "S": "c", "W": "d"})


def test_ulesek_sorrendben_es_pozicio():
    ulesek = lm.ulesek_sorrendben([Lap.parse(x) for x in LAPOK], "W", None)
    assert ulesek[:4] == ["W", "N", "E", "S"]
    k0 = lm.pozicio_keres(PARTI, 0)
    assert k0["actor"]["acting_for_seat"] == "W" and set(k0["state"]["visible_hands"]) == {"W"}
    k1 = lm.pozicio_keres(PARTI, 1)                     # az asztal lapja: a felvevő teszi
    assert k1["actor"] == {"seat": "S", "acting_for_seat": "N", "is_declarer": True,
                           "controls_dummy": True}
    assert set(k1["state"]["visible_hands"]) == {"S", "N"}
    hivott = LAPOK[0][0]
    assert all(c[0] == hivott for c in k1["legal_actions"]["cards"])
    k2 = lm.pozicio_keres(PARTI, 2)                     # védő: a saját keze + az asztal
    assert k2["actor"]["acting_for_seat"] == "E" and set(k2["state"]["visible_hands"]) == {"E", "N"}
    assert len(k2["history"]["play"]) == 2
    from kibic.motor import lejatszas as lj
    a = lj.allas_keresbol(k2)                           # a lejátszó réteg megérti
    assert a.ules == "E" and a.vedo


def _naplo(ules="W", db=52):
    """A kibic (W) naplósorai: minden W-lapnál egy kérés, a valódi lappal."""
    ulesek = lm.ulesek_sorrendben([Lap.parse(x) for x in LAPOK], "W", None)
    sorok = []
    for i in range(db):
        if ulesek[i] != ules:
            continue
        k = lm.pozicio_keres(PARTI, i)
        k["game"]["board_number"] = 7
        sorok.append({"decision": "play", "request": k, "action": {"card": LAPOK[i]},
                      "meta": {"kibic": {"situation": "SZINADAS", "rule": None}}})
    return sorok


def test_osztas_visszaallitasa_a_naplobol():
    sorok = _naplo()
    o = lm.osztas_kerelmekbol([s["request"] for s in sorok])
    assert o is not None and all(o.kezek[u].lapok == LO.kezek[u].lapok for u in "NESW")
    # ha a napló a parti közepén ér véget: több lehetséges kiegészítés
    reszben = _naplo(db=40)
    assert lm.osztas_kerelmekbol([s["request"] for s in reszben]) is None
    assert len(lm.osztasok_kerelmekbol([s["request"] for s in reszben])) > 1


def _hamis_dd(rossz: str | None = None):
    """Hamis DD: minden lap 8 ütés a felvevőnek (bukik); a `rossz` lap 9 (teljesül)."""
    def fv(lo, jatszott, k):
        from kibic.domain import Lap as L
        n = len(jatszott)
        ulesek = lm.ulesek_sorrendben([L.parse(x) for x in LAPOK], "W", None)
        if n >= 52:
            return []
        u = ulesek[n]
        kez = {l for l in lo.kezek[u].lapok if str(l) not in set(jatszott)}
        hivott = L.parse(jatszott[n - n % 4]).szin if n % 4 else None
        legalis = [l for l in kez if l.szin == hivott] or list(kez)
        fo = u in ("N", "S")
        ki = []
        for l in legalis:
            felv = 9 if str(l) == rossz else 8
            ki.append(LapErtekeles(str(l), felv if fo else 13 - felv, felv, True, 0))
        return ki
    return fv


def test_naplo_meres_hamis_dd():
    sorok = _naplo()
    rossz = sorok[2]["action"]["card"]
    meresek, stat = lm.naplo_meres(sorok, _hamis_dd(rossz))
    assert stat["visszaallitva"] == 1 and len(meresek) == len(sorok)
    m = next(x for x in meresek if x.lap == rossz)
    assert m.veszt == 1 and m.eredmeny_veszt and not m.felvevo_oldal      # 8 -> 9: teljesül
    assert sum(x.veszt for x in meresek) == 1
    o = lm.osszesit(meresek)
    assert o["vedo"]["hibas_lap"] == 1 and o["helyzetenkent"]["SZINADAS"]["eredmeny_veszt"] == 1


def test_parti_meres_kibic_es_ember():
    rossz = LAPOK[0]                                     # az ember indulása "rossz"

    def dontes(keres):                                   # a kibic a legnagyobb szabályos lapot
        lap = max(keres["legal_actions"]["cards"], key=lambda c: (Lap.parse(c).rang, c))
        return lap, {"kibic": {"situation": "PROBA"}}
    m = lm.parti_meres(PARTI, dontes, _hamis_dd(rossz), felvevo_oldal=False, max_dontes=3)
    assert len(m) == 3 and all(not x.felvevo_oldal for x in m)
    assert m[0].emberi_lap == rossz and m[0].emberi_veszt == 1
    assert m[0].veszt == (1 if m[0].lap == rossz else 0)
    o = lm.osszesit(m)
    assert o["osszes"]["ember_hibas_lap"] == 1


@pytest.mark.skipif(not VAN_DDS, reason="nincs DDS")
def test_cli_naplo(tmp_path, capsys):
    from kibic.cli.jatekmeres import main
    ut = tmp_path / "naplo.jsonl"
    ut.write_text("".join(json.dumps(s) + "\n" for s in _naplo()), encoding="utf-8")
    assert main(["--naplo", str(ut), "--reszletes", "--json", str(tmp_path / "m.jsonl")]) == 0
    ki = capsys.readouterr().out
    assert "visszaallitva: 1" in ki and "védő" in ki
    assert (tmp_path / "m.jsonl").read_text(encoding="utf-8").count("\n") == len(_naplo())


def test_pbn_forras(tmp_path):
    """A mérőpad PBN-ből is olvas (a [Play] ülés-rotációban, nem időrendben)."""
    from kibic.cli.jatekmeres import partik_fajlbol
    lapok = [Lap.parse(x) for x in LAPOK]
    ul = lm.ulesek_sorrendben(lapok, "W", None)
    rot = ["W", "N", "E", "S"]
    sorok = []
    for t in range(0, 52, 4):
        d = {u: str(l) for u, l in zip(ul[t:t + 4], lapok[t:t + 4])}
        sorok.append(" ".join(d[u] for u in rot))
    ut = tmp_path / "proba.pbn"
    ut.write_text(f'[Event "p"]\n[Board "1"]\n[West "w"]\n[North "n"]\n[East "e"]\n[South "s"]\n'
                  f'[Dealer "S"]\n[Vulnerable "None"]\n[Deal "{LO.pbn("N")}"]\n'
                  f'[Declarer "S"]\n[Contract "3NT"]\n[Auction "S"]\n3NT Pass Pass Pass\n'
                  f'[Play "W"]\n' + "\n".join(sorok) + "\n*\n", encoding="utf-8")
    p = list(partik_fajlbol([str(ut)], "IMP"))
    assert len(p) == 1 and p[0].lapok == LAPOK and p[0].kontraktus.felvevo == "S"
    assert p[0].licit[0] == {**p[0].licit[0], "ules": "S"} and p[0].jatekosok["W"] == "w"


def test_pbn_ures_felvevo(tmp_path):
    """Üres [Declarer]: a felvevő a licitmenetből (a tanpartik gyakran ilyenek)."""
    from kibic.cli.jatekmeres import partik_fajlbol
    lapok = [Lap.parse(x) for x in LAPOK]
    ul = lm.ulesek_sorrendben(lapok, "W", None)
    sorok = [" ".join({u: str(l) for u, l in zip(ul[t:t + 4], lapok[t:t + 4])}[u]
                      for u in ["W", "N", "E", "S"]) for t in range(0, 52, 4)]
    ut = tmp_path / "ures.pbn"
    ut.write_text(f'[Board "1"]\n[Dealer "N"]\n[Vulnerable "None"]\n[Deal "{LO.pbn("N")}"]\n'
                  f'[Declarer ""]\n[Contract "3NT"]\n[Auction "N"]\nPass Pass 3NT Pass\n'
                  f'Pass Pass\n[Play "W"]\n' + "\n".join(sorok) + "\n*\n", encoding="utf-8")
    p = list(partik_fajlbol([str(ut)], "IMP"))
    assert len(p) == 1 and p[0].kontraktus.felvevo == "S" and str(p[0].kontraktus) == "3NT"


def test_mappa_forras(tmp_path):
    """Mappa is megadható: a benne (és almappáiban) lévő .pbn/.lin fájlok, útvonal szerint."""
    from kibic.cli.jatekmeres import fajlok_kibontasa
    (tmp_path / "b.pbn").write_text("", encoding="utf-8")
    (tmp_path / "a.PBN").write_text("", encoding="utf-8")
    (tmp_path / "x.lin").write_text("", encoding="utf-8")
    (tmp_path / "al").mkdir()
    (tmp_path / "al" / "c.pbn").write_text("", encoding="utf-8")
    ki = fajlok_kibontasa([str(tmp_path)], ".pbn")
    assert [p.split("/")[-1] for p in ki] == ["a.PBN", "c.pbn", "b.pbn"]   # útvonal szerint: a.PBN, al/c.pbn, b.pbn
    assert fajlok_kibontasa([str(tmp_path), "egy.lin"], ".lin") == [str(tmp_path / "x.lin"), "egy.lin"]


def test_mag_mellett_nem_az_ido_dont(monkeypatch):
    """--mag mellett az időkorlát csak biztonsági határ (a futás ismételhető);
    --idokorlat-tal a megadott marad. A mérés feljegyzi, miért állt meg a mintavétel."""
    import kibic.cli.jatekmeres as jm
    kapott = {}

    def init(rendszer, ido_s, minta, kov_ms=15000, mag=None):
        kapott.update(ido=ido_s, kov=kov_ms)
        jm._MUNKAS["fv"] = lambda k: (k["legal_actions"]["cards"][0], {"kibic": {"stopped": "BIZTOS",
                                                                                   "samples": 80}})
    monkeypatch.setattr(jm, "_munkas_init", init)
    monkeypatch.setattr(jm, "partik_fajlbol", lambda utak, pont, *_: iter([PARTI]))
    eredeti_dd = lm._dd_szotar
    monkeypatch.setattr(lm, "_dd_szotar", lambda *a, **k: {})      # nincs DD: nincs mérés
    jm.main(["--pbn", "x.pbn", "--mag", "1", "--max-dontes", "1"])
    assert kapott == {"ido": jm.PONTOS_IDO_S, "kov": jm.PONTOS_KOVETKEZTETES_MS}
    jm.main(["--pbn", "x.pbn", "--mag", "1", "--idokorlat", "--ido", "3", "--max-dontes", "1"])
    assert kapott == {"ido": 3, "kov": 15000}
    monkeypatch.setattr(lm, "_dd_szotar", eredeti_dd)
    m = lm.parti_meres(PARTI, jm._MUNKAS["fv"], _hamis_dd(), max_dontes=1)
    assert m[0].megallt == "BIZTOS" and m[0].minta == 80


def test_imp_ertekeles():
    """IMP-ben a teljesítés sokat, a felülütés alig számít."""
    dd = {"SA": LapErtekeles("SA", 10, 10, True, 0), "S2": LapErtekeles("S2", 9, 9, False, 1),
          "H2": LapErtekeles("H2", 8, 8, False, 2)}
    assert lm.imp_ertekeles(dd, "SA", True, K3NT, "NONE") == 0
    assert lm.imp_ertekeles(dd, "S2", True, K3NT, "NONE") == 1          # 430 vs 400
    assert lm.imp_ertekeles(dd, "H2", True, K3NT, "NONE") == 10         # 430 vs -50
    assert lm.imp_ertekeles(dd, "H2", True, K3NT, "NS") == 12           # beliben: 630 vs -100
    # a védő szemszögéből: a felvevő ütései a rosszak
    assert lm.imp_ertekeles(dd, "SA", False, K3NT, "NONE") == 10
    m = lm.parti_meres(PARTI, lambda k: (k["legal_actions"]["cards"][0], {}), _hamis_dd(), max_dontes=2)
    assert all(x.imp_veszt is not None and x.emberi_imp_veszt is not None for x in m)
    assert "imp_ossz" in lm.osszesit(m)["osszes"]


@pytest.mark.skipif(not VAN_DDS, reason="nincs DDS")
def test_teljes_lejatszas():
    """A felvevőt a döntéshozó játssza végig, a védők DD szerint (2026-10-25)."""
    def legkisebb(keres):
        return min(keres["legal_actions"]["cards"], key=lambda c: (Lap.parse(c).rang, c)), {}
    m = lm.teljes_lejatszas(PARTI, legkisebb)
    assert m is not None and m.cel == 9 and 0 <= m.utesek <= 13
    assert m.utesek <= m.dd_indulas_utan                 # a DD-védők ellen több nem lehet
    assert (m.utesek < m.dd_indulas_utan) == bool(m.hibak)
    # tökéletes felvevővel pontosan a DD jön ki
    from kibic.solver.dds import lap_elemzes

    def tokeletes(keres):
        from kibic.motor import lejatszas as lj
        a = lj.allas_keresbol(keres)
        e = lap_elemzes(PARTI.leosztas, [x["card"] for x in keres["history"]["play"]], K3NT)
        return max(e, key=lambda x: x.utesek).lap, {}
    m2 = lm.teljes_lejatszas(PARTI, tokeletes)
    assert m2.utesek == m2.dd_indulas_utan and not m2.hibak and m2.imp_veszt == 0
