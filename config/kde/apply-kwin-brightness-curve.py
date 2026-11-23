#!/usr/bin/env python3
"""Scrive una curva di luminosità automatica di partenza per lo schermo interno (eDP) nella
configurazione di KWin, poi si disattiva (rinomina il file della curva in .applied).

Gira PRIMA di KWin (servizio utente macbookpro14-3-kwin-curve): con KWin acceso la modifica
verrebbe sovrascritta, perché KWin salva la configurazione che ha in memoria (anche al logout).
Il sensore del 14,3 dà valori bassi con la luce ambiente (vedi docs/input.md), da qui i lux piccoli.
"""
import json, os, sys

home = os.path.expanduser('~')
cfg = os.path.join(home, '.config/kwinoutputconfig.json')
want = os.path.join(home, '.config/macbookpro14-3/kwin-brightness-curve.json')

if not os.path.exists(want) or not os.path.exists(cfg):
    sys.exit(0)
curve = json.load(open(want))
assert all(len(p) == 2 for p in curve) and curve == sorted(curve), 'curva non valida'
data = json.load(open(cfg))
n = 0
for group in data:
    if group.get('name') != 'outputs':
        continue
    for out in group.get('data', []):
        if str(out.get('connectorName', '')).startswith('eDP'):
            out['autoBrightnessCurve'] = curve
            out['automaticBrightness'] = True
            n += 1
if n:
    tmp = cfg + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=4)
        f.write('\n')
    os.replace(tmp, cfg)
os.replace(want, want + '.applied')
print(f'curva applicata a {n} schermi eDP')
