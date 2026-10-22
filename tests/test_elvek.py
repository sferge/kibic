"""
Az ELV mint műfaj — a 016_elvek.sql gépezetének próbája.

"Védekező vonalon a kontra 4♥ magasságáig információs."

Ez a mondat három dolgot mond, és mindhárom más gépezetet kíván:

  1. FALLBACK. Az elv csak akkor szólal meg, ha a konkrét helyzetre
     nincs érvényes konvenciónk. Nem prioritás kérdése: két külön
     kulcsú sor prioritással mindkettő jelölt maradna.
  2. AZ ELV NEM DÖNT. A szabály kapuz (hol érvényes, mit jelent), a
     licitet a mérlegelés választja. Ezért `MERLEGELO`, és a jelöltje
     sosem nyer szabály alapon.
  3. NINCS BENNE SZÁM. Ide elsőre küszöbképlet került ("alapkövetelmény
     + szintenkénti pótlék + zóna-kiigazítás"), és fölösleges volt: a
     magasságot az ütésszám, a zónát a pontozás adja — mindkettőt
     magától. A `test_a_zona_a_pontozasbol_jon` ezt számmal mutatja meg.
"""
from kibic.domain import Kez, Kontraktus
from kibic.domain.pontozas import pontszam
from kibic.motor.feloldas import Sor
from kibic.motor.helyzet import Allas, Igeret
from kibic.motor.kifejezes import Kontextus
from kibic.motor.licital import Licitmotor
from kibic.motor.propagal import Propagalo


class Paramtar:
    """Minimális paramétertár. EGYETLEN megállapodás maradt benne:
    meddig információs a kontra. Ez nem számítható — meg kell beszélni."""
    ERTEKEK = {"INFO_KONTRA_HATAR": "4H"}

    def ertek(self, kod):
        return self.ERTEKEK[kod]


# --- a 016_elvek.sql két sora, Python-alakban -----------------------

ELV_HA = {"t": "ES", "gy": [
    {"t": "AG", "ertek": "VEDEKEZO"},
    {"t": "ISMERT_SZINEK", "ki": "ok", "op": ">=", "db": 1},
    {"t": "LICIT_LEGFELJEBB", "hatar": "INFO_KONTRA_HATAR"},
    {"t": "NEM", "gy": [{"t": "NYILATKOZOTT", "ki": "p"}]}]}


def _sor(minta, fajta="SZABALY", feltetel=None, ha=None, jelentes=None,
         pri=0, magy=None, kulcs=None, mod="SORREND"):
    s = Sor(0, 0, "T", 0, kulcs or minta, minta, None, pri, 0,
            feltetel, magy, magy, "NEM", None)
    s.ha_feltetel = ha
    s.jelentes = jelentes
    s.szabaly_fajta = fajta
    s.dontesi_mod = mod
    return s


# Az elvnek NINCS kéz-feltétele és nincs pont-ígérete: a kontra a
# hatókörben mindig szóba jön, és a mérlegelés dönt.
ELV = _sor(".. (?) X", "ELV", None, ELV_HA,
           {"forsz": "EGY_MENET", "tagad": ["BUNTETO"]},
           magy="információs kontra (elv)", kulcs="ELV_INFO_KONTRA",
           mod="MERLEGELO")

# Az ellenfél nyitása. A minta PÁROSLICIT: az ELLENFÉL szemszögéből
# kanonizálunk, és ott ő kezdte a licitet.
OK_NYITAS = _sor("1A", "SZABALY", {"t": "IGAZ"},
                 jelentes={"pont": {"min": 12}, "hossz": {"@A": {"min": 5}}})


def _menet(licit="1S"):
    return [{"ules": "E", "licit": licit}]


def _allas(licit="1S", beli="NONE", szin="S"):
    tar = {"E": Igeret(pont_min=12, hossz_min={szin: 5}, nyilatkozott=True)}
    return Allas(ules="S", beliallas=beli, licitek=_menet(licit),
                 oszto="E", kenyszertar=tar)


def _motor(szabalyok):
    return Licitmotor(szabalyok, Kontextus(parametertar=Paramtar()),
                      mod="SPECIFIKUSSAG")


KEZ = Kez.pbn_bol("4.AQ75.KJ63.Q952")


# --- 1. FALLBACK -----------------------------------------------------

def test_az_elv_csak_akkor_szolal_meg_ha_nincs_konvencio():
    allas = _allas()

    # (a) csak az elv van: ő jelöl, és a döntés ezt meg is mondja
    d = _motor([ELV]).licital(_menet(), "S", KEZ, allas=allas, oszto="E")
    assert d.elvre_esett
    assert [j.licit for j in d.merlegelendo] == ["X"]

    # (b) van konkrét konvenció is ugyanerre: AZ nyer, az elv néma marad
    konvencio = _sor("(1S) X", "SZABALY", {"t": "IGAZ"},
                     magy="negatív kontra, konkrét megállapodás")
    d2 = _motor([ELV, konvencio]).licital(_menet(), "S", KEZ,
                                          allas=allas, oszto="E")
    assert d2.licit == "X"
    assert not d2.elvre_esett
    assert not d2.merlegelendo


def test_a_propagalo_is_retegez():
    """A jelentés-propagálásban ugyanez: a konvenció elnyomja az elvet."""
    menet = _menet() + [{"ules": "S", "licit": "X"}]
    konvencio = _sor("(1S) X", "SZABALY", {"t": "IGAZ"},
                     jelentes={"pont": {"min": 15, "max": 17}})

    er1 = Propagalo([OK_NYITAS, ELV], Paramtar()).kenyszertar(menet, oszto="E")
    ig = er1.kenyszertar["S"]
    assert ig.forsz == "EGY_MENET"
    assert "BUNTETO" in ig.tagad
    assert ig.pont_min == 0, "az elv NEM ígér erőt — ez szándékos"

    er2 = Propagalo([OK_NYITAS, ELV, konvencio],
                    Paramtar()).kenyszertar(menet, oszto="E")
    assert er2.kenyszertar["S"].pont_min == 15     # a konvenció nyert


# --- 2. AZ ELV NEM DÖNT ---------------------------------------------

def test_az_elv_sosem_nyer_szabaly_alapon():
    """
    A kapuőr átengedi, de a `MERLEGELO` miatt nem lesz belőle licit:
    a jelölt a `merlegelendo` listába kerül. Ha a hívó ezt figyelmen
    kívül hagyja, a kontra elmarad — inkább ne kontrázzunk, mint hogy
    rosszul tegyük.
    """
    d = _motor([ELV]).licital(_menet(), "S", KEZ, allas=_allas(), oszto="E")
    assert d.licit is None
    assert d.merlegelendo and not d.jeloltek
    assert "mérlegelendő" in d.osszefoglalo()


def test_a_hatokor_a_licitmagassagtol_fugg():
    """A 4♥ még belefér, a 4♠ már nem — a határ LICITMAGASSÁG, nem szint."""
    be = _motor([ELV]).licital(_menet("4H"), "S", KEZ,
                               allas=_allas("4H", szin="H"), oszto="E")
    assert be.merlegelendo

    ki = _motor([ELV]).licital(_menet("4S"), "S", KEZ,
                               allas=_allas("4S"), oszto="E")
    assert not ki.merlegelendo, "4S fölött már nem információs a kontra"


# --- 3. NINCS BENNE SZÁM --------------------------------------------

def test_a_zona_a_pontozasbol_jon():
    """
    A zónát NEM kell kódolni. Ugyanaz az áldozat (5♥X) ugyanaz ellen a
    gém ellen (4♠) hány bukásig éri meg? A négy zónahelyzet sorrendje
    tisztán a pontértékekből jön ki, egyetlen szabály nélkül — és pont
    az, amit egy játékos amúgy is tud.
    """
    def fer_bele(beli):
        ovek = pontszam(Kontraktus(4, "S", "", "E"), 10, beli)
        mienk = Kontraktus(5, "H", "X", "S")
        return sum(1 for bukas in (1, 2, 3)
                   if -pontszam(mienk, 11 - bukas, beli) < ovek)

    assert fer_bele("EW") == 3        # mi mans, ŐK bell — a legjobb
    assert fer_bele("NONE") == 2
    assert fer_bele("ALL") == 2
    assert fer_bele("NS") == 1        # mi bell, ŐK mans — a legrosszabb

    # A két középső nem egyforma: a margó dönt, nem a bukásszám.
    def margo(beli):
        return (pontszam(Kontraktus(4, "S", "", "E"), 10, beli)
                + pontszam(Kontraktus(5, "H", "X", "S"), 8, beli))

    assert margo("NONE") > margo("ALL")


def test_az_elv_nem_iger_pontot():
    """
    "Lehet, hogy a partneremnek erős lapja van (18+), de lehet, hogy
    nem." Az elv jelentése ezért nem tartalmaz pont-intervallumot —
    csak azt, hogy nem büntető, és hogy felelni kell rá.
    """
    assert "pont" not in ELV.jelentes
    assert ELV.jelentes["forsz"] == "EGY_MENET"
    assert ELV.feltetel is None, "az elv nem szab kéz-feltételt"
