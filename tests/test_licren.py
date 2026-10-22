"""A LICREN .lr formális nyelv értelmezője."""
from kibic.impex.licren import feltetel_elemez, tokenizal


def test_egyszeru_feltetel():
    cs = feltetel_elemez("(S>4)&(P>11)")
    assert cs.fajta == "ES" and len(cs.gyerekek) == 2


def test_vagy_precedencia_alacsonyabb_mint_es():
    cs = feltetel_elemez("(F>15)&(S>4)o(F>20)")
    assert cs.fajta == "VAGY"


def test_intervallum():
    cs = feltetel_elemez("F[12,14]")
    assert cs.fajta == "INTERVALLUM" and cs.ertek == (12, 14)


def test_negacio():
    assert feltetel_elemez("n(S>4)").fajta == "NEM"


def test_elosztas_es_lap():
    assert feltetel_elemez("e4432").fajta == "ELOSZTAS"
    assert feltetel_elemez("a5431").fajta == "RENDEZETT_ELOSZTAS"
    assert feltetel_elemez("(vSA=1)").fajta == "OSSZE"


def test_osszeg_es_kivonas():
    assert feltetel_elemez("(S>H-1)").fajta == "OSSZE"
    assert feltetel_elemez("(vHA+vHK+vHQ>2)").fajta == "OSSZE"


def test_szkorhelyzet():
    assert feltetel_elemez("(@Mo@A)").fajta == "VAGY"


def test_csupasz_jelzo():
    assert feltetel_elemez("b").fajta == "JELZO_ALLITAS"
