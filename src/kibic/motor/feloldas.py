"""
Feloldó: egy rendszer TELJES, érvényes szabálylistájának előállítása.

A tudásbázis rekurzív: egy rendszer `HIVATKOZAS` sorokkal behivatkozhat
másokat (alaprendszert, konvenciókat), azok újakat, és a hivatkozó saját
sorai FELÜLÍRJÁK a behivatkozottak azonos `kulcs`-ú sorait.

    LICREN_STUND
      ├─ HIVATKOZAS -> LICREN_STAND   (746 szabály öröklődik)
      └─ 4 saját SZABALY sor          (a gyenge kettők felülírva)

A feloldás eredménye a `feloldott_licitmenet` táblába kerül. Ez nemcsak
sebesség kérdése: enélkül NEM LÁTHATÓ, mit jelent ténylegesen egy
rendszer az öröklés után — és a rekurzív modellek hibakeresése ilyenkor
reménytelen.

SZABÁLYOK
---------
* Mélységi bejárás: a saját sorok a legspecifikusabbak (mélység 0),
  a behivatkozott rendszereké mélyebbek.
* Azonos `kulcs` esetén a KISEBB MÉLYSÉGŰ nyer; azonos mélységben a
  kártyán ELŐRÉBB hivatkozott rendszer (a HIVATKOZAS sorok sorrendje).
  Ezeket a `sorrendi_felulirasok` listázza, mert csak a sorrend döntött.
* Egy `kulcs`-hoz TÖBB SOR is tartozhat (a LICREN is így csinálja: a
  `2S` nyitásra két szabály van). Ezek EGYÜTT öröklődnek és EGYÜTT
  íródnak felül — csoportos felülírás.
* Kikapcsolt hivatkozás (`hivatkozas_aktiv = 0`) kimarad: "ezt a
  konvenciót mi nem játsszuk".
* KIZÁRÁS (019): a hivatkozó rendszer `KI` módú HIVATKOZAS sora a
  hivatkozó ALATTI teljes fában kizár egy rendszert/konvenciót/
  gyűjteményt, vagy annak egy fejezetét — "ezt a gyűjteményt játsszuk,
  ennek kivételével". A kizárás erősebb a beemelésnél, bármilyen mélyen
  legyen is az.
* TÉMA (019): az azonos témájú konvenciók egymás alternatívái. Ha egy
  rendszer fájában kettő is szerepel, a bejárásban ELŐBB érkező (kisebb
  mélységű, azon belül a kártyán előrébb álló) marad, a másik kimarad —
  és ezt a feloldás mindig feljegyzi (`tema_csere`, azonos mélységben
  `tema_utkozes`, mert ott csak a sorrend döntött).
* Körfigyelés: egy rendszer nem dolgozható fel kétszer.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field


class FeloldasHiba(ValueError):
    pass


@dataclass
class Sor:
    """Egy feloldott szabály."""
    licitmenet_id: int
    rendszer_id: int          # melyik rendszerből származik
    rendszer_kod: str
    melyseg: int              # 0 = saját sor
    kulcs: str
    minta: str
    alfejezet: str | None
    prioritas: int
    specifikussag: int
    feltetel: dict | None
    feltetel_szoveg: str | None
    magyarazat: str | None
    forsz: str
    ismeretlen_jelzok: str | None
    # --- 014_kompetitiv.sql ---
    # Alapértelmezettek, hogy a régi pozicionális hívások ne törjenek.
    jelentes: dict | None = None          # MIT ígér — a kényszertár alapja
    ha_feltetel: dict | None = None       # MILYEN HELYZETBEN (motor/helyzet.py)
    ha_feltetel_szoveg: str | None = None
    elvaras: str = "SEMMI"                # mit vár a partnertől
    magyarazat_en: str | None = None
    # A 009 óta létező oszlop, de eddig csak a motor GLOBÁLIS módja
    # érvényesült. Soronként azért kell, mert vannak szabályok, amelyek
    # nem DÖNTENEK, csak beengednek egy licitet a mérlegelésbe: a
    # büntető kontra ilyen. Az ilyen sor SOSEM nyerhet szabály alapon.
    dontesi_mod: str = "SORREND"
    # --- 016_elvek.sql ---
    # Az ELV nem versenyez a szabályokkal, hanem MÖGÖTTÜK áll: csak
    # akkor szólal meg, ha semmi konkrétabb nem illeszkedett. Ezért nem
    # prioritás, hanem RÉTEG (lásd Licitmotor.licital kétmenetes ciklusát).
    szabaly_fajta: str = "SZABALY"     # SZABALY / ELV / KIVETEL / KIHAGYAS
    ag: str | None = None              # származtatott, a mintából
    # A magyarázathoz: alertálandó-e, melyik fejezetből és forrásból jön
    # (a YAML-importnál a dok_fejezet a forrásfájl: "yaml:.../02_1major.yaml").
    alert: bool = False
    fejezet: str | None = None
    forras: str | None = None
    # FELTÉTELES FELÜLÍRÁS (2026-10-02): ha a kulcsot egy előrébb álló
    # rendszer CSAK helyzeti feltétellel (`ha:`) adta — pl. a Timbuktu az
    # „(1C) X”-et csak erős treff ellen —, ez a sor megmarad, de ott, ahol
    # a felülíró feltétele teljesül, nem él. Itt a felülíró `ha`-fái.
    elnyomo: list | None = None


@dataclass
class Feloldas:
    rendszer_kod: str
    sorok: list[Sor] = field(default_factory=list)
    lanc: list[tuple[str, int]] = field(default_factory=list)  # (kód, mélység)
    felulirt: dict[str, int] = field(default_factory=dict)     # kulcs -> db
    utkozes: list[str] = field(default_factory=list)
    # Azonos mélységű felülírások: itt csak a HIVATKOZAS-sorrend döntött.
    sorrendi_felulirasok: list[str] = field(default_factory=list)
    # Feltételes felülírások: "kulcs: X (ha …) — Y csak azon kívül él"
    felteteles_felulirasok: list[str] = field(default_factory=list)
    # --- 019: kizárás és téma ---
    kizart: list[str] = field(default_factory=list)          # mit, ki zárta ki
    hatastalan_kizarasok: list[str] = field(default_factory=list)
    tema_csere: list[str] = field(default_factory=list)      # a közelebbi nyert
    tema_utkozes: list[str] = field(default_factory=list)    # azonos szinten
    # --- 020: módosított konvenció ---
    torolt: list[str] = field(default_factory=list)          # kivett alapszabályok
    # --- 028: elv-sablon ---
    elv_teruletek: list[str] = field(default_factory=list)   # hol vált ki egy elv
    # elv-sablon példányai: {kód: [{"beallitas": …, "ertekek": {param: érték}}]}
    peldanyok: dict = field(default_factory=dict)

    @property
    def figyelmeztetesek(self) -> list[str]:
        """Amit a rendszer gazdájának látnia kell (import, ellenőrzés)."""
        return ([f"TÉMA-ÜTKÖZÉS: {x}" for x in self.tema_utkozes]
                + [f"HATÁSTALAN KIZÁRÁS: {x}" for x in self.hatastalan_kizarasok])

    @property
    def tajekoztatasok(self) -> list[str]:
        return ([f"kizárva: {x}" for x in self.kizart]
                + [f"téma szerinti csere: {x}" for x in self.tema_csere]
                + [f"módosítás kihagyta: {x}" for x in self.torolt]
                + [f"elv-terület: {x}" for x in self.elv_teruletek]
                + [f"feltételes felülírás: {x}" for x in self.felteteles_felulirasok])

    @property
    def kulcsok(self) -> int:
        return len({s.kulcs for s in self.sorok})

    def kulcs_szerint(self) -> dict[str, list[Sor]]:
        ki: dict[str, list[Sor]] = defaultdict(list)
        for s in self.sorok:
            ki[s.kulcs].append(s)
        return dict(ki)


# --- Beolvasás az adatbázisból ---------------------------------------

def _rendszer_id(cur, kod: str) -> int:
    cur.execute("SELECT id FROM rendszer WHERE kod=%s", (kod,))
    r = cur.fetchone()
    if not r:
        raise FeloldasHiba(f"Nincs ilyen rendszer: {kod!r}")
    return r[0]


_ALAP_OSZLOPOK = ("id, kulcs, minta, alfejezet, prioritas, specifikussag,"
                  " feltetel, feltetel_szoveg, magyarazat, forsz,"
                  " ismeretlen_jelzok")
# A 014_kompetitiv.sql utáni oszlopok. Ha a migráció még nem futott le,
# a lekérdezés visszaesik az alapra — a motor akkor is működik, csak
# kompetitív tudás nélkül.
_UJ_OSZLOPOK = (", jelentes, ha_feltetel, ha_feltetel_szoveg, elvaras,"
                " magyarazat_en, dontesi_mod, szabaly_fajta, ag, alert,"
                " fejezet, dok_fejezet")


def _fa(x):
    if not x:
        return None
    return json.loads(x) if isinstance(x, str) else x


# Mely állapotú sorokat használ a motor?
#   éles mód:  csak az ELFOGADOTT sorokat;
#   TESZT mód: a JAVASOLT és a FELULVIZSGALANDO sorokat is — így egy
#              frissen importált rendszer jóváhagyás előtt kipróbálható.
# Az ELVETETT és a JEGELT sor egyik módban sem kerül a motorba: a JEGELT
# azt jelenti, hogy "tudunk róla, de még ne használd, teszteléskor sem".
ELES_ALLAPOTOK = ("ELFOGADOTT",)
TESZT_ALLAPOTOK = ("ELFOGADOTT", "JAVASOLT", "FELULVIZSGALANDO")


def ervenyes_allapotok(teszt: bool) -> tuple[str, ...]:
    return TESZT_ALLAPOTOK if teszt else ELES_ALLAPOTOK


def _sorok(cur, rendszer_id: int, kod: str, melyseg: int,
           allapotok: tuple[str, ...] = ELES_ALLAPOTOK) -> list[Sor]:
    helyek = ",".join(["%s"] * len(allapotok))
    alap = (f"SELECT {_ALAP_OSZLOPOK}{{extra}} FROM licitmenet"
            " WHERE rendszer_id=%s AND tipus='SZABALY'"
            f"   AND allapot IN ({helyek}) ORDER BY seq")
    arg = (rendszer_id, *allapotok)
    bovitett = True
    try:
        cur.execute(alap.format(extra=_UJ_OSZLOPOK), arg)
    except Exception:              # noqa: BLE001 — a 014 még nem futott le
        bovitett = False
        cur.execute(alap.format(extra=""), arg)

    ki = []
    for sor in cur.fetchall():
        (lid, kulcs, minta, alfej, pri, spec, feltetel, fszoveg,
         magyarazat, forsz, isms) = sor[:11]
        s = Sor(lid, rendszer_id, kod, melyseg,
                kulcs or minta or "", minta or "", alfej,
                pri or 0, spec or 0, _fa(feltetel), fszoveg, magyarazat,
                forsz or "NEM", isms)
        if bovitett:
            s.jelentes = _fa(sor[11])
            s.ha_feltetel = _fa(sor[12])
            s.ha_feltetel_szoveg = sor[13]
            s.elvaras = sor[14] or "SEMMI"
            s.magyarazat_en = sor[15]
            s.dontesi_mod = sor[16] or "SORREND"
            s.szabaly_fajta = sor[17] or "SZABALY"
            s.ag = sor[18]
            s.alert = bool(sor[19])
            s.fejezet = sor[20]
            s.forras = sor[21]
        ki.append(s)
    return ki


def _hivatkozas_beallitasok(cur, rendszer_id: int) -> dict[int, dict]:
    """Az elv-sablon példányok beállítása (028): {hivatkozott_id: beállítás}."""
    try:
        cur.execute("SELECT hivatkozott_id, hivatkozas_beallitas FROM licitmenet"
                    " WHERE rendszer_id=%s AND tipus='HIVATKOZAS'"
                    "   AND hivatkozas_aktiv=1 AND hivatkozas_beallitas IS NOT NULL",
                    (rendszer_id,))
    except Exception:              # noqa: BLE001 — a 028 még nem futott le
        return {}
    return {r[0]: _fa(r[1]) for r in cur.fetchall() if r[1]}


def _sablon(cur, kod: str) -> dict | None:
    """Az elv-sablon definíciója (028: rendszer.sablon), ha az."""
    try:
        cur.execute("SELECT sablon FROM rendszer WHERE kod=%s AND fajta='ELV_SABLON'", (kod,))
    except Exception:              # noqa: BLE001 — a 028 még nem futott le
        return None
    r = cur.fetchone()
    return _fa(r[0]) if r and r[0] else None


def _hivatkozasok(cur, rendszer_id: int) -> list[int]:
    """A beemelt (BE módú, aktív) rendszerek id-je, kártya-sorrendben."""
    alap = ("SELECT hivatkozott_id FROM licitmenet"
            " WHERE rendszer_id=%s AND tipus='HIVATKOZAS'"
            "   AND hivatkozas_aktiv=1 AND hivatkozott_id IS NOT NULL{extra}"
            " ORDER BY seq")
    try:
        cur.execute(alap.format(extra=" AND hivatkozas_mod='BE'"), (rendszer_id,))
    except Exception:              # noqa: BLE001 — a 019 még nem futott le
        cur.execute(alap.format(extra=""), (rendszer_id,))
    return [r[0] for r in cur.fetchall()]


def _kizarasok(cur, rendszer_id: int) -> list[tuple[str, str | None]]:
    """A rendszer KI módú hivatkozásai: [(kizárt kód, fejezet | None)]."""
    try:
        cur.execute(
            "SELECT r.kod, lm.kizart_fejezet FROM licitmenet lm"
            " JOIN rendszer r ON r.id = lm.hivatkozott_id"
            " WHERE lm.rendszer_id=%s AND lm.tipus='HIVATKOZAS'"
            "   AND lm.hivatkozas_aktiv=1 AND lm.hivatkozas_mod='KI'"
            " ORDER BY lm.seq", (rendszer_id,))
    except Exception:              # noqa: BLE001 — a 019 még nem futott le
        return []
    return [(r[0], r[1] or None) for r in cur.fetchall()]


def _alapja(cur, kod: str) -> str | None:
    try:
        cur.execute("SELECT alapja FROM rendszer WHERE kod=%s", (kod,))
    except Exception:              # noqa: BLE001 — a 020 még nem futott le
        return None
    r = cur.fetchone()
    return (r[0] or None) if r else None


def _tema(cur, kod: str) -> str | None:
    try:
        cur.execute("SELECT tema, fajta FROM rendszer WHERE kod=%s", (kod,))
    except Exception:              # noqa: BLE001 — a 019 még nem futott le
        return None
    r = cur.fetchone()
    return (r[0] or None) if r and r[1] == "KONVENCIO" else None


def feloldas(conn, rendszer_kod: str, max_melyseg: int = 10,
             teszt: bool = False) -> Feloldas:
    """
    A rendszer teljes szabálylistája, az öröklés feloldásával, az
    adatbázisból. `teszt=True`: a még jóvá nem hagyott (JAVASOLT,
    FELULVIZSGALANDO) sorokat is használja; a JEGELT-et akkor sem. A bejárás logikája a `feloldas_altalanos`-ban van, így
    ugyanaz fut a YAML-forrásokra is (motor/rendszercheck.py).
    """
    cur = conn.cursor()
    kod_szerint: dict[str, int] = {}

    def rid(kod: str) -> int:
        if kod not in kod_szerint:
            kod_szerint[kod] = _rendszer_id(cur, kod)
        return kod_szerint[kod]

    allapotok = ervenyes_allapotok(teszt)

    def sorok_fn(kod: str, melyseg: int) -> list[Sor]:
        return _sorok(cur, rid(kod), kod, melyseg, allapotok)

    def hivatkozasok_fn(kod: str) -> list:
        ki = []
        beall = _hivatkozas_beallitasok(cur, rid(kod))
        for hid in _hivatkozasok(cur, rid(kod)):
            cur.execute("SELECT kod FROM rendszer WHERE id=%s", (hid,))
            r = cur.fetchone()
            if r:
                kod_szerint[r[0]] = hid
                ki.append((r[0], beall[hid]) if hid in beall else r[0])
        return ki

    def sablon_fn(kod: str) -> dict | None:
        return _sablon(cur, kod)

    def kizarasok_fn(kod: str) -> list[tuple[str, str | None]]:
        return _kizarasok(cur, rid(kod))

    def tema_fn(kod: str) -> str | None:
        return _tema(cur, kod)

    def alapja_fn(kod: str) -> str | None:
        return _alapja(cur, kod)

    rid(rendszer_kod)                     # nem létező rendszer: azonnal hiba
    return feloldas_altalanos(rendszer_kod, sorok_fn, hivatkozasok_fn,
                              max_melyseg, kizarasok_fn, tema_fn, alapja_fn, sablon_fn)


def feloldas_altalanos(rendszer_kod: str, sorok_fn, hivatkozasok_fn,
                       max_melyseg: int = 10, kizarasok_fn=None,
                       tema_fn=None, alapja_fn=None, sablon_fn=None) -> Feloldas:
    """
    Szélességi bejárás a hivatkozási fán.

    ELSŐBBSÉG: egy `kulcs` azé a rendszeré, amelyik a bejárásban ELŐBB
    adta — vagyis a kisebb mélységűé, azonos mélységben pedig a
    kártyán ELŐRÉBB hivatkozotté (a HIVATKOZAS sorok `seq` sorrendje).
    Így egy konvenciókártyán a források sorrendje dönt: ha a Multi és a
    gyenge 2♦ is be van kötve, az nyer, amelyik előbb áll. Egy
    rendszeren BELÜL több sor is tartozhat egy kulcshoz (a LICREN is így
    ír két szabályt a 2S-re) — azok együtt öröklődnek és együtt
    íródnak felül.

    Az azonos mélységű felülírásokat külön is feljegyezzük
    (`Feloldas.sorrendi_felulirasok`): ezek nem hibák, de érdemes
    látni őket, mert csak a kártya sorrendje dönt bennük.

    KIZÁRÁS: `kizarasok_fn(kod) -> [(kód, fejezet|None)]` — a `kod` alatti
    fában érvényes. TÉMA: `tema_fn(kod) -> str|None` — az azonos témájú
    konvenciók közül az első érkező marad — kivéve a módosított
    konvenció saját alapját (`alapja_fn`), az mögötte tovább él.
    KIHAGYÁS (020, 031): a KIHAGYAS (régen TORLES) fajtájú sor lefoglalja a
    kulcsot, de nem kerül a szabályok közé: a mélyebb (alap) szabály így
    kiesik. Ugyanígy működik a jelzésrendszereknél (motor/jelzes.py).
    ELV-SABLON (028): a `hivatkozasok_fn` egy eleme lehet (kód, beállítás)
    pár is — a beállítás az elv-sablon példánya (érvényességi helyzet,
    paraméterek; motor/sablon.py). A `sablon_fn(kod) -> dict | None` a
    sablon definíciója (alapértékek). Ugyanaz a sablon több beállítással
    is beléphet (más-más helyen él).
    """
    from .sablon import beallitas_kulcs, ertekek, peldanyosit, terulet

    def alap_lanc(k: str) -> set[str]:
        ki: set[str] = set()
        while alapja_fn and k and k not in ki:
            k = alapja_fn(k)
            if k:
                ki.add(k)
        return ki

    eredmeny = Feloldas(rendszer_kod)
    latott: set[str] = set()
    # (kód, mélység, érvényes kizárások: {(kód, fejezet|None): ki zárta ki})
    sorban: list[tuple] = [(rendszer_kod, 0, {}, None)]
    # kulcs -> (a gazda rendszer kódja, mélysége)
    gazda: dict[str, tuple[str, int]] = {}
    gazda_ha: dict[str, list] = {}               # kulcs -> a gazda sorainak `ha`-fái
    tema_gazda: dict[str, tuple[str, int]] = {}
    hatott: set[tuple[str, tuple]] = set()      # (kizáró, kizárás) — hatott-e
    # az elv-sablonok TERÜLETEI (028): a kártyán MÖGÖTTÜK álló sorok ott nem élnek
    teruletek: list[dict] = []
    osszes_kizaras: list[tuple[str, tuple]] = []

    while sorban:
        kod, melyseg, kizart, beallitas = sorban.pop(0)
        latott_kulcs = kod if beallitas is None else f"{kod}|{beallitas_kulcs(beallitas)}"
        if latott_kulcs in latott:
            continue                      # körfigyelés / gyémánt-öröklés
        if melyseg > max_melyseg:
            raise FeloldasHiba(
                f"Túl mély hivatkozási lánc ({melyseg}): {rendszer_kod!r}")
        if (kod, None) in kizart:
            ki = kizart[(kod, None)]
            hatott.add((ki, (kod, None)))
            eredmeny.kizart.append(f"{kod} (kizárta: {ki})")
            continue                      # más úton még beléphet
        tema = tema_fn(kod) if tema_fn else None
        sajat_sorok = list(sorok_fn(kod, melyseg))
        sablon_def = sablon_fn(kod) if sablon_fn else None
        if sablon_def is not None or beallitas is not None:
            sajat_sorok = peldanyosit(sajat_sorok, sablon_def, beallitas)
        # Egy témát csak olyan konvenció foglalhat el, amelyiknek ebben a
        # módban van HASZNÁLHATÓ sora: a még jóvá nem hagyott (élesben
        # üres) új konvenció nem szoríthatja ki az elfogadott alternatívát.
        if tema and not sajat_sorok:
            tema = None
        if tema:
            tg = tema_gazda.get(tema)
            if tg is not None and tg[0] != kod and kod in alap_lanc(tg[0]):
                tg = None                 # a módosítás alapja: él mögötte
            elif tg is not None and tg[0] != kod:
                szoveg = (f"„{tema}”: {tg[0]} marad, {kod} kimarad")
                if tg[1] == melyseg:
                    eredmeny.tema_utkozes.append(
                        szoveg + " (azonos szinten — csak a sorrend döntött)")
                else:
                    eredmeny.tema_csere.append(szoveg)
                latott.add(latott_kulcs)
                continue
            else:
                tema_gazda.setdefault(tema, (kod, melyseg))
        latott.add(latott_kulcs)
        eredmeny.lanc.append((kod, melyseg))
        elotte = len(eredmeny.sorok)
        elozo_teruletek = list(teruletek)

        for s in sajat_sorok:
            fk = (kod, s.fejezet or None)
            if s.fejezet and fk in kizart:
                hatott.add((kizart[fk], fk))
                continue
            g = gazda.get(s.kulcs)
            if getattr(s, "szabaly_fajta", "") in ("KIHAGYAS", "TORLES"):
                if g is None:
                    gazda[s.kulcs] = (kod, melyseg)
                    eredmeny.torolt.append(f"{s.kulcs} ({kod})")
                continue
            if g is None:
                gazda[s.kulcs] = (kod, melyseg)
                gazda_ha[s.kulcs] = [s.ha_feltetel]
                eredmeny.sorok.append(s)
            elif g[0] == kod:
                eredmeny.sorok.append(s)  # ugyanaz a rendszer: csoport
                gazda_ha.setdefault(s.kulcs, []).append(s.ha_feltetel)
            elif gazda_ha.get(s.kulcs) and all(gazda_ha[s.kulcs]):
                # a felülíró csak bizonyos helyzetben él: azon kívül ez
                s.elnyomo = list(gazda_ha[s.kulcs])
                eredmeny.sorok.append(s)
                szoveg = (f"{s.kulcs}: {g[0]} csak a saját helyzetében írja "
                          f"felül ezt: {kod}")
                if szoveg not in eredmeny.felteteles_felulirasok:
                    eredmeny.felteteles_felulirasok.append(szoveg)
            else:
                eredmeny.felulirt[s.kulcs] = eredmeny.felulirt.get(s.kulcs, 0) + 1
                if g[1] == melyseg:
                    eredmeny.sorrendi_felulirasok.append(
                        f"{s.kulcs}: {g[0]} (előrébb a kártyán) felülírja "
                        f"ezt: {kod}")

        if elozo_teruletek:
            for s in eredmeny.sorok[elotte:]:
                s.elnyomo = list(s.elnyomo or []) + elozo_teruletek
        if sablon_def is not None:
            eredmeny.peldanyok.setdefault(kod, []).append(
                {"beallitas": beallitas or {}, "ertekek": ertekek(sablon_def, beallitas)})
            t_ = terulet(sablon_def, beallitas)
            if t_ is not None:
                teruletek.append(t_)
                eredmeny.elv_teruletek.append(
                    f"{kod}" + (f" ({' / '.join((beallitas or {}).get('ervenyes') or [])} után)"
                                if (beallitas or {}).get("ervenyes") else "")
                    + " — a kártyán mögötte álló sorok ott nem élnek")

        sajat = list(kizarasok_fn(kod)) if kizarasok_fn else []
        gyerek_kizart = dict(kizart)
        for k in sajat:
            k = (k[0], k[1] or None)
            gyerek_kizart.setdefault(k, kod)
            osszes_kizaras.append((kod, k))
        for h in hivatkozasok_fn(kod):
            if isinstance(h, tuple):
                sorban.append((h[0], melyseg + 1, gyerek_kizart, h[1]))
            else:
                sorban.append((h, melyseg + 1, gyerek_kizart, None))

    for ki, (k, fej) in osszes_kizaras:
        if (ki, (k, fej)) not in hatott:
            eredmeny.hatastalan_kizarasok.append(
                f"{ki}: {k}" + (f" / „{fej}”" if fej else "")
                + " — nincs ilyen a hivatkozott fában")
    for k, fej in {(k, f) for _, (k, f) in osszes_kizaras if f}:
        n = 0
        for (ki, kk) in hatott:
            if kk == (k, fej):
                n += 1
        if n:
            eredmeny.kizart.append(f"{k} / „{fej}” fejezet")

    eredmeny.kizart = list(dict.fromkeys(eredmeny.kizart))
    _utkozes_ellenorzes(eredmeny)
    return eredmeny


def _utkozes_ellenorzes(f: Feloldas) -> None:
    """
    Azonos kulcs + azonos prioritás + azonos specifikusság = kétértelmű.
    Ilyenkor nem dönthető el, melyik szabály nyer.
    """
    csoport: dict[tuple, list[Sor]] = defaultdict(list)
    for s in f.sorok:
        csoport[(s.kulcs, s.prioritas, s.specifikussag)].append(s)
    for (kulcs, pri, spec), sorok in csoport.items():
        if len(sorok) > 1 and len({s.licitmenet_id for s in sorok}) > 1:
            # több sor azonos kulcson: csak akkor baj, ha a feltételük is
            # ütközhet — ezt a licitmotor futásidőben dönti el
            f.utkozes.append(
                f"{kulcs}: {len(sorok)} sor azonos prioritással ({pri}) "
                f"és specifikussággal ({spec})")


# --- Kiírás az adatbázisba -------------------------------------------

def ment(conn, f: Feloldas) -> int:
    """A feloldás eredményének mentése a `feloldott_licitmenet` táblába."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM rendszer WHERE kod=%s", (f.rendszer_kod,))
    rid = cur.fetchone()[0]
    cur.execute("DELETE FROM feloldott_licitmenet WHERE rendszer_id=%s", (rid,))

    # kulcsonként a GYŐZTES sor (a legkisebb mélység, azon belül a
    # legmagasabb prioritás) kerül be, a felülírt darabszámmal
    legjobb: dict[str, Sor] = {}
    for s in f.sorok:
        elozo = legjobb.get(s.kulcs)
        if elozo is None or (s.melyseg, -s.prioritas) < (elozo.melyseg,
                                                         -elozo.prioritas):
            legjobb[s.kulcs] = s

    sorok = [(rid, s.kulcs, s.licitmenet_id, s.rendszer_id, s.melyseg,
              min(255, f.felulirt.get(s.kulcs, 0)))
             for s in legjobb.values()]
    if sorok:
        cur.executemany(
            "INSERT INTO feloldott_licitmenet"
            " (rendszer_id, kulcs, licitmenet_id, eredet_rendszer, melyseg,"
            "  felulirt_db) VALUES (%s,%s,%s,%s,%s,%s)", sorok)
    conn.commit()
    return len(sorok)
