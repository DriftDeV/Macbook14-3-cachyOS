#!/usr/bin/env python3
"""Inserisce bankstown (bassi psicoacustici, pkgs/bankstown-lv2) all'inizio del grafo degli altoparlanti di mbp143-audio.

headroom0/1 -> bassex (bankstown) -> f0 (passa-alto 88 Hz) -> ... resto del grafo invariato.
Così le armoniche nascono dal segnale delle app, prima del volume (Loudness), e passano poi da crossover, limitatori
e protezione termica. Valori: quelli di Asahi Linux per il MacBook Pro 14" M1 (asahi-audio firs/j314/graph.json),
provati e preferiti dall'utente sul 14,3 il 25/11/2026. Uso: add-bankstown.py graphs/speakers.json
"""
import json
import sys

BASSEX = {
    "type": "lv2",
    "name": "bassex",
    "plugin": "https://chadmed.au/bankstown",
    "control": {
        "bypass": 0,
        "amt": 1.45,
        "sat_second": 1.35,
        "sat_third": 2.25,
        "blend": 0.67,
        "ceil": 200.0,
        "floor": 20.0,
        "final_hp": 200.0,
    },
}
# collegamento originale -> (uscita verso bankstown, ingresso da bankstown)
REWIRE = {
    ("headroom0:Out", "f0c0b0:In"): ("bassex:in_l", "bassex:out_l"),
    ("headroom1:Out", "f0c1b0:In"): ("bassex:in_r", "bassex:out_r"),
}

path = sys.argv[1]
with open(path) as f:
    doc = json.load(f)
g = doc["filter.graph"]
if any(n["name"] == "bassex" for n in g["nodes"]):
    sys.exit("bassex è già nel grafo")

links, found = [], set()
for link in g["links"]:
    key = (link["output"], link["input"])
    if key in REWIRE:
        to_in, from_out = REWIRE[key]
        links.append({"output": key[0], "input": to_in})
        links.append({"output": from_out, "input": key[1]})
        found.add(key)
    else:
        links.append(link)
if found != set(REWIRE):
    sys.exit("collegamenti headroom -> f0 non trovati: il grafo è cambiato, controlla prima di applicare")

idx = max(i for i, n in enumerate(g["nodes"]) if n["name"].startswith("headroom")) + 1
g["nodes"].insert(idx, BASSEX)
g["links"] = links
with open(path, "w") as f:
    json.dump(doc, f, indent=2)
    f.write("\n")
print("bankstown inserito in", path)
