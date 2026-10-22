"""Licitmotor: döntés, jelölthalmaz, döntési módok."""
import pytest

from kibic.domain import Kez, kovetkezo_ules
from kibic.motor.feloldas import Sor
from kibic.motor.kifejezes import Kontextus
from kibic.motor.licital import Licitmotor


def sor(minta, feltetel, prioritas=10, spec=0, szoveg=""):
    return Sor(licitmenet_id=prioritas, rendszer_id=1, rendszer_kod="T",
               melyseg=0, kulcs=minta, minta=minta, alfejezet=None,
               prioritas=prioritas, specifikussag=spec, feltetel=feltetel,
               feltetel_szoveg=szoveg, magyarazat=None, forsz="NEM",
               ismeretlen_jelzok=None)


def hcp_legalabb(n):
    return {"t": "OSSZE", "op": ">=",
            "bal": {"t": "ERT", "kod": "HCP"}, "jobb": {"t": "SZAM", "v": n}}


def szin_legalabb(szin, n):
    return {"t": "OSSZE", "op": ">=",
            "bal": {"t": "SZIN", "szin": szin}, "jobb": {"t": "SZAM", "v": n}}


def es(*agak):
    return {"t": "ES", "gy": list(agak)}


def menet(*tokenek, kezdo="N"):
    ki, u = [], kezdo
    for t in tokenek:
        ki.append({"ules": u, "licit": t})
        u = kovetkezo_ules(u)
    return ki


ERŐS_PIKK = "AKQ32.K54.Q76.J3"      # 5 pikk, 16 HCP
GYENGE = "8532.964.J73.842"         # 4 pikk, 2 HCP


# --- Alapműködés ------------------------------------------------------

def test_nyitas_egyetlen_szaballyal():
    m = Licitmotor([sor("1S", es(szin_legalabb("S", 5), hcp_legalabb(12)))])
    d = m.licital([], "N", Kez.pbn_bol(ERŐS_PIKK))
    assert d.licit == "1S"
    assert not d.bizonytalan


def test_nem_teljesulo_feltetel_eseten_nincs_dontes():
    m = Licitmotor([sor("1S", es(szin_legalabb("S", 5), hcp_legalabb(12)))])
    d = m.licital([], "N", Kez.pbn_bol(GYENGE))
    assert d.licit is None and d.jeloltek == []


def test_valasz_a_partner_nyitasara():
    m = Licitmotor([sor("1C-1S", szin_legalabb("S", 4))])
    d = m.licital(menet("1C", "PASS"), "S", Kez.pbn_bol(ERŐS_PIKK))
    assert d.licit == "1S"


# --- Jelölthalmaz és bizonytalanság ----------------------------------

def test_tobb_jelolt_eseten_bizonytalan():
    m = Licitmotor([
        sor("1S", es(szin_legalabb("S", 5), hcp_legalabb(12)), prioritas=10),
        sor("1NT", hcp_legalabb(15), prioritas=20),
    ])
    d = m.licital([], "N", Kez.pbn_bol(ERŐS_PIKK))
    assert d.bizonytalan
    assert {j.licit for j in d.jeloltek} == {"1S", "1NT"}


def test_sorrend_mod_a_magasabb_prioritast_valasztja():
    m = Licitmotor([
        sor("1S", szin_legalabb("S", 5), prioritas=10),
        sor("1NT", hcp_legalabb(15), prioritas=20),
    ], mod="SORREND")
    assert m.licital([], "N", Kez.pbn_bol(ERŐS_PIKK)).licit == "1NT"


def test_specifikussag_mod_maskepp_donthet():
    m = Licitmotor([
        sor("1S", szin_legalabb("S", 5), prioritas=10, spec=99),  # a sor spec-je nyer
        sor("1NT", hcp_legalabb(15), prioritas=20, spec=1),
    ], mod="SPECIFIKUSSAG")
    assert m.licital([], "N", Kez.pbn_bol(ERŐS_PIKK)).licit == "1S"


def test_merlegelo_mod_nem_dont():
    m = Licitmotor([
        sor("1S", szin_legalabb("S", 5)),
        sor("1NT", hcp_legalabb(15)),
    ], mod="MERLEGELO")
    d = m.licital([], "N", Kez.pbn_bol(ERŐS_PIKK))
    assert d.licit is None
    assert len(d.jeloltek) == 2          # a hívó dönt


# --- Engedélyezett licitek (a játékprotokoll legal_actions listája) --

def test_engedelyezett_lista_szukit():
    m = Licitmotor([
        sor("1S", szin_legalabb("S", 5), prioritas=10),
        sor("1NT", hcp_legalabb(15), prioritas=20),
    ])
    d = m.licital([], "N", Kez.pbn_bol(ERŐS_PIKK), engedelyezett=["1S"])
    assert d.licit == "1S"


# --- Háromértékű logika ----------------------------------------------

def test_eldonthetetlen_szabaly_nem_jelolt():
    """Feloldatlan metrika: nem illeszkedő, de nem is kizárt."""
    m = Licitmotor([sor("1S", {"t": "OSSZE", "op": ">=",
                               "bal": {"t": "ERT", "kod": "@PONT"},
                               "jobb": {"t": "SZAM", "v": 11}})])
    d = m.licital([], "N", Kez.pbn_bol(ERŐS_PIKK))
    assert d.licit is None and d.eldonthetetlen == 1


def test_feloldott_metrikaval_mar_dont():
    m = Licitmotor([sor("1S", {"t": "OSSZE", "op": ">=",
                               "bal": {"t": "ERT", "kod": "@PONT"},
                               "jobb": {"t": "SZAM", "v": 11}})],
                   Kontextus(metrika={"PONT": "P_HOSSZ"}))
    d = m.licital([], "N", Kez.pbn_bol(ERŐS_PIKK))
    assert d.licit == "1S" and d.eldonthetetlen == 0


# --- Változós minták --------------------------------------------------

def test_valtozos_minta_kotese():
    """1M-2M: az emelés csak azonos nemesre illik."""
    m = Licitmotor([sor("1M-2M", szin_legalabb("H", 3))])
    d = m.licital(menet("1H", "PASS"), "S", Kez.pbn_bol("A32.K542.Q76.J32"))
    assert d.licit == "2H"


def test_kotetlen_valtozo_nem_ad_licitet():
    """
    Az `1C-1M` utolsó tokenje KÖTETLEN változó: az előzményben nem
    szerepelt `M`, tehát nem tudjuk, melyik nemest mondjuk.
    """
    m = Licitmotor([sor("1C-1M", szin_legalabb("S", 4))])
    assert m.licital(menet("1C", "PASS"), "S",
                     Kez.pbn_bol(ERŐS_PIKK)).licit is None


def test_kotott_valtozobol_szamitjuk_a_licitet():
    """`1M-2M`: a nemes az ELŐZMÉNYBŐL kötődik, a licit abból számítódik."""
    m = Licitmotor([sor("1M-2M", szin_legalabb("H", 3))])
    kez = Kez.pbn_bol("A32.K542.Q76.J32")
    assert m.licital(menet("1H", "PASS"), "S", kez).licit == "2H"
    assert m.licital(menet("1S", "PASS"), "S", kez).licit == "2S"


def test_negyedik_szin_kiszamitasa():
    m = Licitmotor([sor("1A-1B-1E-2Q", szin_legalabb("D", 3))])
    d = m.licital(menet("1C", "PASS", "1H", "PASS", "1S", "PASS"), "N",
                  Kez.pbn_bol("A32.K542.Q763.J3"))
    assert d.licit == "2D"


# --- Hibás minta ------------------------------------------------------

def test_hibas_minta_nem_all_le():
    m = Licitmotor([sor("ez nem minta", hcp_legalabb(0)),
                    sor("1S", szin_legalabb("S", 5))])
    assert len(m.hibas_mintak) == 1
    assert m.licital([], "N", Kez.pbn_bol(ERŐS_PIKK)).licit == "1S"
