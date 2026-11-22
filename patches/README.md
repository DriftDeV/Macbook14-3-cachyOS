# patches/

Qui vanno le patch che servono *e* che non sono già in un fork da cui scarichiamo.
Al momento è vuota di proposito: la ricerca indica DKMS + header come strada
preferita rispetto a un kernel patchato (`linux-cachyos` non ha una cartella
di patch utente: ogni patch va aggiunta all'array `source` del suo PKGBUILD).

Patch candidate, **non ancora incluse** perché non verificate su un 14,3:

| Patch | Scopo | Stato |
|---|---|---|
| `drm/amdgpu: reset VI ASIC on Apple boards with VRAM at 0` | ibernazione | non upstream |
| handler `.resume` per `apple-ib-tb` (s2idle) | Touch Bar dopo sospensione | PR upstream in attesa |
| PR #2 / #3 di F13-Kr1pt0n/macbook-pro-touchbar-driver | build kernel ≥6.15, deadlock, ALS | non fuse; già nel fork nonderbe |

Convenzione: `NNNN-descrizione.patch`, con in testa l'URL di origine e la versione
di kernel su cui è stata provata.
