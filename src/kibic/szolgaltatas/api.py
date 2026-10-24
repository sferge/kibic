"""
HTTP-burkolat a kibic szolgáltatásaihoz (FastAPI).

Indítás:
    pip install "fastapi" "uvicorn[standard]"
    uvicorn kibic.szolgaltatas.api:app --host 0.0.0.0 --port 9050

A logika NEM itt van: ez csak szállítóréteg. A `dd_elemzes()` tiszta
függvény, ezért ugyanaz a kód használható közvetlen importtal is, ha a
hívó szintén Python és ugyanazon a gépen fut.

BIZTONSÁG: ha a KIBIC_SHARED_SECRET környezeti változó be van állítva,
minden kérésnek `Authorization: Bearer <titok>` fejlécet kell hoznia.
"""
from __future__ import annotations

import os
import threading
import time

try:
    from fastapi import Depends, FastAPI, Header, HTTPException, Request
except ImportError as e:      # pragma: no cover
    raise ImportError(
        "A HTTP-burkolathoz a FastAPI kell: pip install fastapi uvicorn"
    ) from e

from .atjaro import (PROTOKOLL, TAR as _IDEM, AtjaroHiba, Utkozes,
                     bid_dontes, claim_dontes, play_dontes)
from .dd import DdHiba, dd_elemzes
from .licit import LicitHiba, licit_elemzes

# Titkok. Az ajánlott beállítás EGY érték: KIBIC_SHARED_SECRET = az MB
# AI_SHARED_SECRET-je, és ezt minden védett végpont elfogadja.
#   KIBIC_SHARED_SECRET     — a kibic titka (/v1/kibic/..., és az AI-végpontok is,
#                             ha nincs külön AI-titok)
#   KIBIC_AI_SHARED_SECRET  — OPCIONÁLIS külön titok az AI-végpontokra
#                             (/v1/bridge/..., /v1/kibic/kiosztas...)
# Ha a második nincs megadva, az elsőre esik vissza. Így a gateway
# bekapcsolható úgy, hogy a MÁR MŰKÖDŐ DD-hívások ne kezdjenek 401-et
# kapni — azokat a MohaBridzs a DD-beállításból hívja, más fejléccel.
TITOK = os.getenv("KIBIC_SHARED_SECRET", "")
ATJARO_TITOK = os.getenv("KIBIC_AI_SHARED_SECRET", "") or TITOK

# A DDS globális állapotot használ, a szálbiztonsága nem garantált —
# ezért egy zár mögé tesszük. Ha ez szűk keresztmetszet lesz, külön
# folyamatokba érdemes tenni, nem szálakba.
_DDS_ZAR = threading.Lock()

app = FastAPI(title="kibic", version="0.2.0",
              description="Bridzs: double dummy elemzés és licitmagyarázat")

# --- Rendszer-gyorsítótár --------------------------------------------
# Egy rendszer feloldása (öröklés + paraméterek) drága: kérésenként
# újracsinálni pazarlás, ezért egyszer töltjük be és megtartjuk. A
# tudásbázis változásakor a `/v1/kibic/ujratolt` üríti.

_TAR: dict[tuple, tuple] = {}
_TAR_ZAR = threading.Lock()


def _db_kapcsolat():
    import pymysql
    return pymysql.connect(
        host=os.getenv("KIBIC_HOST", "localhost"),
        user=os.getenv("KIBIC_USER", "kibic"),
        password=os.getenv("KIBIC_PASS", ""),
        database=os.getenv("KIBIC_DB", "kibic"),
        charset="utf8mb4", autocommit=False)


# TESZT MÓD: a jóvá nem hagyott (JAVASOLT) szabálysorokat is használja.
# Alapértelmezés a környezeti változóból; a /v1/kibic/licit kérésben a
# "test_mode": true/false felülírja. A JEGELT sorokat egyik mód sem látja.
TESZT_MOD = os.getenv("KIBIC_TESZT_MOD", "") in ("1", "igen", "true")


def _rendszer_betolto(rendszer_kod: str, par_nev: str | None,
                      teszt: bool | None = None):
    """A licit-szolgáltatás ezt kapja: (szabálysorok, paramétertár)."""
    teszt = TESZT_MOD if teszt is None else bool(teszt)
    kulcs = (rendszer_kod, par_nev, teszt)
    with _TAR_ZAR:
        if kulcs in _TAR:
            return _TAR[kulcs]
    from ..motor.feloldas import FeloldasHiba, feloldas
    from ..motor.kriterium import parametertar_betolt
    conn = _db_kapcsolat()
    try:
        sorok = feloldas(conn, rendszer_kod, teszt=teszt).sorok
        paramtar = parametertar_betolt(conn, rendszer_kod, par_nev)
    except FeloldasHiba as e:
        raise LicitHiba(str(e)) from e
    finally:
        conn.close()
    with _TAR_ZAR:
        _TAR[kulcs] = (sorok, paramtar)
    return sorok, paramtar


# A licit-szolgáltatás innen tudja, mi az alapértelmezett mód (a válaszba írja).
_rendszer_betolto.teszt_alap = TESZT_MOD


def _jogosultsag(authorization: str | None = Header(default=None)) -> None:
    if not TITOK:
        return
    varhato = f"Bearer {TITOK}"
    if authorization != varhato:
        raise HTTPException(status_code=401, detail="Érvénytelen titok")


def _jogosultsag_atjaro(authorization: str | None = Header(default=None)
                        ) -> None:
    """A gateway-végpontok saját titka (lásd a fenti megjegyzést)."""
    if not ATJARO_TITOK:
        return
    if authorization != f"Bearer {ATJARO_TITOK}":
        raise HTTPException(status_code=401, detail="Érvénytelen titok")


@app.get("/v1/kibic/allapot")
def allapot() -> dict:
    """Életjel: a DDS és a tudásbázis elérhetősége."""
    from ..domain import ERTEKELOK
    ki: dict = {"statusz": "ok", "ertekelok": len(ERTEKELOK),
                "betoltott_rendszer": sorted({k[0] for k in _TAR}),
                "teszt_mod": TESZT_MOD,
                "atjaro_protokoll": PROTOKOLL}
    try:
        from ..solver import dds            # noqa: F401
        ki["dds"] = "elerheto"
    except ImportError as e:
        ki["statusz"] = "korlatozott"
        ki["dds"] = "hianyzik"
        ki["hiba"] = str(e)
    try:
        conn = _db_kapcsolat()
        conn.close()
        ki["adatbazis"] = "elerheto"
    except Exception as e:            # noqa: BLE001
        ki["statusz"] = "korlatozott"
        ki["adatbazis"] = f"nem elerheto: {e}"
    return ki


@app.post("/v1/kibic/dd", dependencies=[Depends(_jogosultsag)])
async def dd(keres: dict, request: Request) -> dict:
    """Laponkénti double dummy elemzés egy játékállásra."""
    start = time.time()
    try:
        with _DDS_ZAR:
            valasz = dd_elemzes(keres)
    except DdHiba as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ImportError as e:
        raise HTTPException(status_code=503,
                            detail=f"A DDS nem elérhető: {e}") from e
    valasz["elapsed_ms"] = int((time.time() - start) * 1000)
    return valasz


@app.post("/v1/kibic/dd-tabla", dependencies=[Depends(_jogosultsag)])
async def dd_tabla_vegpont(keres: dict) -> dict:
    """
    Leosztás-elemzés: a 20 mezős DD-tábla, vonalankénti maximum, par, és
    ha a kérés hozza, a játszott kontraktus eltérése a partól. Ugyanazt a
    kéréstestet fogadja, mint a /v1/kibic/dd (+ `dealer`,
    `declarer_tricks`). Leosztásonként elég egyszer hívni.
    """
    from .ddtabla import ddtabla_elemzes
    start = time.time()
    try:
        with _DDS_ZAR:
            valasz = ddtabla_elemzes(keres)
    except ValueError as e:        # DdHiba is ValueError; a domain (pl. "8S",
        raise HTTPException(       # rossz PBN) sima ValueError-t dob
            status_code=400, detail=str(e)) from e
    except ImportError as e:
        raise HTTPException(status_code=503,
                            detail=f"A DDS nem elérhető: {e}") from e
    valasz["elapsed_ms"] = int((time.time() - start) * 1000)
    return valasz


@app.post("/v1/kibic/licit", dependencies=[Depends(_jogosultsag)])
async def licit(keres: dict, request: Request) -> dict:
    """
    Mit licitálna a kibic — és mit értett meg az eddigi menetből?

    A válasz akkor is hasznos, ha nem tud licitálni: az
    `auction_understanding` és a `coverage` megmondja, hol néma a
    rendszer. Éppen ez a mérés.
    """
    start = time.time()
    try:
        valasz = licit_elemzes(keres, _rendszer_betolto)
    except LicitHiba as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ImportError as e:
        raise HTTPException(status_code=503,
                            detail=f"Hiányzó függőség: {e}") from e
    valasz["elapsed_ms"] = int((time.time() - start) * 1000)
    return valasz


@app.post("/v1/kibic/ujratolt", dependencies=[Depends(_jogosultsag)])
def ujratolt() -> dict:
    """A rendszer-gyorsítótár ürítése a tudásbázis módosítása után."""
    with _TAR_ZAR:
        db = len(_TAR)
        _TAR.clear()
        _KARTYA.clear()
        _KINALT.clear()
        _ISMERT.clear()
        _KATALOGUS.clear()
        _LEIRAS.clear()
    idem = _IDEM.urit()
    return {"statusz": "ok", "kiuritett_rendszer": db,
            "kiuritett_idempotencia": idem}


# =====================================================================
# MohaBridzs AI Gateway — `mohabridzs-ai/1.0`
# =====================================================================
# Ugyanaz a motor, más szerződés: itt pontosan EGY szabályos akciót kell
# adni a `deadline_ms` határidőn belül. A fordítás az `atjaro` modulban
# van; itt csak a szállítás, a titok és az idempotencia.

def _idempotencia(keres: dict, kulcs: str | None):
    try:
        return _IDEM.olvas(kulcs, keres)
    except Utkozes as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@app.post("/v1/bridge/bid", dependencies=[Depends(_jogosultsag_atjaro)])
async def bridge_bid(
    keres: dict,
    idempotency_key: str | None = Header(default=None,
                                         alias="Idempotency-Key"),
) -> dict:
    """Licitdöntés a MohaBridzs webappnak."""
    kesz = _idempotencia(keres, idempotency_key)
    if kesz is not None:
        return kesz
    try:
        valasz = bid_dontes(keres, _rendszer_betolto)
    except AtjaroHiba as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    _IDEM.ir(idempotency_key, keres, valasz)
    return valasz


@app.post("/v1/bridge/explain", dependencies=[Depends(_jogosultsag_atjaro)])
async def bridge_explain(keres: dict) -> dict:
    """
    Licitmagyarázat bárkinek az asztalnál (mohabridzs-ai/1.1): csak a
    MEGÁLLAPODÁS, kéz nélkül. Tiszta függvény — nincs idempotencia-tár.
    """
    from .magyarazat import MagyarazatHiba, explain_valasz
    try:
        return explain_valasz(keres, _rendszer_betolto)
    except (MagyarazatHiba, LicitHiba) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


_KARTYA: dict[tuple, dict] = {}


def _kartya(rendszer_kod: str, teszt: bool | None = None) -> dict:
    """A kártya adatai (gyorsítótárazva; a /v1/kibic/ujratolt üríti)."""
    from ..motor.kartya import kartya_db
    teszt = TESZT_MOD if teszt is None else bool(teszt)
    kulcs = (rendszer_kod, teszt)
    with _TAR_ZAR:
        if kulcs in _KARTYA:
            return _KARTYA[kulcs]
    conn = _db_kapcsolat()
    try:
        adat = kartya_db(conn, rendszer_kod, teszt)
    finally:
        conn.close()
    with _TAR_ZAR:
        _KARTYA[kulcs] = adat
    return adat


# A kínált rendszerek (van kártyájuk) — a profilfeloldás és a
# capabilities ebből dolgozik. Gyorsítótárazva; az ujratolt üríti.
_KINALT: list[dict] = []


def _kinalt() -> list[dict]:
    from ..motor.kartya import kinalt_rendszerek_db
    with _TAR_ZAR:
        if _KINALT:
            return list(_KINALT)
    conn = _db_kapcsolat()
    try:
        lista = kinalt_rendszerek_db(conn)
    finally:
        conn.close()
    with _TAR_ZAR:
        _KINALT[:] = lista
    return list(lista)


# Az ismert rendszerek és rendszercsaládok (kártya nélkül is): a vonalak
# rendszerének feloldásához (game.systems). Gyorsítótárazva.
_ISMERT: dict[str, dict] = {}


def _ismert() -> dict[str, dict]:
    with _TAR_ZAR:
        if _ISMERT:
            return dict(_ISMERT)
    conn = _db_kapcsolat()
    try:
        cur = conn.cursor()
        cur.execute("SELECT kod, fajta, csalad, nev, leiras FROM rendszer"
                    " WHERE aktiv = 1 AND fajta IN"
                    " ('ALAPRENDSZER', 'RENDSZER', 'RENDSZERCSALAD')")
        adat = {str(r[0]).upper(): {"kind": r[1], "family": r[2], "name": r[3],
                                    "description": r[4]}
                for r in cur.fetchall()}
    finally:
        conn.close()
    with _TAR_ZAR:
        _ISMERT.clear()
        _ISMERT.update(adat)
    return dict(adat)


from . import profil as _profil  # noqa: E402

_profil.KINALT_FORRAS = _kinalt
_profil.ISMERT_FORRAS = _ismert


@app.post("/v1/bridge/card", dependencies=[Depends(_jogosultsag_atjaro)])
async def bridge_card(keres: dict) -> dict:
    """
    A konvenciókártya (mohabridzs-ai/1.1): a MEGÁLLAPODÁS, kéz nélkül,
    WBF-szerkezetben. `system` nélkül a kérdezett AI aktuális profiljáé,
    `system`-mel a kért rendszeré. `format`: "html" (alap) vagy "json".
    """
    from ..motor.kartya import kartya_html
    from .magyarazat import KartyaHiba, kartya_valasz
    try:
        return kartya_valasz(keres, _kartya, kartya_html)
    except KartyaHiba as e:
        raise HTTPException(status_code=e.statusz, detail=str(e)) from e
    except Exception as e:             # noqa: BLE001
        raise HTTPException(status_code=400,
                            detail=f"A kártya nem készíthető el: {e}") from e


@app.get("/v1/kibic/kartya")
def kibic_kartya(system: str | None = None, test_mode: bool | None = None):
    """
    A kártya böngészőben. `system` nélkül az alaprendszeré (KIBIC_RENDSZER):
    /v1/kibic/kartya  vagy  /v1/kibic/kartya?system=KIBIC_STAND
    """
    from fastapi.responses import HTMLResponse

    from ..motor.kartya import kartya_html
    try:
        adat = _kartya((system or _profil.ALAP_RENDSZER).upper(), test_mode)
    except Exception as e:             # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    return HTMLResponse(kartya_html(adat))


_LEIRAS: dict = {}


@app.get("/v1/kibic/leiras")
def kibic_leiras(system: str | None = None, format: str = "html",
                 test_mode: bool | None = None):
    """
    A rendszer TELJES leírása (a feloldott rendszer minden szabálya, forrás
    és fejezet szerint) — a kártya hosszú párja. `format`: html (nyomtatható)
    vagy md. Titok nélkül hívható, mint a kártya (kéz nincs benne).
    """
    from fastapi.responses import HTMLResponse, PlainTextResponse

    from .leiras import leiras_db, leiras_html, leiras_md
    kod = (system or _profil.ALAP_RENDSZER).upper()
    teszt = TESZT_MOD if test_mode is None else bool(test_mode)
    kulcs = (kod, teszt)
    with _TAR_ZAR:
        adat = _LEIRAS.get(kulcs)
    if adat is None:
        conn = _db_kapcsolat()
        try:
            adat = leiras_db(conn, kod, teszt)
        except Exception as e:         # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(e)) from e
        finally:
            conn.close()
        with _TAR_ZAR:
            _LEIRAS[kulcs] = adat
    nev = kod.lower()
    if str(format).lower() == "md":
        return PlainTextResponse(leiras_md(adat), media_type="text/markdown; charset=utf-8",
                                 headers={"Content-Disposition": f'attachment; filename="{nev}.md"'})
    return HTMLResponse(leiras_html(adat))


@app.get("/v1/bridge/capabilities")
def bridge_kepessegek() -> dict:
    """
    Mit tud az AI-szolgáltatás, melyik rendszert játssza (1.1), és milyen
    rendszereket ismer (1.2-tervezet). Titok nélkül is hívható.
    """
    from ..motor.kartya import kartya_kivonat
    from .magyarazat import kepessegek
    rendszerek = []
    for r in _profil.rendszer_lista():
        try:
            r["summary"] = kartya_kivonat(_kartya(r["code"]))
        except Exception:              # noqa: BLE001 — a lista akkor is menjen
            r["summary"] = None
        rendszerek.append(r)
    try:
        csaladok = [{"code": k, "name": v.get("name"), "description": v.get("description")}
                    for k, v in sorted(_ismert().items())
                    if v.get("kind") == "RENDSZERCSALAD"]
    except Exception:                  # noqa: BLE001
        csaladok = []
    ki = kepessegek(rendszerek, _profil.ALAP_RENDSZER, csaladok)
    from .kiosztas import PROTOKOLL as _DD_PROT
    # 1.1: a kibic a licitdöntés előtt magyarázatot kérhet (request_information)
    ki["request_information"] = True
    ki["deal_design"] = {"protocol": _DD_PROT, "endpoint": "/v1/kibic/kiosztas",
                         "capabilities": "/v1/kibic/kiosztas/kepessegek"}
    return ki


_KATALOGUS: dict = {}


@app.get("/v1/bridge/systems")
def bridge_rendszerek() -> dict:
    """
    A rendszerek katalógusa (1.2): RENDSZERCSALÁD → ALAPRENDSZER → RENDSZER,
    csak az alapadatok — a MohaBridzs ebből kínál választólistát a
    játékosoknak (és ebből tölti a game.systems-t). Titok nélkül hívható.
    """
    from .katalogus import katalogus_db
    with _TAR_ZAR:
        if _KATALOGUS:
            return dict(_KATALOGUS)
    try:
        kartyas = {r["system"].upper() for r in _kinalt()}
    except Exception:                  # noqa: BLE001
        kartyas = set()
    conn = _db_kapcsolat()
    try:
        adat = katalogus_db(conn, kartyas, _profil.ALAP_RENDSZER)
    finally:
        conn.close()
    adat = {"protocol": "mohabridzs-ai/1.2", **adat}
    with _TAR_ZAR:
        _KATALOGUS.clear()
        _KATALOGUS.update(adat)
    return adat


@app.post("/v1/kibic/magyaraz", dependencies=[Depends(_jogosultsag)])
async def kibic_magyaraz(keres: dict) -> dict:
    """
    MŰHELY: egy elhangzott licit jelentése + mit licitált volna ott a kibic
    a megadott kézzel, és miért. A kéz adatait is visszaadja — csak
    tanításhoz, ellenfélnek soha.
    """
    from .magyarazat import magyaraz_muhely
    try:
        return magyaraz_muhely(keres, _rendszer_betolto)
    except LicitHiba as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/v1/bridge/play", dependencies=[Depends(_jogosultsag_atjaro)])
async def bridge_play(
    keres: dict,
    idempotency_key: str | None = Header(default=None,
                                         alias="Idempotency-Key"),
) -> dict:
    """Kijátszás: tények -> DD-szűrő -> a megállapodás a jó lapok közül (motor/lejatszas.py)."""
    from starlette.concurrency import run_in_threadpool
    kesz = _idempotencia(keres, idempotency_key)
    if kesz is not None:
        return kesz
    try:
        # a mintavétel és a DD másodpercekig is tarthat: ne az eseményhurkon fusson
        valasz = await run_in_threadpool(play_dontes, keres, _rendszer_betolto,
                                         _jelzesek_rendszerhez, _DDS_ZAR)
    except AtjaroHiba as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    _IDEM.ir(idempotency_key, keres, valasz)
    return valasz


@app.post("/v1/bridge/claim", dependencies=[Depends(_jogosultsag_atjaro)])
async def bridge_claim(
    keres: dict,
    idempotency_key: str | None = Header(default=None,
                                         alias="Idempotency-Key"),
) -> dict:
    """Terítés elbírálása (MB AI-terítés 1.0): elfogadjuk-e (motor/terites.py)."""
    from starlette.concurrency import run_in_threadpool
    kesz = _idempotencia(keres, idempotency_key)
    if kesz is not None:
        return kesz
    try:
        valasz = await run_in_threadpool(claim_dontes, keres, _DDS_ZAR)
    except AtjaroHiba as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    _IDEM.ir(idempotency_key, keres, valasz)
    return valasz


# =====================================================================
# RENDSZERSZERKESZTŐ — böngészős műhely (GET /szerkeszto)
# =====================================================================
# A felület egy statikus oldal; az adatokat a /v1/kibic/szerk/* végpontok
# adják (ugyanaz a titok, mint a többi /v1/kibic/* végpontnak — az oldal
# fejlécében adható meg). A próbakéz a /v1/kibic/licit-et hívja.

def _szerk(fv, *args, **kw):
    from .szerkeszto import SzerkesztoHiba
    conn = _db_kapcsolat()
    try:
        return fv(conn, *args, **kw)
    except SzerkesztoHiba as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        conn.close()


_JELZES_TAR: dict[tuple, object] = {}


def _jelzesek_rendszerhez(rendszer_kod: str):
    """Egy licitrendszer jelzésrendszere (gyorsítótárazva; az újratöltés üríti)."""
    kulcs = (rendszer_kod, TESZT_MOD)
    with _TAR_ZAR:
        if kulcs in _JELZES_TAR:
            return _JELZES_TAR[kulcs]
    from ..motor.kartya import jelzesek_rendszerhez_db, jelzesek_rendszerhez_yaml
    j = None
    try:
        conn = _db_kapcsolat()
        try:
            j = jelzesek_rendszerhez_db(conn, rendszer_kod, TESZT_MOD)
        finally:
            conn.close()
    except Exception as e:             # noqa: BLE001 — pl. a 031 még nem futott le
        print(f"[kibic] jelzésrendszer az adatbázisból: {type(e).__name__}: {e} — YAML-tartalék",
              flush=True)
    if j is None:
        # tartalék: a YAML (rendszerek/yaml + rendszerek/jelzesek) — a lejátszás
        # ne maradjon megállapodás nélkül
        j = jelzesek_rendszerhez_yaml(rendszer_kod, TESZT_MOD)
    with _TAR_ZAR:
        _JELZES_TAR[kulcs] = j
    return j


def _gyorsitotar_urites() -> None:
    with _TAR_ZAR:
        _TAR.clear()
        _JELZES_TAR.clear()
        _KARTYA.clear()
        _KINALT.clear()
        _ISMERT.clear()
        _KATALOGUS.clear()


@app.get("/szerkeszto")
def szerkeszto_oldal():
    from pathlib import Path

    from fastapi.responses import HTMLResponse
    return HTMLResponse((Path(__file__).parent / "szerkeszto.html")
                        .read_text(encoding="utf-8"))


@app.get("/v1/kibic/szerk/rendszerek", dependencies=[Depends(_jogosultsag)])
def szerk_rendszerek():
    from .szerkeszto import rendszerek
    return _szerk(rendszerek)


@app.get("/v1/kibic/szerk/fa", dependencies=[Depends(_jogosultsag)])
def szerk_fa(system: str, test_mode: bool = True):
    from .szerkeszto import fa
    try:
        return _szerk(fa, system, test_mode)
    except HTTPException:
        raise
    except Exception as e:             # noqa: BLE001 — pl. ismeretlen rendszer
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/v1/kibic/szerk/rendszer", dependencies=[Depends(_jogosultsag)])
def szerk_rendszer(system: str):
    from .szerkeszto import rendszer_info
    return _szerk(rendszer_info, system)


@app.get("/v1/kibic/szerk/feloldott", dependencies=[Depends(_jogosultsag)])
def szerk_feloldott(system: str, prefix: str | None = None,
                    openings: bool = False, test_mode: bool = True):
    from .szerkeszto import feloldott
    return _szerk(feloldott, system, prefix, openings, test_mode)


@app.get("/v1/kibic/szerk/fejezetek", dependencies=[Depends(_jogosultsag)])
def szerk_fejezetek(system: str):
    from .szerkeszto import fejezetek
    return _szerk(fejezetek, system)


@app.get("/v1/kibic/szerk/szabalyok", dependencies=[Depends(_jogosultsag)])
def szerk_szabalyok(system: str, chapter: str | None = None):
    from .szerkeszto import szabalyok
    return _szerk(szabalyok, system, chapter)


@app.post("/v1/kibic/szerk/allapot", dependencies=[Depends(_jogosultsag)])
def szerk_allapot(keres: dict):
    """{system, action: jovahagy|jegel|kiolvaszt|visszavon, ids | chapter, author}"""
    from .szerkeszto import allapot_muvelet
    n = _szerk(allapot_muvelet, keres.get("system"), keres.get("action"),
               keres.get("ids"), keres.get("chapter"), keres.get("author") or "")
    _gyorsitotar_urites()                  # a motor azonnal az újat lássa
    return {"changed": n}


@app.get("/v1/kibic/szerk/megjegyzes", dependencies=[Depends(_jogosultsag)])
def szerk_megjegyzesek(system: str | None = None, key: str | None = None):
    from .szerkeszto import megjegyzesek
    return _szerk(megjegyzesek, system, key or None)


@app.post("/v1/kibic/szerk/megjegyzes", dependencies=[Depends(_jogosultsag)])
def szerk_megjegyzes_ment(keres: dict):
    from .szerkeszto import megjegyzes_ment
    return {"id": _szerk(megjegyzes_ment, keres)}


@app.post("/v1/kibic/szerk/megjegyzes/{mid}/lezar",
          dependencies=[Depends(_jogosultsag)])
def szerk_megjegyzes_lezar(mid: int):
    from .szerkeszto import megjegyzes_lezar
    _szerk(megjegyzes_lezar, mid)
    return {"ok": True}


# --- a szerkesztő jelzés-oldala (jelzésrendszerek, 030) ---

@app.get("/v1/kibic/szerk/jelzes/rendszerek", dependencies=[Depends(_jogosultsag)])
def szerk_jelzes_rendszerek():
    from .jelzes_szerk import jelzes_rendszerek
    return _szerk(jelzes_rendszerek)


@app.get("/v1/kibic/szerk/jelzes/rendszer", dependencies=[Depends(_jogosultsag)])
def szerk_jelzes_rendszer(system: str):
    from .jelzes_szerk import jelzes_rendszer
    return _szerk(jelzes_rendszer, system)


@app.get("/v1/kibic/szerk/jelzes/fa", dependencies=[Depends(_jogosultsag)])
def szerk_jelzes_fa(system: str, level: str = "TESZT"):
    from .jelzes_szerk import jelzes_fa
    return _szerk(jelzes_fa, system, level)


@app.get("/v1/kibic/szerk/jelzes/fejezetek", dependencies=[Depends(_jogosultsag)])
def szerk_jelzes_fejezetek(system: str):
    from .jelzes_szerk import jelzes_fejezetek
    return _szerk(jelzes_fejezetek, system)


@app.get("/v1/kibic/szerk/jelzes/sorok", dependencies=[Depends(_jogosultsag)])
def szerk_jelzes_sorok(system: str, chapter: str | None = None):
    from .jelzes_szerk import jelzes_sorok
    return _szerk(jelzes_sorok, system, chapter)


@app.get("/v1/kibic/szerk/jelzes/feloldott", dependencies=[Depends(_jogosultsag)])
def szerk_jelzes_feloldott(system: str, level: str = "TESZT"):
    from .jelzes_szerk import jelzes_feloldott
    return _szerk(jelzes_feloldott, system, level)


@app.get("/v1/kibic/szerk/jelzes/proba", dependencies=[Depends(_jogosultsag)])
def szerk_jelzes_proba(system: str, holding: str, situation: str = "INDITAS",
                       level: str = "TESZT", context: str | None = None):
    from .jelzes_szerk import jelzes_proba
    return _szerk(jelzes_proba, system, holding, situation, level,
                  [x for x in (context or "").split(",") if x])


@app.post("/v1/kibic/szerk/jelzes/allapot", dependencies=[Depends(_jogosultsag)])
def szerk_jelzes_allapot(keres: dict):
    """{system, action: jovahagy|jegel|kiolvaszt|visszavon, ids | chapter, author}"""
    from .jelzes_szerk import jelzes_allapot_muvelet
    n = _szerk(jelzes_allapot_muvelet, keres.get("system"), keres.get("action"),
               keres.get("ids"), keres.get("chapter"), keres.get("author") or "")
    _gyorsitotar_urites()                  # a kártya azonnal az újat lássa
    return {"changed": n}


@app.get("/v1/kibic/szerk/export", dependencies=[Depends(_jogosultsag)])
def szerk_export():
    from .szerkeszto import export
    return _szerk(export)


# --- Kiosztástervező (mohabridzs-deal-design/1.1) ------------------------

@app.get("/v1/kibic/kiosztas/kepessegek", dependencies=[Depends(_jogosultsag_atjaro)])
async def kiosztas_kepessegek() -> dict:
    """Mit vállal a kiosztástervező (források, célok, helyzetek, korlátok)."""
    from .kiosztas import kepessegek
    return kepessegek()


@app.post("/v1/kibic/kiosztas", dependencies=[Depends(_jogosultsag_atjaro)])
def kiosztas_vegpont(keres: dict):
    """
    Kiosztássor a MohaBridzs-nek: generált (célzott), PBN-ből vagy kész
    kiosztásokból. Hiba esetén {"protocol", "request_id", "status": "error",
    "error": {"code", "message"}} a megfelelő HTTP-kóddal. Szinkron (def):
    a FastAPI külön szálon futtatja, a DDS-hívások a zár mögött mennek.
    """
    from fastapi.responses import JSONResponse
    from . import kiosztas as k

    class _ZaroltDd(k.DdMotor):
        def tablak(self, lista):
            with _DDS_ZAR:
                return super().tablak(lista)

        def indulasok(self, kezek, kon):
            with _DDS_ZAR:
                return super().indulasok(kezek, kon)

    def naplo(valasz: dict, http: int = 200) -> None:
        """Egy sor a konzolra (mindig), a teljes kérés + értelmezés JSONL-be
        (KIBIC_KIOSZTAS_NAPLO, ha be van állítva). Így utólag is látszik,
        MIT kért az MB, és mit értett belőle a kibic."""
        import json as _json
        import logging
        kr = keres if isinstance(keres, dict) else {}
        cel = kr.get("target") or {}
        st = valasz.get("stats") or {}
        logging.getLogger("uvicorn.error").info(
            "kiosztas: request_id=%s text=%s target=%s preset=%s -> HTTP %s %s %s/%s (%s jelölt, %s ms)%s",
            kr.get("request_id"), bool(kr.get("text")), sorted(cel), cel.get("preset"), http,
            valasz.get("status"), st.get("returned"), st.get("requested"), st.get("tried"),
            st.get("elapsed_ms"),
            f" HIBA {valasz['error']['code']}" if valasz.get("error") else "")
        ut = os.getenv("KIBIC_KIOSZTAS_NAPLO")
        if not ut:
            return
        rovid = dict(kr)
        forras = dict(rovid.get("source") or {})
        if forras.get("pbn"):
            forras["pbn"] = f"<{len(forras['pbn'])} karakter>"
        if forras.get("deals"):
            forras["deals"] = f"<{len(forras['deals'])} kiosztás>"
        rovid["source"] = forras or None
        sor = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "http": http, "request": rovid,
               "status": valasz.get("status"), "error": valasz.get("error"),
               "interpretation": valasz.get("interpretation"), "stats": st,
               "deal_ids": [d.get("deal_id") for d in valasz.get("deals") or []]}
        try:
            with open(ut, "a", encoding="utf-8") as f:
                f.write(_json.dumps(sor, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def hiba(kod, uzenet, http):
        naplo({"status": "error", "error": {"code": kod}}, http)
        return JSONResponse(status_code=http, content={
            "protocol": k.PROTOKOLL,
            "request_id": keres.get("request_id") if isinstance(keres, dict) else None,
            "status": "error", "error": {"code": kod, "message": uzenet}})

    try:
        csaladok = None
        try:
            from .profil import ismert_rendszerek
            ism = ismert_rendszerek()
            rsz = (keres.get("systems") or {}) if isinstance(keres, dict) else {}
            csaladok = {v: (ism.get(str(rsz.get(v) or k.ALAP_RENDSZER).upper()) or {}).get("family")
                        for v in ("NS", "EW")}
        except Exception:          # noqa: BLE001 — család nélkül is licitál
            csaladok = None
        dd = _ZaroltDd() if k.dd_elerheto() else None
        valasz = k.kiosztas(keres, _rendszer_betolto, dd, csaladok)
    except k.KiosztasHiba as e:
        return hiba(e.kod, str(e), e.http)
    except LicitHiba as e:
        return hiba("auction_unavailable", str(e), 503)
    if valasz.get("status") == "empty" and not valasz.get("dry_run"):
        valasz["error"] = {"code": "no_deals_found",
                           "message": "az időkereten belül egyetlen megfelelő kiosztás sem akadt"}
        naplo(valasz, 422)
        return JSONResponse(status_code=422, content=valasz)
    naplo(valasz)
    return valasz


@app.get("/healthz")
def healthz() -> dict:
    """Él-e a folyamat. Nem kötelező a szerződésben, de hasznos."""
    return {"status": "ok", "protocol": PROTOKOLL}


@app.get("/readyz")
def readyz() -> dict:
    """Tud-e dönteni: van-e adatbázis a rendszer betöltéséhez."""
    try:
        conn = _db_kapcsolat()
        conn.close()
    except Exception as e:                      # noqa: BLE001
        raise HTTPException(status_code=503,
                            detail=f"adatbázis nem elérhető: {e}") from e
    return {"status": "ready", "protocol": PROTOKOLL}
