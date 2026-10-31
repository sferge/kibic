"""
SÜRGETÉS ÉS ÉLETJEL — `POST /v1/bridge/urge` (MB 1.1.76, opcionális).

Az MB egy már futó `/bid` vagy `/play` kérésre kérdez rá (`original_request_id`):

    status     él-e a döntés, hol tart
    expedite   „siess”: ha lehet, kész, szabályos döntést kér most
    cancel     (kibic-bővítés, az MB még nem küldi) a döntés eredménye már
               nem kell — a számítás a legközelebbi ponton megáll, a DDS
               felszabadul a többi asztalnak

Ehhez a gateway nyilvántartja a folyamatban lévő döntéseket (`FELADATOK`,
request_id szerint). A lejátszás a mintavétel közben jelenti az előrehaladást
(minták száma, a DDS-re várakozás, a vezető lap biztossága), és sürgetésre a
mintavétel a következő mintánál megáll: a pillanatnyi legjobb lap megy ki az
MB tartaléka helyett (a döntés `meta.kibic.stopped` értéke ilyenkor SURGETES).

A szöveg (`message`) játékosoknak is megjeleníthető: lapot, kezet, elemzést
NEM tartalmaz — csak azt, mennyit dolgozott a kibic és mennyire biztos.
A lap NEVÉT a vezető lap biztosságánál sem mondjuk ki.

A végpont gyors (az MB legfeljebb 3 mp-ig vár): csak memóriát olvas, és
`expedite`-nál legfeljebb `VARAKOZAS_S`-ig vár a kész döntésre.
"""
from __future__ import annotations

import json
import os
import threading
import time

# a kész / hibás döntés ennyi ideig kérdezhető le (az MB 2 percet javasol;
# a 2026-10-25-i megakadásnál az MB perceken át ugyanazt kérte)
MEGORZES_S = float(os.getenv("KIBIC_URGE_MEGORZES_S", "600"))
MAX_FELADAT = 2000
# expedite: legfeljebb ennyit vár a válaszadás előtt a kész döntésre
VARAKOZAS_S = float(os.getenv("KIBIC_URGE_VARAKOZAS_MS", "2000")) / 1000
MAX_UZENET = 300
MAX_VALASZ = 65536
PARANCSOK = ("status", "expedite", "cancel")


class UrgeHiba(ValueError):
    """Értelmezhetetlen életjelkérés (HTTP 400)."""


class Feladat:
    """Egy folyamatban lévő (vagy nemrég befejezett) döntés."""

    def __init__(self, request_id: str, dontes: str, lenyomat: str | None = None,
                 hatarido_ms: int | None = None):
        self.request_id = request_id
        self.dontes = dontes                  # bid / play / claim
        self.lenyomat = lenyomat
        self.hatarido_ms = hatarido_ms
        self.kezdet = time.time()
        self.allapot = "working"              # working / ready / failed
        self.szakasz = "sorban"               # sorban / kovetkeztetes / mintavetel /
        #                                       dds_var / dontes / gondolkodas / kesz
        self.szakasz_kezdet = self.kezdet
        self.keret_s: float | None = None     # a mintavétel időkerete
        self.cel_minta: int | None = None
        self.minta = 0
        self.dds_var_s = 0.0                  # összesen ennyit várt a DDS-re
        self.legjobb: dict[str, int] = {}     # lap -> hány mintában (az egyik) legjobb
        self.valasz: dict | None = None
        self.hiba: str | None = None
        self.vege: float | None = None
        self.siess = threading.Event()        # expedite / cancel
        self.megszakitva = False              # cancel
        self.kesz_esemeny = threading.Event()
        self._zar = threading.Lock()

    # --- a döntés oldaláról (munkaszál) ---------------------------------

    def szakaszba(self, nev: str) -> None:
        with self._zar:
            if self.szakasz != nev:
                self.szakasz, self.szakasz_kezdet = nev, time.time()

    def keret(self, keret_s: float, cel_minta: int | None) -> None:
        with self._zar:
            self.keret_s, self.cel_minta = keret_s, cel_minta
            self.szakasz, self.szakasz_kezdet = "mintavetel", time.time()

    def dd_eredmeny(self, ered, var_s: float = 0.0, szamit: bool = True) -> None:
        """Egy DD-hívás a mintán (`ered`: LapErtekeles-lista)."""
        with self._zar:
            self.dds_var_s += var_s
            if not szamit:
                return
            self.minta += 1
            try:
                for e in ered or ():
                    if getattr(e, "legjobb", False):
                        k = str(getattr(e, "lap", ""))
                        self.legjobb[k] = self.legjobb.get(k, 0) + 1
            except TypeError:
                pass

    def megallito(self) -> bool:
        return self.siess.is_set()

    def kesz(self, valasz: dict) -> None:
        with self._zar:
            if self.allapot == "working":
                self.valasz, self.allapot = valasz, "ready"
                self.szakasz, self.szakasz_kezdet = "gondolkodas", time.time()
                self.vege = time.time()
        self.kesz_esemeny.set()

    def hibas(self, ok: str) -> None:
        with self._zar:
            if self.allapot == "working":
                self.allapot, self.hiba, self.vege = "failed", ok, time.time()
        self.kesz_esemeny.set()

    # --- az életjel oldaláról ----------------------------------------------

    def pillanatkep(self) -> dict:
        """Az előrehaladás szerkezetten (kibic-bővítés: `progress`)."""
        most = time.time()
        with self._zar:
            ki = {"phase": self.szakasz,
                  "elapsed_ms": int((most - self.kezdet) * 1000),
                  "phase_elapsed_ms": int((most - self.szakasz_kezdet) * 1000)}
            if self.dontes == "play" and (self.keret_s or self.minta):
                ki["samples"] = self.minta
                if self.cel_minta:
                    ki["samples_target"] = self.cel_minta
                if self.legjobb and self.minta:
                    ki["leader_confidence"] = round(max(self.legjobb.values()) / self.minta, 2)
            if self.dds_var_s >= 0.05:
                ki["dds_wait_ms"] = int(self.dds_var_s * 1000)
            eta = self._hatralevo_s(most)
            if eta is not None:
                ki["eta_ms"] = int(eta * 1000)
            ki["expedite_requested"] = self.siess.is_set()
        return ki

    def _hatralevo_s(self, most: float) -> float | None:
        if self.allapot != "working":
            return 0.0
        if self.szakasz in ("mintavetel", "dds_var") and self.keret_s:
            # a keret a mintavétel kezdetétől fut; a DDS-várakozás is benne van
            return max(0.0, self.keret_s - (most - self.szakasz_kezdet)) + 0.5
        if self.hatarido_ms:
            return max(0.0, self.hatarido_ms / 1000 * 0.5 - (most - self.kezdet))
        return None

    def uzenet(self, foglalt: int = 0) -> str:
        p = self.pillanatkep()
        mp = p["elapsed_ms"] // 1000
        if self.allapot == "ready":
            return "Elkészültem."
        if self.allapot == "failed":
            return "A döntés hibával végződött."
        sz = self.szakasz
        if sz == "sorban":
            t = f"Sorra várok ({mp} mp óta)."
        elif sz == "kovetkeztetes":
            t = "A licitből következtetek a rejtett lapokra."
        elif sz == "dds_var":
            t = (f"A double dummy elemzőre várok, más asztalok is számolnak "
                 f"(eddig {p.get('samples', 0)} leosztást néztem meg, {mp} mp).")
        elif sz == "mintavetel":
            t = f"Elemzem az állást: eddig {p.get('samples', 0)} lehetséges leosztást néztem meg ({mp} mp)."
            if p.get("leader_confidence") is not None and p.get("samples", 0) >= 6:
                t += f" A legjobbnak látszó lap a leosztások {round(p['leader_confidence'] * 100)}%-ában a legjobb."
        elif sz == "dontes":
            t = "Mindjárt döntök."
        else:
            t = f"Dolgozom ({mp} mp)."
        if self.siess.is_set() and not self.megszakitva:
            if self.dontes == "play":
                t += " A sürgetést megkaptam: a következő elemzett leosztás után döntök."
            else:
                t += " A sürgetést megkaptam; a licitet a futó elemzés végén adom meg."
        if foglalt > 1:
            t += f" Most {foglalt} döntésen dolgozom egyszerre."
        return t[:MAX_UZENET]


class Feladattar:
    """request_id -> Feladat; a befejezetteket `MEGORZES_S`-ig őrzi."""

    def __init__(self, megorzes_s: float = MEGORZES_S, max_db: int = MAX_FELADAT):
        self.megorzes_s = megorzes_s
        self.max_db = max_db
        self._tar: dict[str, Feladat] = {}
        self._zar = threading.Lock()

    def indul(self, keres: dict, dontes: str, lenyomat: str | None = None
              ) -> tuple[Feladat | None, bool]:
        """(feladat, új-e). Ugyanarra a még dolgozó request_id-ra a meglévőt adja."""
        rid = keres.get("request_id") if isinstance(keres, dict) else None
        if not rid:
            return None, False
        try:
            hatarido = int(keres.get("deadline_ms") or 0) or None
        except (TypeError, ValueError):
            hatarido = None
        with self._zar:
            self._takarit()
            f = self._tar.get(rid)
            if f is not None and f.allapot == "working":
                return f, False
            f = Feladat(rid, dontes, lenyomat, hatarido)
            self._tar[rid] = f
            return f, True

    def keres(self, rid: str) -> Feladat | None:
        with self._zar:
            return self._tar.get(rid)

    def foglalt(self) -> int:
        with self._zar:
            return sum(1 for f in self._tar.values() if f.allapot == "working")

    def _takarit(self) -> None:
        most = time.time()
        regi = [k for k, f in self._tar.items()
                if f.vege is not None and most - f.vege > self.megorzes_s]
        for k in regi:
            del self._tar[k]
        if len(self._tar) > self.max_db:
            for k in sorted((k for k, f in self._tar.items() if f.vege is not None),
                            key=lambda k: self._tar[k].vege)[:len(self._tar) - self.max_db]:
                del self._tar[k]

    def urit(self) -> int:
        with self._zar:
            db = len(self._tar)
            self._tar.clear()
        return db


FELADATOK = Feladattar()


# --- a végpont logikája (api.py köti be) ----------------------------------

def ellenoriz(keres: dict) -> tuple[str, str, str]:
    """(request_id, original_request_id, command) vagy UrgeHiba."""
    if not isinstance(keres, dict):
        raise UrgeHiba("A kérés nem JSON-objektum")
    rid, eredeti = keres.get("request_id"), keres.get("original_request_id")
    if not isinstance(rid, str) or not rid:
        raise UrgeHiba("A 'request_id' hiányzik")
    if not isinstance(eredeti, str) or not eredeti:
        raise UrgeHiba("Az 'original_request_id' hiányzik")
    parancs = str(keres.get("command") or "status").lower()
    if parancs not in PARANCSOK:
        raise UrgeHiba(f"Ismeretlen 'command': {parancs}")
    return rid, eredeti, parancs


def _meretre(valasz: dict) -> dict:
    """A teljes válasz legfeljebb 64 KiB: ha kell, a `meta.kibic` diagnosztika kimarad."""
    if len(json.dumps(valasz, ensure_ascii=False, default=str)) <= MAX_VALASZ - 2048:
        return valasz
    v = dict(valasz)
    if isinstance(v.get("meta"), dict):
        v["meta"] = {k: x for k, x in v["meta"].items() if k != "kibic"}
    return v


def valasz(keres: dict, feladat: Feladat | None, tarolt: dict | None = None,
           tar: Feladattar | None = None) -> dict:
    """Az életjel válasza a feladat (vagy a tárolt kész válasz) alapján."""
    rid, eredeti, parancs = ellenoriz(keres)
    tar = tar or FELADATOK
    ki: dict = {"request_id": rid, "original_request_id": eredeti}
    if feladat is None and tarolt is not None:
        # nincs (már) a nyilvántartásban, de az idempotencia-tárban kész válasz van
        ki.update(status="ready", message="Elkészültem.", response=_meretre(tarolt))
        return ki
    if feladat is None:
        ki.update(status="unknown",
                  message="Nem találom ezt a kérést a folyamatban lévő feladatok között.")
        return ki
    if feladat.allapot == "ready" and feladat.valasz is not None:
        ki.update(status="ready", message="Elkészültem.", response=_meretre(feladat.valasz))
        if feladat.megszakitva:
            ki["cancelled"] = True
        return ki
    if feladat.allapot == "failed":
        ki.update(status="failed", message="A döntés hibával végződött.")
        return ki
    ki.update(status="working", message=feladat.uzenet(tar.foglalt()),
              progress=feladat.pillanatkep())
    eta = ki["progress"].get("eta_ms")
    if feladat.siess.is_set():
        ki["retry_after_ms"] = 5000
    elif eta is not None:
        ki["retry_after_ms"] = int(min(60000, max(5000, eta)))
    if feladat.megszakitva:
        ki["cancelled"] = True
    return ki


def parancs_vegrehajt(feladat: Feladat | None, parancs: str) -> None:
    if feladat is None or feladat.allapot != "working":
        return
    if parancs == "cancel":
        feladat.megszakitva = True
        feladat.siess.set()
    elif parancs == "expedite":
        feladat.siess.set()
