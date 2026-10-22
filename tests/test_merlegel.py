"""
A mérlegelő lánc próbája: kényszertár -> mintavétel -> pontozás.

A DDS-t NEM hívjuk (endplay nélkül is le kell futnia): a DD-táblákat
kézzel adjuk meg, így az összemérés logikája önmagában ellenőrizhető.

Amit igazol:
  1. a mintavétel minden leosztása kielégíti a kényszertárat;
  2. a minta jelzi, ha az irányított (torzított) ágra kellett esni;
  3. a kalibráció a várt irányba mozdítja a becslést;
  4. az IMP- és az MP-mérték tud ELLENTÉTES irányba mutatni — a modul
     ezért nem dönt egyik szerint sem.
"""
import pytest

from kibic.domain import ERTEKELOK, Kez
from kibic.motor.helyzet import Allas, Igeret
from kibic.motor.merlegel import (Kalibracio, Kimenetel, Osszemeres,
                                  buntetes_vagy_sajat)
from kibic.domain import Kontraktus
from kibic.motor.mintavetel import mintavetel

SAJAT = Kez.pbn_bol("K4.AQJ2.KQ74.T93")          # 15 HCP

TAR = {
    "N": Igeret(pont_min=12, pont_max=21, hossz_min={"S": 5},
                nyilatkozott=True),
    "E": Igeret(pont_min=5, pont_max=10, hossz_min={"C": 5, "D": 5},
                nyilatkozott=True),
    "W": Igeret(pont_min=0, pont_max=8, hossz_min={"C": 3},
                nyilatkozott=True),
}

MENET = [{"ules": "N", "licit": "1S"}, {"ules": "E", "licit": "2NT"},
         {"ules": "S", "licit": "P"}, {"ules": "W", "licit": "3C"}]


def test_minden_minta_teljesiti_a_kenyszereket():
    m = mintavetel(SAJAT, "S", TAR, db=40, mag=11)
    assert len(m.leosztasok) == 40
    for lo in m.leosztasok:
        assert lo.kezek["S"] == SAJAT
        n, e = lo.kezek["N"], lo.kezek["E"]
        assert 12 <= ERTEKELOK["HCP"](n) <= 21
        assert n.hossz("S") >= 5
        assert 5 <= ERTEKELOK["HCP"](e) <= 10
        assert e.hossz("C") >= 5 and e.hossz("D") >= 5


def test_a_torzitott_minta_jelzi_magat():
    """Szoros kényszerek mellett az elutasításos ág nem elég — és ezt a
    minta megmondja, ahelyett hogy csendben torzított számot adna."""
    m = mintavetel(SAJAT, "S", TAR, db=40, mag=11)
    assert m.torzitott is True
    assert "TORZÍTOTT" in m.osszefoglalo()


def test_laza_kenyszer_torzitatlan_marad():
    laza = {u: Igeret() for u in ("N", "E", "W")}
    m = mintavetel(SAJAT, "S", laza, db=40, mag=11)
    assert m.torzitott is False
    assert m.hatekonysag == 1.0


def test_ellentmondasos_kenyszertar_hibat_ad():
    rossz = {"N": Igeret(pont_min=20, pont_max=10, nyilatkozott=True),
             "E": Igeret(), "W": Igeret()}
    with pytest.raises(Exception):
        mintavetel(SAJAT, "S", rossz, db=5, mag=1)


def test_kalibracio_a_vart_iranyba_mozdit():
    k = Kalibracio(eltolas={(True, False): 0.25, (False, False): -0.02},
                   minta_db={(True, False): 400, (False, False): 3000})
    assert k.megmerve
    assert k.korrigal(8, kontrazott=True, szan=False) == pytest.approx(8.25)
    assert k.korrigal(8, kontrazott=False, szan=False) == pytest.approx(7.98)


def test_kis_minta_eseten_osszevon():
    """
    A gyűjteményen a kontrázott szan cellája 37 játszmából állt: ±0.24
    standard hibával az "eredménye" zaj. Ilyenkor a durvább modellre
    kell esni, nem zajt korrekcióként használni.
    """
    k = Kalibracio(eltolas={(True, True): 9.9, (False, True): 0.30,
                            (False, False): 0.03},
                   minta_db={(True, True): 37, (False, True): 1549,
                             (False, False): 3551})
    # a kontra-bontást adjuk fel előbb, a szanét nem: a szan a nagyobb hatás
    assert k._cella(True, True) == (False, True)
    assert k.korrigal(8, kontrazott=True, szan=True) == pytest.approx(8.30)
    # Ha semmiből sincs elég minta, nem találunk ki számot.
    ures = Kalibracio(eltolas={(True, True): 9.9}, minta_db={(True, True): 5})
    assert ures.korrigal(8, kontrazott=True, szan=True) == 8


def test_eloszlasbol_huz_nem_atlagot_ad():
    """
    A LÉNYEG: az átlagkorrekciót a kerekítés elnyeli — round(8 + 0.16)
    továbbra is 8 —, tehát átlaggal a szimuláció valójában
    korrigálatlan marad. Az eloszlásból húzva viszont a védelem
    hibázása tényleg megjelenik a mintában.
    """
    import random
    k = Kalibracio(eltolas={(True, False): 0.16},
                   minta_db={(True, False): 422},
                   eloszlas={(True, False): {-1: 82, 0: 196, 1: 109, 2: 22}})
    assert k.van_eloszlas
    rnd = random.Random(1)
    huzasok = [k.huz(8, True, False, rnd) for _ in range(3000)]
    assert set(huzasok) == {7, 8, 9, 10}
    # az átlag a mért eltolás közelében van, de a SZÓRÁS is megvan
    assert 8.0 < sum(huzasok) / len(huzasok) < 8.4
    assert len([h for h in huzasok if h != 8]) > 1000

    # a DD-ütésszám határain belül marad
    assert k.huz(13, True, False, rnd) <= 13
    assert k.huz(0, True, False, rnd) >= 0


def test_kalibralatlan_allapot_kimondja_magat():
    assert "NINCS KALIBRÁLVA" in Kalibracio().leiras()


def test_imp_es_mp_ellentetes_lehet():
    """
    Hét leosztásból hatszor nyer kicsit a kontra, egyszer veszít sokat.
    MP-ben a kontra a jobb (86% nyerési arány), IMP-ben nem.
    Ugyanaz a döntés, két verseny, két helyes válasz.
    """
    a = Kimenetel("kontra", Kontraktus(3, "C", "X", "W"),
                  [100] * 6 + [-1400])
    b = Kimenetel("saját", Kontraktus(4, "S", "", "N"), [50] * 7)
    o = Osszemeres(a, b, kalibralva=True)
    assert o.nyeresi_arany > 0.8
    assert o.imp_kulonbseg < 0
    assert "ELLENTÉTES" in o.osszefoglalo()


def _tabla(ertek: int) -> dict:
    """Minden irány, minden szín ugyanannyi ütés — a logika próbájához."""
    return {u: {sz: ertek for sz in ("S", "H", "D", "C", "NT")}
            for u in ("N", "E", "S", "W")}


def test_buntetes_vagy_sajat_lefut_dds_nelkul():
    m = mintavetel(SAJAT, "S", TAR, db=10, mag=5)
    allas = Allas(ules="S", beliallas="NONE", licitek=MENET, oszto="N",
                  kenyszertar=TAR)
    # 6 ütés mindenkinek: a 3C erősen bukik, a mi kontraktusunk is
    o = buntetes_vagy_sajat(allas, m.leosztasok,
                            dd_tablak=[_tabla(6)] * 10)
    assert o.a.kontraktus.kontra == "X"
    assert o.a.atlag > 0            # a bukásuk nekünk pozitív írás
    assert o.b.atlag < 0            # a saját kontraktusunk nagyot bukna
    assert o.imp_kulonbseg > 0      # itt a kontra egyértelműen jobb
    assert not o.kalibralva


def test_sajat_kontraktus_a_jelenlegi_szint_folott_keres():
    m = mintavetel(SAJAT, "S", TAR, db=5, mag=5)
    allas = Allas(ules="S", beliallas="NONE", licitek=MENET, oszto="N",
                  kenyszertar=TAR)
    o = buntetes_vagy_sajat(allas, m.leosztasok, dd_tablak=[_tabla(10)] * 5)
    k = o.b.kontraktus
    magasabb = (k.szint > 3) or (k.szint == 3 and k.szin != "C")
    assert magasabb, f"{k} nem magasabb a 3C-nél"
    assert k.felvevo in ("N", "S")
