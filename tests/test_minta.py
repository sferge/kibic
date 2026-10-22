"""Mintaillesztő motor: kanonizálás, változókötés, Q, specifikusság."""
import pytest

from kibic.domain import kovetkezo_ules
from kibic.motor.minta import (MintaHiba, illeszkedik, kanonizal, kibont,
                               legjobb_talalat, minta_parse)


def menet(*tokenek, kezdo="N"):
    """Licitmenet építése: a tokenek a kezdőtől óramutató szerint."""
    ki, u = [], kezdo
    for t in tokenek:
        ki.append({"ules": u, "licit": t})
        u = kovetkezo_ules(u)
    return ki


def kanon(*tokenek, ules="N", kezdo="N"):
    return kanonizal(menet(*tokenek, kezdo=kezdo), ules)


# --- Kanonizálás ------------------------------------------------------

def test_paroslicit_alak_ha_nincs_kozbeszolas():
    sz, _ = kanon("1NT", "PASS", "2C", ules="S")
    assert sz == "1NT-2C"


def test_kompetitiv_alak_ha_van_kozbeszolas():
    sz, _ = kanon("1D", "2C", "2H", ules="N")
    assert sz == "1D (2C) 2H"


def test_nyitas_elotti_passzok_kimaradnak():
    """Harmadik helyen indított licit: a minta az első érdemi licittel kezdődik.
    A passzolt kéz ténye az Allas-ból (teljes menet) olvasható, nem a mintából."""
    sz, _ = kanon("PASS", "PASS", "1H", ules="N")
    assert sz == "1H"


# --- Minta-értelmezés -------------------------------------------------

def test_kevert_jeloles_hibat_dob():
    with pytest.raises(MintaHiba):
        minta_parse("1M-2M (2S) 3M")


def test_szan_roviditese_elfogadott():
    """A LICREN és a magyar leírások `N`-t írnak `NT` helyett."""
    assert str(minta_parse("1N-2C")) == "1NT-2C"


def test_helyettesito_csak_ellenfelnel():
    with pytest.raises(MintaHiba):
        minta_parse("1D * 2H")


# --- Változókötés -----------------------------------------------------

@pytest.mark.parametrize("licitek,illik,kotes", [
    (("1H", "PASS", "2H"), True,  "M=H"),
    (("1S", "PASS", "2S"), True,  "M=S"),
    (("1H", "PASS", "2S"), False, None),
])
def test_ismetelt_valtozo_ugyanazt_a_szint_jelenti(licitek, illik, kotes):
    _, tk = kanon(*licitek, ules="N")
    t = illeszkedik(minta_parse("1M-2M"), tk)
    assert (t is not None) is illik
    if illik:
        assert t.kotes_szoveg() == kotes


def test_minor_valtozo_nem_illik_nemesre():
    _, tk = kanon("1H", "PASS", "2H", ules="N")
    assert illeszkedik(minta_parse("1m-2m"), tk) is None


# --- Negyedik szín ----------------------------------------------------

def test_negyedik_szin_relacios_szamitasa():
    _, tk = kanon("1C", "PASS", "1H", "PASS", "1S", "PASS", "2D", ules="N")
    t = illeszkedik(minta_parse("1A-1B-1E-2Q"), tk)
    assert t is not None
    assert t.kotesek == {"A": "C", "B": "H", "E": "S", "Q": "D"}   # a Q is kötődik (2026-10-02)


def test_nem_negyedik_szin_nem_illik():
    _, tk = kanon("1C", "PASS", "1H", "PASS", "1S", "PASS", "2C", ules="N")
    assert illeszkedik(minta_parse("1A-1B-1E-2Q"), tk) is None


# --- Ütközésfeloldás --------------------------------------------------

def test_a_specifikusabb_minta_nyer():
    _, tk = kanon("1D", "2C", "2H", ules="N")
    mintak = [minta_parse("1D (*) 2H"), minta_parse("1D (2C) 2M"),
              minta_parse("1D (2C) 2H")]
    gyoztes, mind = legjobb_talalat(mintak, tk)
    assert len(mind) == 3
    assert gyoztes.minta.nyers == "1D (2C) 2H"


# --- Helyettesítők ----------------------------------------------------

def test_barmennyi_akcio_kihagyasa():
    _, tk = kanon("1H", "PASS", "2H", "2S", "3H", ules="N")
    assert illeszkedik(minta_parse("1M .. 3M"), tk) is not None


def test_barmely_licit_helyettesito():
    _, tk = kanon("1H", "1S", "2H", ules="N")
    assert illeszkedik(minta_parse("1M (?) 2M"), tk) is not None


# --- Kibontás ---------------------------------------------------------

@pytest.mark.parametrize("minta,db", [
    ("1M-2M", 2), ("1m-1M-2M", 4), ("1A-1B-1E-2Q", 24), ("1NT-2C", 1),
])
def test_kibontas_darabszama(minta, db):
    assert len(kibont(minta_parse(minta))) == db


def test_kibontas_helyes_szekvenciakat_ad():
    ki = dict(kibont(minta_parse("1M-2M")))
    assert set(ki) == {"1H-2H", "1S-2S"}
