"""Baja de promiedos los resultados finales y los guarda en resultados.json.

Lo corre la VPS con cron cada 3 minutos (scripts/actualizar.sh, ver scripts/VPS.md).
La página lee ese archivo al abrirse y
carga esos resultados como oficiales (no se pueden editar).

- Liga: fechas 14 a 16 del Clausura.
- Playoffs del Clausura: las fases que aparezcan después de las fechas del Clausura.
- Copas: semifinales y finales de Libertadores, Sudamericana y Copa Argentina.
Solo se guardan los partidos terminados (status 3).
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Accept-Language": "es-AR,es;q=0.9",
    "X-VER": "1.11.7.5",  # sin esto la lista del día viene vacía
}
SITE = "https://www.promiedos.com.ar/league"
API = "https://api.promiedos.com.ar/league/games"
FECHAS = {14, 15, 16}
MANUAL = __import__("os").path.join(__import__("os").path.dirname(__file__), "manual.json")

# id de promiedos -> id de la página
TEAMS = {
    "hchc": "ins", "igg": "boc", "hcbh": "dyj", "ihc": "vel", "igj": "lan", "ihh": "new", "bbjbf": "gim",
    "ihe": "ind", "igf": "slo", "igh": "est", "hcag": "uni", "hcah": "pla", "bbjea": "rie", "beafh": "cco",
    "jche": "tal", "ihf": "cen", "ihb": "arg", "iia": "glp", "fhid": "bel", "hbbh": "sar", "igi": "riv",
    "jafb": "bar", "iie": "hur", "hcch": "irv", "gbfc": "atu", "iid": "tig", "ihi": "ban", "ihg": "rac",
    "bheaf": "erc", "hccd": "ald",
    # rivales de copa
    "bcbf": "fla", "bccc": "pal", "bcbg": "flu", "bcch": "vas", "bcaj": "cam", "bcghf": "ctq",
}
CUPS = [("libertadores", "bac", "lib"), ("conmebol-sudamericana", "dij", "sud"), ("copa-argentina", "gea", "ca")]


def get(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read().decode("utf8")


def filters(slug, lid):
    html = get(f"{SITE}/{slug}/{lid}")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1))["props"]["pageProps"]["data"]["games"]["filters"]


def games(lid, key):
    return json.loads(get(f"{API}/{lid}/{key}")).get("games", [])


def ints(v):
    return [int(x) for x in v] if v else None


def single_winner(g):
    """1 o 2 según quién ganó un partido único (goles y, si empatan, penales); None si no se sabe."""
    for k in ("scores", "penalties"):
        v = ints(g.get(k))
        if v and len(v) == 2 and v[0] != v[1]:
            return 1 if v[0] > v[1] else 2
    return None


def team_ids(g):
    return [TEAMS.get(t["id"]) for t in g["teams"]]


def main(out_path):
    out = {"liga": [], "playoffs": [], "copas": [], "agenda_po": [], "sin_mapear": []}

    # --- Liga y playoffs del Clausura
    fl = filters("liga-profesional", "hc")
    names = [f["name"] for f in fl]
    start = max(i for i, n in enumerate(names) if n == "Fecha 1")  # el último "Fecha 1" es el del Clausura
    for f in fl[start:]:
        m = re.fullmatch(r"Fecha (\d+)", f["name"])
        playoff = re.search(r"Octavos|Cuartos|Semifinal|Final", f["name"])
        if not ((m and int(m.group(1)) in FECHAS) or playoff):
            continue
        for g in games("hc", f["key"]):
            st = g.get("status", {}).get("enum")
            if playoff:  # agenda de los playoffs (día y hora tal como los da promiedos; la página los ajusta a su horario)
                h, a = team_ids(g)
                if h and a and g.get("start_time"):
                    out["agenda_po"].append({"fase": f["name"], "h": h, "a": a, "t": g["start_time"]})
            if st != 3 or not g.get("scores"):
                if m:
                    print("sin terminar:", f["name"], g.get("url_name"), "estado", st)
                continue
            h, a = team_ids(g)
            if not h or not a:
                out["sin_mapear"].append(g.get("url_name"))
                continue
            row = {"h": h, "a": a, "g": ints(g["scores"])}
            if m:
                row["f"] = int(m.group(1))
                out["liga"].append(row)
            else:
                row["fase"] = f["name"]
                if g.get("penalties"):
                    row["p"] = ints(g["penalties"])
                out["playoffs"].append(row)

    # --- Lista del día (promiedos la actualiza cada 15 s; la de la fecha cada 5 min): partidos de ayer y hoy en Argentina.
    art = timezone(timedelta(hours=-3))
    seen = {(r["h"], r["a"]) for r in out["liga"]}
    for day in {(datetime.now(art) - timedelta(days=k)).strftime("%d-%m-%Y") for k in (0, 1)}:
        try:
            data = json.loads(get(f"https://api.promiedos.com.ar/games/{day}"))
        except Exception:
            continue
        for lg in data.get("leagues", []):
            if lg.get("id") != "hc":
                continue
            for g in lg.get("games", []):
                if g.get("status", {}).get("enum") != 3 or not g.get("scores") or not re.fullmatch(r"Fecha (\d+)", g.get("stage_round_name", "")):
                    continue
                f = int(g["stage_round_name"].split()[1])
                h, a = team_ids(g)
                if f in FECHAS and h and a and (h, a) not in seen:
                    out["liga"].append({"h": h, "a": a, "g": ints(g["scores"]), "f": f})
                    seen.add((h, a))

    # --- Copas: semifinales y final. Una llave está definida cuando el partido trae "to_qualify".
    for slug, lid, cup in CUPS:
        for f in filters(slug, lid):
            if not re.fullmatch(r"Semifinales?|Final", f["name"]):
                continue
            for g in games(lid, f["key"]):
                if g.get("status", {}).get("enum") != 3:
                    continue
                q = g.get("to_qualify") or (g.get("winner") if f["name"] == "Final" else None)
                if q not in (1, 2) and (cup == "ca" or f["name"] == "Final"):
                    q = single_winner(g)  # partido único: lo define el marcador o, si empatan, los penales
                print(cup, f["name"], g.get("url_name"), g.get("scores"), g.get("penalties"), "to_qualify", g.get("to_qualify"), "winner", g.get("winner"), "->", q)
                if q not in (1, 2):
                    continue
                h, a = team_ids(g)
                if not h or not a:
                    out["sin_mapear"].append(g.get("url_name"))
                    continue
                out["copas"].append({"copa": cup, "fase": f["name"], "h": h, "a": a, "w": h if q == 1 else a})

    # Un resultado final ya guardado no se borra: a veces promiedos devuelve la lista de una fecha incompleta.
    try:
        prev = json.load(open(out_path, encoding="utf8"))
    except (OSError, ValueError):
        prev = {}
    same = lambda x, r: {x["h"], x["a"]} == {r["h"], r["a"]} and x.get("copa") == r.get("copa") and x.get("f") == r.get("f")
    for k in ("liga", "playoffs", "copas"):
        for r in prev.get(k, []):
            if not any(same(x, r) for x in out[k]):
                out[k].append(r)

    # Cargas manuales (scripts/manual.json): resultados que promiedos todavía no tiene o tiene mal.
    # Se agregan si promiedos no trae ese cruce; si lo trae, manda promiedos.
    try:
        manual = json.load(open(MANUAL, encoding="utf8"))
    except (OSError, ValueError):
        manual = {}
    for k in ("liga", "playoffs", "copas"):
        for r in manual.get(k, []):
            if not any({x["h"], x["a"]} == {r["h"], r["a"]} and x.get("copa") == r.get("copa") for x in out[k]):
                out[k].append(r)

    for k in ("liga", "playoffs", "copas", "agenda_po"):
        out[k].sort(key=lambda r: json.dumps(r, sort_keys=True))
    # Solo se reescribe si cambió algo (la fecha de actualización no cuenta).
    try:
        old = json.load(open(out_path, encoding="utf8"))
    except (OSError, ValueError):
        old = {}
    if {k: v for k, v in old.items() if k != "actualizado"} == out:
        print("sin cambios")
        return
    out["actualizado"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
    with open(out_path, "w", encoding="utf8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"liga {len(out['liga'])} · playoffs {len(out['playoffs'])} · copas {len(out['copas'])} · sin mapear {len(out['sin_mapear'])}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "resultados.json")
