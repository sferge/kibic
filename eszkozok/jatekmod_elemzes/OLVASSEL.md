# Játékmódok a gyűjteményekből (2026-11-02)

Pavlicek-partik (`tanpartik/pavlicek_teljes`, a „Play:” címkék) és BBO „Hand of the day”
(`tanpartik/bbo_hotd`, a magyarázatok kulcsszavai) — a két kézből számolt kezdőjegyekkel.
A források nem verziózottak. Futtatás (a köztes fájlok: /tmp/jatekmod_elemzes):

    mkdir -p /tmp/jatekmod_elemzes && cd eszkozok/jatekmod_elemzes
    python3 rp.py && python3 rp2.py && python3 rp3.py && python3 rp4.py
    python3 bbo.py && python3 bbo2.py

Az eredmény és az értelmezés: claude/terv-jatekmodok-2026-11-02.md (projekt).
