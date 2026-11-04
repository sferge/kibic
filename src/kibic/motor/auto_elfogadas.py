"""
AUTOMATIKUS ELFOGADÁS: a JAVASOLT sor ELFOGADOTT lesz, ha nem ütközik.

A szerkesztő kérése (2026-11-04): a JAVASOLT állapot kézi kezelése
nehézkes; ami nem ütközik egyetlen ELFOGADOTT vagy JAVASOLT sorral sem,
az legyen ELFOGADOTT.

    * ÜTKÖZÉS: a `rendszercheck` szerint — ugyanabban a licithelyzetben
      ugyanarra a kézre két azonos rangú sor KÜLÖNBÖZŐ licitet ad;
    * a vizsgálat MINDEN rendszerben lefut, amely a sort tartalmazza
      (teszt módú feloldás: ELFOGADOTT + JAVASOLT + FELULVIZSGALANDO);
    * a sor csak akkor fogadható el, ha legalább egy rendszerben
      ténylegesen vizsgálat alá került, és sehol sem ütközött;
    * ELLENŐRIZETLEN (nem bontható minta, pl. `..` / `*`, vagy egyetlen
      rendszer sem hivatkozza): JAVASOLT marad.

Melyik sor jelölt: az import csak az ÚJ vagy MEGVÁLTOZOTT sorokat adja
át (a kézzel JAVASOLT-ra visszaállított, változatlan sort nem bírálja
felül); a `--auto-elfogad` kapcsoló az összes meglévő JAVASOLT sort.

Adatbázis nélkül tesztelhető: a bemenet a feloldott sorlista
rendszerenként.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .rendszercheck import ellenoriz

AUTO_JOVAHAGYO = "auto (ütközésmentes)"


@dataclass
class AutoEredmeny:
    elfogadhato: set[int] = field(default_factory=set)
    utkozo: dict[int, list[str]] = field(default_factory=dict)
    ellenorizetlen: set[int] = field(default_factory=set)
    rendszerek: list[str] = field(default_factory=list)

    def jelentes(self, nev=None) -> str:
        nev = nev or (lambda i: f"#{i}")
        s = [f"Automatikus elfogadás ({', '.join(self.rendszerek) or '-'}): "
             f"{len(self.elfogadhato)} sor ELFOGADOTT, "
             f"{len(self.utkozo)} ütközik, "
             f"{len(self.ellenorizetlen)} ellenőrizetlen (JAVASOLT marad)."]
        for i, okok in sorted(self.utkozo.items(), key=lambda x: nev(x[0])):
            s.append(f"  ÜTKÖZIK  {nev(i)}")
            s += [f"      {o}" for o in okok[:3]]
        for i in sorted(self.ellenorizetlen, key=nev):
            s.append(f"  ELLENŐRIZETLEN  {nev(i)}")
        return "\n".join(s)


def utkozesmentes(rendszerek: dict, jeloltek: set[int], kez_db: int = 100,
                  mag: int = 1) -> AutoEredmeny:
    """
    `rendszerek`: {kód: (sorok, paramtar, feloldás vagy None)}.
    `jeloltek`: a JAVASOLT sorok licitmenet_id-je.
    """
    er = AutoEredmeny()
    vizsgalt: set[int] = set()
    for kod, (sorok, pt, fel) in sorted(rendszerek.items()):
        sajat = {s.licitmenet_id for s in sorok} & jeloltek
        if not sajat:
            continue
        er.rendszerek.append(kod)
        ch = ellenoriz(sorok, pt, kez_db=kez_db, mag=mag, feloldas=fel,
                       csak_sorok=sajat)
        vizsgalt |= ch.vizsgalt_idk & sajat
        for u in ch.utkozesek:
            ok = (f"{kod} [{u.helyzet or 'nyitás'}]: {' / '.join(u.licitek)}"
                  f" ({u.db} kézen; {', '.join(u.mintak)})")
            for i in u.sor_idk:
                if i in jeloltek:
                    er.utkozo.setdefault(i, []).append(ok)
    er.elfogadhato = (vizsgalt & jeloltek) - set(er.utkozo)
    er.ellenorizetlen = jeloltek - vizsgalt - set(er.utkozo)
    return er
