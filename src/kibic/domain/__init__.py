"""Domain-mag: a bridzs alapfogalmai, adatbázis- és formátumfüggetlenül."""
from .kartya import (
    SZINEK, SZIN_NEV, LAPOK, LAP_ERTEK, ULESEK, ULES_NEV, BELIK,
    Lap, Kez, Leosztas,
    kovetkezo_ules, vonal, beliben,
    ERTEKELOK, ertekeld,
)
from .pontozas import Kontraktus, pontszam, pontszam_ns, imp

__all__ = [
    "SZINEK", "SZIN_NEV", "LAPOK", "LAP_ERTEK", "ULESEK", "ULES_NEV", "BELIK",
    "Lap", "Kez", "Leosztas", "kovetkezo_ules", "vonal", "beliben",
    "ERTEKELOK", "ertekeld",
    "Kontraktus", "pontszam", "pontszam_ns", "imp",
]

# Az értékelő-definíciók AUTOMATIKUS betöltése (pillanatkép vagy DB).
# Enélkül az ERTEKELOK szótár üres maradna.
from . import ertekelo as _ertekelo  # noqa: E402,F401
from .ertekelo import TAR, Ertekelotar, betolt_adatbazisbol  # noqa: E402,F401
