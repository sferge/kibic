"""
A `.env` BETÖLTŐJÉNEK próbája.

Azért van, mert ez a modul pont azt a hibát hivatott kizárni, amit a
tesztek természetüknél fogva NEM vesznek észre: a `conftest.py` betölti a
`.env`-et, tehát a tesztek akkor is zöldek, ha a szolgáltatás nem látja a
jelszót. Itt ezért nem a „működik-e" a kérdés, hanem a három tulajdonság,
amin a csapda múlik:

  * a MEGLÉVŐ környezeti változót nem írja felül (a systemd/Docker
    beállítás erősebb, mint a fejlesztői `.env`);
  * megtalálja a `.env`-et akkor is, ha a munkakönyvtár nem a repó
    (így indul a szolgáltatás systemd alól);
  * az `allapot()` KIMONDJA, ha a jelszó hiányzik — a pymysql
    veremkivonata helyett.
"""
import os
from pathlib import Path

from kibic import env


def test_a_meglevo_kornyezet_erosebb(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("KIBIC_PASS=fajlbol\n", encoding="utf-8")
    monkeypatch.setenv("KIBIC_PASS", "kornyezetbol")
    monkeypatch.chdir(tmp_path)
    env.betolt(ujra=True)
    assert os.environ["KIBIC_PASS"] == "kornyezetbol"


def test_a_hianyzo_kulcsot_potolja(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "# megjegyzés\n"
        "export KIBIC_USER=kibic\n"
        'KIBIC_PASS="idezojeles jelszo"\n'
        "ROSSZ_SOR_EGYENLOSEG_NELKUL\n", encoding="utf-8")
    monkeypatch.delenv("KIBIC_USER", raising=False)
    monkeypatch.delenv("KIBIC_PASS", raising=False)
    monkeypatch.chdir(tmp_path)
    env.betolt(ujra=True)
    assert os.environ["KIBIC_USER"] == "kibic"
    assert os.environ["KIBIC_PASS"] == "idezojeles jelszo"


def test_megtalalja_a_repogyokeret_mas_munkakonyvtarbol(monkeypatch, tmp_path):
    """
    A szolgáltatás nem a repóból indul (systemd, /, bárhonnan). A `.env`
    helyét ezért a MODUL helyéből is tudni kell — ez volt az a hiányzó
    darab, ami miatt a szerver 1045-öt kapott, a tesztek meg zöldek
    voltak.
    """
    gyoker = Path(env.__file__).resolve().parent.parent.parent
    monkeypatch.chdir(tmp_path)                 # üres, .env nélküli hely
    talalt = env.betolt(ujra=True)
    if (gyoker / ".env").is_file():
        assert any(str(gyoker) in t for t in talalt), talalt
    else:
        assert talalt == []                     # nincs .env: nem hiba


def test_az_allapot_kimondja_ha_nincs_jelszo(monkeypatch):
    """
    A jelszót a betöltés UTÁN vesszük el: pont azt az állapotot utánozva,
    amikor a szerver `source .env` nélkül indult. Az `allapot()` élőben
    olvassa a környezetet, tehát ki kell mondania a hiányt.
    """
    for k in ("KIBIC_USER", "KIBIC_PASS", "KIBIC_DB"):
        monkeypatch.delenv(k, raising=False)
    a = env.allapot()
    assert "KIBIC_PASS" in a["hianyzo_adatbazis_valtozo"]
    assert a["figyelmeztetes"] and "1045" in a["figyelmeztetes"]


def test_az_allapot_nem_arulja_el_a_titkot(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KIBIC_PASS", "ez-nagyon-titkos")
    monkeypatch.setenv("KIBIC_AI_SHARED_SECRET", "ez-is")
    env.betolt(ujra=True)
    a = env.allapot()
    szoveg = repr(a)
    assert "ez-nagyon-titkos" not in szoveg
    assert "ez-is" not in szoveg
    assert "beállítva" in a["beallitva"]["KIBIC_PASS"]
