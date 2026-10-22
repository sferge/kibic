"""A rendszer a profilkódból (1.1), a rendszerlista és a kért kártya (1.2-tervezet)."""
import pytest

from kibic.szolgaltatas import profil
from kibic.szolgaltatas.magyarazat import KartyaHiba, kartya_valasz, kepessegek

KINALT = [{"system": "KIBIC_STAND", "name": "Kibic standard", "kind": "KONVENCIOKARTYA"},
          {"system": "MOHA_STAND", "name": "Moha standard", "kind": "KONVENCIOKARTYA"}]


@pytest.fixture(autouse=True)
def kinalt(monkeypatch):
    monkeypatch.setattr(profil, "KINALT_FORRAS", lambda: KINALT)
    monkeypatch.setattr(profil, "ALAP_RENDSZER", "KIBIC_STAND")
    monkeypatch.setattr(profil, "ALAP_PAR", None)
    monkeypatch.delenv("KIBIC_PROFILOK", raising=False)


def _k(kod=None, **tobb):
    return dict({"actor": {"seat": "S", "profile_code": kod}}, **tobb)


def test_feloldas_sorrend(monkeypatch):
    assert profil.profil_feloldas(_k())["system"] == "KIBIC_STAND"
    p = profil.profil_feloldas(_k("moha_stand"))
    assert (p["system"], p["matched"]) == ("MOHA_STAND", True)
    # 1.1: a MohaBridzs a modell nevét küldi — szó nélkül a saját rendszer
    p = profil.profil_feloldas(_k("kibic"))
    assert (p["system"], p["matched"]) == ("KIBIC_STAND", False)
    monkeypatch.setenv("KIBIC_PROFILOK", "haziko=MOHA_STAND:Feri-Juli")
    p = profil.profil_feloldas(_k("haziko"))
    assert (p["system"], p["pair"], p["matched"]) == ("MOHA_STAND", "Feri-Juli", True)


def test_adatbazis_nelkul_is_licital(monkeypatch):
    def hiba():
        raise RuntimeError("nincs db")
    monkeypatch.setattr(profil, "KINALT_FORRAS", hiba)
    p = profil.profil_feloldas(_k("moha_stand"))
    assert p["system"] == "KIBIC_STAND"


def test_rendszer_lista_es_kepessegek():
    lista = profil.rendszer_lista()
    assert [(r["code"], r["default"]) for r in lista] == [
        ("KIBIC_STAND", True), ("MOHA_STAND", False)]
    k = kepessegek(lista, profil.ALAP_RENDSZER)
    assert k["default_system"] == "KIBIC_STAND" and len(k["systems"]) == 2


def _kartya(kod):
    return {"system": kod, "name": kod.title()}


def test_kartya_parameter_nelkul_az_aktualis_profile():
    v = kartya_valasz(_k("kibic", format="json"), _kartya)
    assert v["system"] == "KIBIC_STAND" and v["current"] is True
    assert v["current_system"] == "KIBIC_STAND" and "html" not in v


def test_kartya_kert_rendszer_a_profiltol_fuggetlenul():
    v = kartya_valasz(_k("kibic", system="MOHA_STAND"), _kartya,
                      lambda a: "<html>")
    assert v["system"] == "MOHA_STAND" and v["current"] is False
    assert v["current_system"] == "KIBIC_STAND" and v["html"] == "<html>"


def test_kartya_ismeretlen_rendszer():
    with pytest.raises(KartyaHiba) as e:
        kartya_valasz(_k(system="LICREN_STAND"), _kartya)
    with pytest.raises(KartyaHiba):
        kartya_valasz(_k(system="kibic"), _kartya)     # modellnév nem rendszer
    assert e.value.statusz == 404
