"""
PODI-PORI és DOPI-ROPI generátor (a szerkesztő, 2026-11-11).

    python eszkozok/lepcsos_kozbeszolas.py        # -> konvenciok/podi.yaml, dopi.yaml

A meglévő konvenciók LÉPCSŐS válaszaiból (ahol a licit lépcsőszáma hordozza
az információt: kulcslap- és ászválaszok) és a RELÉ-kérdésekből (ahol a relé
szintje a kérdés, nem a szín) állítja elő a közbeszólás utáni változatot:

  PODI-PORI   1. lépcső passz, 2. lépcső kontra (kontrára rekontra),
              3. lépcső az első szabad licit (L1), 4. lépcső L2 ...
  DOPI-ROPI   ugyanez, az 1. és a 2. lépcső felcserélve.

RELÉ-helyzet (a YAML-sor `rele: n` kulcsa; a relé sorszáma hordozza a
kérdést, nem a licit színe), közbeszólás után:
  PODI: 1. relé = passz, n. relé = az (n-1). szabad licit, kontra = büntető;
  DOPI: 1. relé = kontra, passz = forszírozó passz.
A relé-passz (PODI) után a válaszoló nem passzolhat (az a közbeszólás
szerződése volna): kontra = 1. lépcső, utána az első szabad licit = 2. lépcső.
A DOPI relé-kontrája után: az első szabad licit = 1. lépcső.

A leállás (pl. 4NT, 5m a spirálban) NEM lépcső: azt a generátor nem érinti.
A spirál (motor/spiral.py) ugyanezt a kódban követi.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

GYOKER = Path(__file__).resolve().parent.parent
KONV = GYOKER / "rendszerek" / "yaml" / "konvenciok"
FORRASOK = ["rkc.yaml", "moha_3nt_4m.yaml", "gerber.yaml", "moha_jacoby.yaml",
            "moha_szlem.yaml"]

DENOM = ["C", "D", "H", "S", "NT"]
SZIMB = {"C": "♣", "D": "♦", "H": "♥", "S": "♠", "NT": "NT"}


def rang(lic: str) -> int | None:
    m = re.fullmatch(r"([1-7])(C|D|H|S|NT|N)", lic)
    if not m:
        return None
    d = "NT" if m.group(2) in ("N", "NT") else m.group(2)
    return (int(m.group(1)) - 1) * 5 + DENOM.index(d)


def licit(r: int) -> str:
    return f"{r // 5 + 1}{DENOM[r % 5]}"


def szep(lic: str) -> str:
    if lic in ("X", "XX", "P"):
        return {"X": "kontra", "XX": "rekontra", "P": "passz"}[lic]
    return lic[0] + SZIMB[lic[1:]]


def tokenek(minta: str) -> tuple[bool, list[str]]:
    """(van-e kezdő '..', a MI licitjeink sorban)."""
    if "-" in minta and " " not in minta:
        return False, minta.split("-")
    t = minta.split()
    if t and t[0] == "..":
        return True, t[1:]
    return False, t


def kompetitiv(eleje: bool, mi: list[str]) -> str:
    """A mi licitjeink közé az ellenfél passzai: '.. 4C (P) 4D'."""
    return (".. " if eleje else "") + " (P) ".join(mi)


def lepcsos_sor(s: dict) -> bool:
    if "kulcslapok" in s or "aszok" in s:
        return True
    if isinstance(s.get("jelentes"), dict) and "kulcslap" in s["jelentes"]:
        return True
    return any(isinstance(v, dict) and "aszok" in v for v in s.get("vagy") or [])


def rele_sor(s: dict) -> int:
    """A relé sorszáma (a YAML `rele:` kulcsa), vagy 0."""
    try:
        return int(s.get("rele") or 0)
    except (TypeError, ValueError):
        return 0


def betolt():
    sorok = []
    for f in FORRASOK:
        p = KONV / f
        if not p.exists():
            continue
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        for fej in d.get("fejezetek") or []:
            for s in fej.get("szabalyok") or []:
                if isinstance(s, dict) and "minta" in s:
                    sorok.append((d["rendszer"]["kod"], s))
    return sorok


def csoportok(sorok):
    """{(eleje, előtag-licitek): [sor, ...]} — a lépcsős válaszcsoportok."""
    cs: dict[tuple, list] = {}
    for kod, s in sorok:
        eleje, mi = tokenek(str(s["minta"]))
        if len(mi) < 2 or mi[-1] in ("P", "X", "XX") or rang(mi[-1]) is None:
            continue
        cs.setdefault((eleje, tuple(mi[:-1])), []).append(s)
    jo = {}
    for k, ss in cs.items():
        if sum(lepcsos_sor(s) for s in ss) < 3:
            continue
        kerdes = rang(k[1][-1])
        hivasok = sorted({rang(tokenek(str(s["minta"]))[1][-1]) for s in ss})
        if kerdes is None or hivasok[0] != kerdes + 1 or hivasok != list(range(hivasok[0], hivasok[-1] + 1)):
            continue                       # nem egymást követő lépcsők
        jo[k] = [s for s in ss if lepcsos_sor(s) or "etszik" in str(s.get("alert", ""))]
    return jo


def lepcso_hivas(k: int, kozbe: str, alap: int, mod: str) -> str | None:
    """A k-adik (1-től) lépcső hívása a `kozbe` közbeszólás után.
    alap: a kérdés rangja (a kontrás esetben az L1 innen indul)."""
    if mod == "PODI":
        elso, masodik = "P", ("XX" if kozbe == "X" else "X")
    else:
        elso, masodik = ("XX" if kozbe == "X" else "X"), "P"
    if k == 1:
        return elso
    if k == 2:
        return masodik
    tol = alap if kozbe == "X" else rang(kozbe)
    r = tol + (k - 2)
    return licit(r) if r < 35 else None


def kozbeszolasok(kerdes: int, utolso: int) -> list[str]:
    return ["X"] + [licit(r) for r in range(kerdes + 1, min(utolso, 34) + 1)]


def sor_masol(s: dict, minta: str, kulcs: str, alert_elo: str) -> dict:
    u = {k: v for k, v in s.items() if k not in ("minta", "kulcs", "kivalt", "nyers", "folytatas")}
    u.pop("fajta", None)                  # pontos minta: SZABÁLY (az elvek elé)
    u = {"minta": minta, "kulcs": kulcs, **u}
    if not (set(u) & KEZ_FELTETEL):
        u["pont"] = "0+"                  # a szabálynak kéz-feltétel kell
    for mezo in ("alert", "magyarazat"):
        if isinstance(u.get(mezo), str):
            u[mezo] = f"{alert_elo}: {u[mezo]}"
    if "alert" not in u and "magyarazat" not in u:
        u["alert"] = alert_elo
    return u


KEZ_FELTETEL = {"pont", "hossz", "kulcslapok", "aszok", "vagy", "adu_dama", "kontroll",
                "fohonor", "vesztok", "gyorsutes", "elosztas", "osszesen"}


def kulcs_alap(s: dict) -> str:
    return str(s.get("kulcs") or re.sub(r"[^A-Z0-9]+", "-", str(s["minta"]).upper()).strip("-"))


def general(mod: str) -> list[tuple[str, list[dict]]]:
    sorok = betolt()
    cs = csoportok(sorok)
    fejezetek = []
    # 1) a lépcsős válaszok a közbeszólás után
    valaszok = []
    for (eleje, elo), ss in sorted(cs.items()):
        kerdes = rang(elo[-1])
        hivasok = sorted({rang(tokenek(str(s["minta"]))[1][-1]) for s in ss})
        for kb in kozbeszolasok(kerdes, hivasok[-1]):
            for s in ss:
                k = rang(tokenek(str(s["minta"]))[1][-1]) - kerdes
                h = lepcso_hivas(k, kb, kerdes, mod)
                if h is None:
                    continue
                minta = kompetitiv(eleje, list(elo)) + f" ({kb}) {h}"
                valaszok.append(sor_masol(
                    s, minta, f"{kulcs_alap(s)}-{mod}-{kb}",
                    f"{mod} ({szep(kb)} után, {k}. lépcső)"))
    fejezetek.append((f"Lépcsős válasz a közbeszólás után ({mod})", valaszok))

    # 2) RELÉ-helyzet (`rele: n`): a partner licitje után közbeszólás — a relé
    # a sorszámától függ (nem attól, mire szóltak közbe): PODI: 1. relé =
    # passz, n. relé = az (n-1). szabad licit, kontra = büntető; DOPI: 1. relé
    # = kontra, passz = forszírozó. Utána a relé válaszai lépcsőkben.
    rele, relevalasz = [], []
    for kod, s in sorok:
        n = rele_sor(s)
        if not n:
            continue
        eleje, mi = tokenek(str(s["minta"]))
        if len(mi) < 2 or rang(mi[-2]) is None:
            continue
        elo, r = mi[:-1], mi[-1]
        vcs = cs.get((eleje, tuple(mi)), [])
        for kb in ["X"] + [licit(x) for x in range(rang(elo[-1]) + 1, min(rang(r) + 3, 34) + 1)]:
            alap = kompetitiv(eleje, list(elo)) + f" ({kb})"
            elso = "P" if mod == "PODI" else ("XX" if kb == "X" else "X")
            if n == 1:
                rh = elso
            else:
                rr = (rang(elo[-1]) if kb == "X" else rang(kb)) + (n - 1)
                if rr >= 35:
                    continue
                rh = licit(rr)
            rele.append(sor_masol(s, f"{alap} {rh}", f"{kulcs_alap(s)}-{mod}-{kb}",
                                  f"{mod} ({szep(kb)} után): {szep(rh)} = {n}. relé"))
            if n == 1 and mod == "PODI" and kb != "X":
                rele.append({"minta": f"{alap} X", "kulcs": f"{kulcs_alap(s)}-{mod}-{kb}-BUNTETO",
                             "prioritas": 9, "pont": "0+", "hossz": {kb[1:]: "4+"} if kb[1:] in "CDHS" else {},
                             "magyarazat": f"PODI: a kontra büntető ({szep(kb)})"})
            if n == 1 and mod == "DOPI":
                rele.append({"minta": f"{alap} P", "kulcs": f"{kulcs_alap(s)}-{mod}-{kb}-FORSZPASSZ",
                             "prioritas": 9, "pont": "0+",
                             "magyarazat": "DOPI: forszírozó passz (nem kérdezek relével)"})
            # a relé válaszai: a passz-relé után a válaszoló nem passzolhat
            # (kontra = 1. lépcső); licit-relé után a lépcsők a relé fölött
            for v in vcs:
                k = rang(tokenek(str(v["minta"]))[1][-1]) - rang(r)
                if rh == "P":
                    tol = rang(elo[-1]) if kb == "X" else rang(kb)
                    h = ("XX" if kb == "X" else "X") if k == 1 else licit(tol + k - 1)
                elif rh in ("X", "XX"):
                    tol = rang(elo[-1]) if kb == "X" else rang(kb)
                    h = licit(tol + k)
                else:
                    h = licit(rang(rh) + k)
                if rang(h) is not None and rang(h) >= 35:
                    continue
                relevalasz.append(sor_masol(
                    v, f"{alap} {rh} (P) {h}", f"{kulcs_alap(v)}-{mod}-{kb}",
                    f"{mod} (relé {szep(kb)} után, {k}. lépcső)"))
    # 3) a közbeszólás a KÉRDÉS után, a „tetszik” az 1. lépcsővel (PODI: passz,
    # DOPI: kontra) — utána a relé az első szabad licit, a válaszai onnan lépcsők
    for kod, s in sorok:
        if rele_sor(s) != 1:
            continue
        eleje, mi = tokenek(str(s["minta"]))
        if len(mi) < 3:
            continue
        elo, tetszik, r = mi[:-2], mi[-2], mi[-1]
        if (eleje, tuple(elo)) not in cs or rang(tetszik) != rang(elo[-1]) + 1:
            continue
        vcs = cs.get((eleje, tuple(mi)), [])
        q = rang(elo[-1])
        for kb in kozbeszolasok(q, min(rang(r) + 3, 34)):
            th = lepcso_hivas(1, kb, q, mod)
            r2 = licit((q if kb == "X" else rang(kb)) + 1)
            alap = kompetitiv(eleje, elo) + f" ({kb}) {th} (P)"
            rele.append(sor_masol(s, f"{alap} {r2}", f"{kulcs_alap(s)}-{mod}-T-{kb}",
                                  f"{mod} ({szep(kb)} után a „tetszik” {szep(th)}): {r2} = relé"))
            for v in vcs:
                k = rang(tokenek(str(v["minta"]))[1][-1]) - rang(r)
                h = licit(rang(r2) + k)
                if rang(h) >= 35:
                    continue
                relevalasz.append(sor_masol(
                    v, f"{alap} {r2} (P) {h}", f"{kulcs_alap(v)}-{mod}-T-{kb}",
                    f"{mod} (relé {szep(kb)} után, {k}. lépcső)"))
    fejezetek.append((f"Relé a „tetszik” utáni közbeszólásnál ({mod})", rele))
    fejezetek.append((f"A relé válaszai a közbeszólás után ({mod})", relevalasz))
    return fejezetek


FEJ = {
    "PODI": ("PODI", "PODI-PORI", "PODI-PORI",
             "Lépcsős válasz / relé közbeszólás után: 1. lépcső passz, 2. lépcső kontra (rekontra), 3. lépcsőtől az első szabad licit. Relénél: passz = relé, kontra = büntető."),
    "DOPI": ("DOPI", "DOPI-ROPI", "DOPI-ROPI",
             "Lépcsős válasz / relé közbeszólás után: 1. lépcső kontra (rekontra), 2. lépcső passz, 3. lépcsőtől az első szabad licit. Relénél: kontra = relé, passz = forszírozó."),
}


def kiir(mod: str) -> Path:
    kod, nev, nev_en, leiras = FEJ[mod]
    sorok = [f"# {kod} — GENERÁLT FÁJL (eszkozok/lepcsos_kozbeszolas.py), kézzel ne írd át.",
             "# Forrás: a lépcsős válaszok és a relék a " + ", ".join(FORRASOK) + " fájlokból.",
             "rendszer:", f"  kod: {kod}", f"  nev: {nev}", f"  nev_en: {nev_en}",
             "  fajta: KONVENCIO", f"  leiras: \"{leiras}\"", "fejezetek:"]
    for cim, ss in general(mod):
        if not ss:
            continue
        sorok += [f"  - fejezet: \"{cim}\"", "    szabalyok:"]
        for s in ss:
            sorok.append("      - " + yaml.safe_dump(s, default_flow_style=True, allow_unicode=True,
                                                     width=100000, sort_keys=False).strip())
    p = KONV / f"{kod.lower()}.yaml"
    p.write_text("\n".join(sorok) + "\n", encoding="utf-8")
    return p


if __name__ == "__main__":
    for m in (sys.argv[1:] or ["PODI", "DOPI"]):
        p = kiir(m)
        print(p.relative_to(GYOKER), sum(1 for l in p.read_text().splitlines() if "minta:" in l))
