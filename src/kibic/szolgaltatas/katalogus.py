"""
A RENDSZEREK KATALÓGUSA (2026-10-02): RENDSZERCSALÁD → ALAPRENDSZER → RENDSZER.

    RENDSZERCSALÁD   egy rendszercsalád általános rendszere (NATURAL,
                     STRONG_CLUB, ACOL, POLISH …) — ismeretlen pár
                     licitjeinek értéséhez
    ALAPRENDSZER     emberi forrásból (klubstandard, SAYC, Precision …),
                     egy családba tartozik
    RENDSZER         amit egy pár játszik: PONTOSAN EGY alaprendszer +
                     konvenciók; a családja az alaprendszeréé

A `GET /v1/bridge/systems` (MohaBridzs: választólisták a játékosoknak) és
a szerkesztő ugyanebből dolgozik. Tiszta függvények: az adatbázis-olvasás
a `katalogus_db`-ben, a többi tesztelhető kapcsolat nélkül.
"""
from __future__ import annotations


def alaprendszer_terkep(fajtak: dict[str, str],
                        hivatkozasok: list[tuple[str, str, bool]]) -> dict[str, list[str]]:
    """
    RENDSZER kód -> az alaprendszerei (aktív hivatkozásokon át, RENDSZER /
    GYUJTEMENY közvetítésével; konvención át nem). `hivatkozasok`:
    [(hivatkozó, hivatkozott, aktív)], csak a beemelések (a kizárás nem).
    """
    gyerekek: dict[str, list[str]] = {}
    for ki, kit, aktiv in hivatkozasok:
        if aktiv:
            gyerekek.setdefault(ki, []).append(kit)

    def alapok(kod: str) -> list[str]:
        ki: list[str] = []
        latott: set[str] = set()
        sor = [kod]
        while sor:
            k = sor.pop(0)
            if k in latott:
                continue
            latott.add(k)
            for c in gyerekek.get(k, []):
                f = fajtak.get(c)
                if f == "ALAPRENDSZER" and c not in ki:
                    ki.append(c)
                elif f in ("RENDSZER", "GYUJTEMENY"):
                    sor.append(c)
        return ki

    return {k: alapok(k) for k, f in fajtak.items() if f == "RENDSZER"}


def katalogus(rendszerek: list[dict], hivatkozasok: list[tuple[str, str, bool]],
              kartyas: set[str] | None = None,
              alap: str | None = None) -> dict:
    """
    `rendszerek`: [{code, kind, family, name, name_en, description, version}]
    — csak RENDSZERCSALAD / ALAPRENDSZER / RENDSZER kell belőle.
    `kartyas`: a kínált (kártyás) rendszerek kódjai — ezekkel tud a kibic
    játszani; ellenfélként bármelyik kód (és bármelyik család) megadható.
    """
    kartyas = {k.upper() for k in (kartyas or set())}
    fajtak = {r["code"]: r.get("kind") for r in rendszerek}
    alapok = alaprendszer_terkep(fajtak, hivatkozasok)
    adat = {r["code"]: r for r in rendszerek}

    def kozos(r: dict) -> dict:
        ki = {"code": r["code"], "name": r.get("name"), "name_en": r.get("name_en"),
              "description": r.get("description")}
        if r.get("version"):
            ki["version"] = r["version"]
        return ki

    rendszer_lista = []
    for kod in sorted(k for k, f in fajtak.items() if f == "RENDSZER"):
        r = adat[kod]
        a = alapok.get(kod) or []
        e = dict(kozos(r), family=r.get("family"), base_system=a[0] if len(a) == 1 else None,
                 has_card=kod in kartyas, playable=kod in kartyas)
        if len(a) != 1:
            e["problem"] = ("nincs alaprendszere" if not a else
                            "több alaprendszere van: " + ", ".join(a))
        elif adat.get(a[0], {}).get("family") != r.get("family"):
            e["problem"] = "a családja nem egyezik az alaprendszeréével"
        rendszer_lista.append(e)

    alap_lista = []
    for kod in sorted(k for k, f in fajtak.items() if f == "ALAPRENDSZER"):
        r = adat[kod]
        alap_lista.append(dict(kozos(r), family=r.get("family"),
                               systems=[s["code"] for s in rendszer_lista
                                        if s["base_system"] == kod],
                               has_card=kod in kartyas))

    csalad_lista = []
    csalad_kodok = {k for k, f in fajtak.items() if f == "RENDSZERCSALAD"}
    for kod in sorted(csalad_kodok | {a.get("family") for a in alap_lista if a.get("family")}):
        r = adat.get(kod) or {"code": kod}
        csalad_lista.append(dict(kozos(r), generic_system=kod in csalad_kodok,
                                 base_systems=[a["code"] for a in alap_lista
                                               if a.get("family") == kod]))

    ki = {"families": csalad_lista, "base_systems": alap_lista, "systems": rendszer_lista}
    if alap:
        ki["default_system"] = alap
    return ki


def katalogus_db(conn, kartyas: set[str] | None = None, alap: str | None = None) -> dict:
    """A katalógus az adatbázisból (rendszer + HIVATKOZAS sorok)."""
    cur = conn.cursor()
    cur.execute("SELECT kod, fajta, csalad, nev, nev_en, leiras, verzio FROM rendszer"
                " WHERE aktiv = 1 AND fajta IN ('RENDSZERCSALAD', 'ALAPRENDSZER', 'RENDSZER',"
                " 'GYUJTEMENY')")
    sorok = [{"code": str(r[0]).upper(), "kind": r[1], "family": r[2], "name": r[3],
              "name_en": r[4], "description": r[5], "version": r[6]}
             for r in cur.fetchall()]
    try:
        cur.execute("SELECT r.kod, c.kod, lm.hivatkozas_aktiv FROM licitmenet lm"
                    " JOIN rendszer r ON r.id = lm.rendszer_id"
                    " JOIN rendszer c ON c.id = lm.hivatkozott_id"
                    " WHERE lm.tipus = 'HIVATKOZAS' AND lm.hivatkozas_mod = 'BE'"
                    " AND COALESCE(lm.fejezet, '') <> 'Alapja'")
    except Exception:              # noqa: BLE001 — a 019 előtt nincs hivatkozas_mod
        cur.execute("SELECT r.kod, c.kod, lm.hivatkozas_aktiv FROM licitmenet lm"
                    " JOIN rendszer r ON r.id = lm.rendszer_id"
                    " JOIN rendszer c ON c.id = lm.hivatkozott_id"
                    " WHERE lm.tipus = 'HIVATKOZAS'")
    hiv = [(str(a).upper(), str(b).upper(), bool(c)) for a, b, c in cur.fetchall()]
    return katalogus(sorok, hiv, kartyas, alap)
