"""
Egy rendszer ember által olvasható leírása fájlba — adatbázis nélkül, a
YAML-forrásból (a szolgáltatásban: GET /v1/kibic/leiras és /v1/kibic/kartya).

    python -m kibic.cli.rendszerleiras --rendszer MOHA_STAND --ki moha_stand.html
    python -m kibic.cli.rendszerleiras --rendszer MOHA_STAND --formatum md --ki moha_stand.md
    python -m kibic.cli.rendszerleiras --rendszer MOHA_STAND --kartya --ki moha_kartya.html

A teljes leírás (alap) a feloldott rendszer minden szabálya forrás és fejezet
szerint; a `--kartya` a rövid változat (a konvenciókártya).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Rendszerleírás (teljes vagy kártya) fájlba")
    ap.add_argument("--rendszer", default="MOHA_STAND")
    ap.add_argument("--formatum", choices=("html", "md"), default="html")
    ap.add_argument("--kartya", action="store_true", help="a rövid változat (kártya, HTML)")
    ap.add_argument("--ki", required=True)
    ap.add_argument("--yaml", nargs="*", default=["rendszerek/yaml"])
    a = ap.parse_args(argv)
    from ..impex.rendszer_yaml import betolt
    g = betolt([Path(u) for u in a.yaml])
    if a.rendszer not in g:
        print(f"Nincs ilyen rendszer a YAML-ban: {a.rendszer}", file=sys.stderr)
        return 2
    if a.kartya:
        from ..motor.kartya import kartya_html, kartya_yamlbol
        szoveg = kartya_html(kartya_yamlbol(g, a.rendszer))
    else:
        from ..szolgaltatas.leiras import leiras_html, leiras_md, leiras_yamlbol
        adat = leiras_yamlbol(g, a.rendszer)
        szoveg = leiras_html(adat) if a.formatum == "html" else leiras_md(adat)
    Path(a.ki).write_text(szoveg, encoding="utf-8")
    print(f"{a.ki} ({len(szoveg) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
