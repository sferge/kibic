"""
A RENDSZER TELJES LEÍRÁSA ember által olvasható alakban (HTML / Markdown).

A kártya (`/v1/kibic/kartya`) a RÖVID változat: a WBF-kártya mezői
összefoglalva. Ez itt a HOSSZÚ: a feloldott rendszer MINDEN szabálya —
pontosan azok, amelyekkel a kibic licitál —, a forrás (alaprendszer vagy
konvenció) és azon belül a fejezet szerint, a fejezetek és a konvenciók
jegyzeteivel. Nyomtatható (a böngészőből PDF-be is).

    GET /v1/kibic/leiras?system=MOHA_STAND&format=html|md
    python -m kibic.cli.rendszerleiras --rendszer MOHA_STAND --ki moha.html

Kéz nincs benne, csak a megállapodás.
"""
from __future__ import annotations

import datetime as _dt
import html as _html

from ..motor.kartya import szep

FORSZ_NEV = {"GEMFORSZ": "GF", "EGY_MENET": "F1", "SZLEMFORSZ": "szlemforsz",
             "KIZARO": "kizáró"}


def _sor_adat(s) -> dict:
    kulcs = s.kulcs or ""
    return {
        "licit": szep(s.minta or ""),
        "minta": s.minta or "",
        "jelentes": (s.magyarazat or "").strip(),
        "feltetel": (s.feltetel_szoveg or "").strip(),
        "helyzet": (getattr(s, "ha_feltetel_szoveg", None) or "").strip(),
        "alert": bool(getattr(s, "alert", False)),
        "forsz": FORSZ_NEV.get(s.forsz or "", ""),
        "elv": getattr(s, "szabaly_fajta", "SZABALY") == "ELV",
        "lehetoseg": "~" in kulcs,
        "merlegelo": getattr(s, "dontesi_mod", "") == "MERLEGELO",
    }


def _sz(v):
    return "igen" if v is True else "nem" if v is False else v


def _sablon_adat(sb: dict | None, peldanyok: list[dict] | None) -> dict | None:
    """Egy elv-sablon a leíráshoz: a szöveg, a paraméterek, és hol él."""
    if not sb:
        return None
    pars = sb.get("parameterek") or {}
    hol, ertek = [], {}
    for p in peldanyok or []:
        b = p.get("beallitas") or {}
        hol.append(" / ".join(b.get("ervenyes") or []) or "mindenhol")
        if b.get("kivalt") is False:
            hol[-1] += " (nem váltja ki a mögötte álló sorokat)"
        ertek = p.get("ertekek") or ertek
    szoveg = sb.get("szoveg")
    if szoveg:                          # a {PARAMÉTER} helyén az érték (a példányé, vagy az alap)
        for k, v in pars.items():
            szoveg = szoveg.replace("{" + k + "}", str(_sz(ertek.get(k, v.get("alap")))))
    return {"szoveg": szoveg, "hol": hol,
            "terulet": sb.get("terulet_szoveg"),
            "parameterek": [{"kod": k, "leiras": v.get("leiras"), "alap": _sz(v.get("alap")),
                             "ertek": _sz(ertek.get(k, v.get("alap"))),
                             "tartomany": v.get("tartomany")} for k, v in pars.items()]}


def leiras_adat(rendszer: dict, lanc: list[dict], sorok, teszt: bool = True,
                peldanyok: dict | None = None) -> dict:
    """
    `rendszer`: {kod, nev, leiras, jegyzet}; `lanc`: a kártya sorrendjében a
    források {kod, nev, leiras, tema, jegyzet, fejezet_jegyzetek, fajta};
    `sorok`: a feloldott szabályok.
    """
    from .szerkeszto import menet_kulcs, osszevont_nyitasok
    osz = osszevont_nyitasok(s.minta or "" for s in sorok)
    forrasonkent: dict[str, dict[str, list]] = {}
    for s in sorok:
        fej = s.fejezet or "Egyéb"
        forrasonkent.setdefault(s.rendszer_kod, {}).setdefault(fej, []).append(s)
    reszek = []
    for f in lanc:
        fejezetek = forrasonkent.get(f["kod"])
        if not fejezetek:
            continue
        fj = f.get("fejezet_jegyzetek") or {}
        reszek.append({
            "kod": f["kod"], "nev": f.get("nev") or f["kod"], "leiras": f.get("leiras"),
            "tema": f.get("tema"), "jegyzet": f.get("jegyzet"), "fajta": f.get("fajta"),
            "sablon": _sablon_adat(f.get("sablon"), (peldanyok or {}).get(f["kod"])),
            "fejezetek": [{
                "cim": cim, "jegyzet": fj.get(cim),
                "szabalyok": [_sor_adat(s) for s in sorted(
                    lista, key=lambda s: (menet_kulcs(s.minta or "", osz), s.minta or "",
                                          -(s.prioritas or 0)))],
            } for cim, lista in fejezetek.items()],
        })
    return {"rendszer": rendszer, "reszek": reszek, "osszesen": len(sorok),
            "teszt": teszt,
            "keszult": _dt.datetime.now().isoformat(timespec="minutes")}


# --- forrásból -----------------------------------------------------------

def leiras_yamlbol(forrasok: dict, kod: str) -> dict:
    from ..motor.rendszercheck import feloldas_forrasokbol
    f, _ = feloldas_forrasokbol(forrasok, kod)
    gy = forrasok[kod]

    def adat(k):
        r = forrasok.get(k)
        if r is None:
            return {"kod": k}
        return {"kod": k, "nev": r.nev, "leiras": r.leiras, "tema": getattr(r, "tema", None),
                "jegyzet": getattr(r, "jegyzet", None), "fajta": r.fajta,
                "fejezet_jegyzetek": getattr(r, "fejezet_jegyzetek", None) or {},
                "sablon": getattr(r, "sablon", None) or None}
    return leiras_adat({"kod": kod, "nev": gy.nev, "leiras": gy.leiras,
                        "jegyzet": getattr(gy, "jegyzet", None)},
                       [adat(k) for k, _ in dict.fromkeys(f.lanc)], f.sorok, teszt=True,
                       peldanyok=f.peldanyok)


def leiras_db(conn, kod: str, teszt: bool = True) -> dict:
    import json
    from ..motor.feloldas import feloldas
    f = feloldas(conn, kod, teszt=teszt)
    kodok = [k for k, _ in f.lanc]
    cur = conn.cursor()
    helyek = ",".join(["%s"] * len(kodok))
    try:
        cur.execute(f"SELECT kod, nev, leiras, fajta, jegyzet, fejezet_jegyzetek"
                    f" FROM rendszer WHERE kod IN ({helyek})", kodok)
    except Exception:              # noqa: BLE001 — a 022 még nem futott le
        cur.execute(f"SELECT kod, nev, leiras, fajta, NULL, NULL"
                    f" FROM rendszer WHERE kod IN ({helyek})", kodok)
    adatok = {}
    for k, nev, leiras, fajta, jegyzet, fj in cur.fetchall():
        if isinstance(fj, (str, bytes)):
            try:
                fj = json.loads(fj)
            except ValueError:
                fj = {}
        adatok[k] = {"kod": k, "nev": nev, "leiras": leiras, "fajta": fajta,
                     "jegyzet": jegyzet, "fejezet_jegyzetek": fj or {}}
    try:                           # 028: az elv-sablonok
        cur.execute(f"SELECT kod, sablon FROM rendszer WHERE kod IN ({helyek})"
                    f" AND sablon IS NOT NULL", kodok)
        for k, sb in cur.fetchall():
            if isinstance(sb, (str, bytes)):
                sb = json.loads(sb)
            if k in adatok and sb:
                adatok[k]["sablon"] = sb
    except Exception:              # noqa: BLE001 — a 028 még nem futott le
        pass
    gy = adatok.get(kod, {"kod": kod, "nev": kod})
    return leiras_adat({"kod": kod, "nev": gy.get("nev"), "leiras": gy.get("leiras"),
                        "jegyzet": gy.get("jegyzet")},
                       [adatok.get(k, {"kod": k}) for k in dict.fromkeys(kodok)], f.sorok, teszt,
                       peldanyok=f.peldanyok)


# --- megjelenítés ---------------------------------------------------------

def _e(x) -> str:
    return _html.escape(str(x or ""))


def _piros(s: str) -> str:
    return s.replace("♥", '<span class="p">♥</span>').replace("♦", '<span class="p">♦</span>')


def _jelzok(r: dict) -> list[str]:
    j = []
    if r["alert"]:
        j.append("alert")
    if r["forsz"]:
        j.append(r["forsz"])
    if r["elv"]:
        j.append("elv")
    if r["lehetoseg"]:
        j.append("lehetőség")
    if r["merlegelo"]:
        j.append("mérlegelő")
    return j


def leiras_html(adat: dict) -> str:
    r = adat["rendszer"]
    tart = []
    for i, f in enumerate(adat["reszek"]):
        tart.append(f'<li><a href="#r{i}">{_e(f["nev"])}</a> '
                    f'<span class="k">({sum(len(c["szabalyok"]) for c in f["fejezetek"])})</span></li>')
    test = []
    for i, f in enumerate(adat["reszek"]):
        test.append(f'<section id="r{i}"><h2>{_e(f["nev"])} <span class="k">{_e(f["kod"])}</span></h2>')
        if f.get("leiras"):
            test.append(f'<p class="le">{_piros(_e(f["leiras"]))}</p>')
        if f.get("jegyzet"):
            test.append(f'<p class="jegyzet">{_piros(_e(f["jegyzet"]))}</p>')
        sb = f.get("sablon")
        if sb:
            test.append('<div class="elv"><b>Az elv</b> (a szerkesztő szavai alapján):'
                        f'<p>{_piros(_e(sb["szoveg"]))}</p>')
            if sb["hol"]:
                test.append(f'<p><b>Hol él:</b> {_piros(_e("; ".join(sb["hol"])))}'
                            + (f' — ott a kártyán mögötte álló sorok nem élnek '
                               f'(terület: {_e(sb["terulet"])})' if sb.get("terulet") else "")
                            + '</p>')
            if sb["parameterek"]:
                test.append('<p><b>Paraméterek:</b></p><ul>' + "".join(
                    f'<li><code>{_e(p["kod"])}</code> = <b>{_e(p["ertek"])}</b>'
                    + (f' (alap: {_e(p["alap"])})' if p["ertek"] != p["alap"] else "")
                    + (f' — {_e(p["leiras"])}' if p.get("leiras") else "") + '</li>'
                    for p in sb["parameterek"]) + '</ul>')
            test.append('</div>')
        for c in f["fejezetek"]:
            test.append(f'<h3>{_piros(_e(c["cim"]))}</h3>')
            if c.get("jegyzet"):
                test.append(f'<p class="jegyzet">{_piros(_e(c["jegyzet"]))}</p>')
            test.append('<table><tr><th>Licit</th><th>Jelentés</th><th>Feltétel (a lap)</th><th></th></tr>')
            for s in c["szabalyok"]:
                test.append(f'<tr><td class="l">{_piros(_e(s["licit"]))}</td>'
                            f'<td>{_piros(_e(s["jelentes"] or "—"))}'
                            + (f' <span class="k">[helyzet: {_e(s["helyzet"])}]</span>' if s["helyzet"] else "")
                            + f'</td><td class="f">{_piros(_e(s["feltetel"]))}</td>'
                            f'<td class="j">{_e(" · ".join(_jelzok(s)))}</td></tr>')
            test.append("</table>")
        test.append("</section>")
    teszt = (" — <b>teszt mód</b>: a jóvá nem hagyott (javasolt) sorok is benne vannak"
             if adat.get("teszt") else " — csak az elfogadott sorok")
    return f"""<!doctype html><html lang="hu"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(r.get('nev') or r['kod'])} — teljes leírás</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:24px;color:#1b1b1b;max-width:1200px}}
h1{{margin:0 0 4px}} h2{{margin-top:32px;border-bottom:2px solid #333;padding-bottom:3px}}
h3{{margin:18px 0 6px;color:#333}}
.k{{color:#777;font-size:12px;font-weight:normal}} .p{{color:#c00}}
.elv{{background:#eef4fb;border-left:3px solid #4a7ab8;padding:6px 10px;font-size:13px;margin:6px 0}}
.elv p{{margin:4px 0}} .le{{margin:4px 0}} .jegyzet{{background:#f6f6f0;border-left:3px solid #bba;padding:6px 10px;
  font-size:13px;white-space:pre-wrap;margin:6px 0}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin-bottom:8px}}
th,td{{border-bottom:1px solid #ddd;padding:3px 6px;text-align:left;vertical-align:top}}
th{{background:#eee}} td.l{{white-space:nowrap;font-weight:600}}
td.f{{color:#555;font-size:12px}} td.j{{color:#555;font-size:11px;white-space:nowrap}}
ul.tart{{columns:3;font-size:13px}}
@media print{{body{{margin:8mm}} h2{{break-before:auto}} tr{{break-inside:avoid}}}}
</style></head><body>
<h1>{_e(r.get('nev') or r['kod'])} <span class="k">{_e(r['kod'])}</span></h1>
<p>{_piros(_e(r.get('leiras')))}</p>
{f'<p class="jegyzet">{_piros(_e(r.get("jegyzet")))}</p>' if r.get('jegyzet') else ''}
<p class="k">{adat['osszesen']} szabály, a kibic feloldása szerint (ezekkel licitál){teszt}.
Készült: {_e(adat['keszult'])}. A rövid változat a kártya: /v1/kibic/kartya?system={_e(r['kod'])}.
Jelölések: alert · GF = gémforsz · F1 = egy körre kényszerít · elv = helyzeti elv (bármely menetben,
ha nincs konkrétabb; a „..” = bármely licitmenet; M/m = nemes/minor, oM = a másik nemes,
A/B = színváltozó; + = a legolcsóbb licit a színben) · lehetőség = a zárójeles érték (pl. rossz 11) · mérlegelő = a szimuláció dönt.</p>
<h2>Tartalom</h2><ul class="tart">{''.join(tart)}</ul>
{''.join(test)}
</body></html>"""


def leiras_md(adat: dict) -> str:
    r = adat["rendszer"]
    ki = [f"# {r.get('nev') or r['kod']} ({r['kod']}) — teljes leírás", ""]
    if r.get("leiras"):
        ki += [r["leiras"], ""]
    if r.get("jegyzet"):
        ki += [f"> {r['jegyzet']}", ""]
    ki += [f"*{adat['osszesen']} szabály, a kibic feloldása szerint"
           + ("; teszt mód: a javasolt sorok is" if adat.get("teszt") else "")
           + f". Készült: {adat['keszult']}.*", ""]
    for f in adat["reszek"]:
        ki += [f"## {f['nev']} ({f['kod']})", ""]
        if f.get("leiras"):
            ki += [f["leiras"], ""]
        if f.get("jegyzet"):
            ki += [f"> {f['jegyzet']}", ""]
        sb = f.get("sablon")
        if sb:
            ki += [f"**Az elv** (a szerkesztő szavai alapján): {sb['szoveg']}", ""]
            if sb["hol"]:
                ki += [f"**Hol él:** {'; '.join(sb['hol'])}"
                       + (f" — ott a kártyán mögötte álló sorok nem élnek (terület: {sb['terulet']})"
                          if sb.get("terulet") else ""), ""]
            for p in sb["parameterek"]:
                ki.append(f"- `{p['kod']}` = **{p['ertek']}**"
                          + (f" (alap: {p['alap']})" if p["ertek"] != p["alap"] else "")
                          + (f" — {p['leiras']}" if p.get("leiras") else ""))
            if sb["parameterek"]:
                ki.append("")
        for c in f["fejezetek"]:
            ki += [f"### {c['cim']}", ""]
            if c.get("jegyzet"):
                ki += [f"> {c['jegyzet']}", ""]
            ki += ["| Licit | Jelentés | Feltétel (a lap) | |", "|---|---|---|---|"]
            for s in c["szabalyok"]:
                jel = s["jelentes"] or "—"
                if s["helyzet"]:
                    jel += f" [helyzet: {s['helyzet']}]"
                cella = lambda x: (x or "").replace("|", "\\|").replace("\n", " ")  # noqa: E731
                ki.append(f"| **{cella(s['licit'])}** | {cella(jel)} | {cella(s['feltetel'])} "
                          f"| {cella(' · '.join(_jelzok(s)))} |")
            ki.append("")
    return "\n".join(ki)
