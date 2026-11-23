# Audio su MacBookPro14,3: risultati verificati

Data: 23 novembre 2026. Macchina: MacBookPro14,3, CachyOS, kernel `7.3.5-2-cachyos` (clang + ThinLTO),
PipeWire 1.6.11, WirePlumber 0.5.19, KDE Plasma 6.8. Tag come in [`README.md`](README.md).

## Hardware [F]

- Scheda `HDA Intel PCH` (`00:1f.3`), codec **Cirrus Logic CS8409** (`0x10138409`), subsystem `0x106b3900`.
  Confermato sulla macchina: **non** è un CS4208.
- Col driver giusto il codec si presenta come `CS8409/CS42L83` (il CS42L83 gestisce il jack cuffie/microfono).
- Seconda scheda `HDA ATI HDMI` (Radeon, `01:00.1`): audio HDMI/DP, gestito dal kernel.

## Senza driver [F]

Il modulo del kernel `snd-hda-codec-cs8409` riconosce il codec ma lo configura in modo generico
(non conosce gli amplificatori Apple): PipeWire mostra "Audio interno" ma gli speaker restano muti.

## Driver scelto

- `davidjo/snd_hda_macbookpro` (CS8409 + amplificatori Apple) nel fork **`dnlbtz/snd_hda_macbookpro`, branch
  `offlineDkmsDeb`, commit `11febcf`** (2026-11-09) = master davidjo + 5 correzioni scritte su un 14,3:
  ripresa dopo S3/ibernazione (ripete il setup se il codec ha perso i GPIO), microfono cuffie a 4 poli,
  "Capture Source" che sceglie fra microfono interno e cuffie, interrupt, build DKMS senza rete.
- [F] I file del kernel inclusi nel fork (`kernel/7.3/sound/hda/...`, 8 file) sono **identici** a Linux v7.3
  (confronto byte per byte con `torvalds/linux` tag `v7.3`). Nei commit dnlbtz nessuna chiamata a file, rete o programmi esterni.
- [F] Patch nostra [`../patches/audio/`](../patches/audio/): `LLVM=1` automatico nel `Makefile` (gcc rifiuta le opzioni
  del kernel clang: `-fms-anonymous-structs`, `-mstack-alignment`). Due warning innocui (fall-through in pin sense, label C23).
- [F] Il fork compila solo per le serie di kernel che contiene (oggi `7.3`): `scripts/install-audio.sh` salta le altre
  (l'LTS `6.18` resta senza driver: speaker muti su quel kernel). Per aggiungere una serie: `./vendorKernel 6.18` nel fork.

## Prove [F]

| Prova | Risultato |
|---|---|
| Modulo sostituito al volo (unbind `00:1f.3`, rmmod, insmod, bind) | `GPIO mask 0x27 direction 0x22` dopo il boot setup; ingressi Mic Jack e Headphone Jack creati |
| Speaker (`speaker-test -c 2 -t wav`) | **funzionano**, sinistra e destra |
| Microfono interno | **funziona** (livello in Impostazioni → Audio) |
| Cuffie (inserimento/rimozione) | **funzionano**, l'audio passa alle cuffie e torna agli speaker; il driver registra plug/unplug/tasto |
| Microfono delle cuffie | **funziona** |
| Installazione DKMS (`scripts/install-audio.sh`) | `snd_hda_macbookpro/0.1` installato in `updates/dkms` per 7.3.5; modulo originale archiviato da DKMS |

## Da verificare [NV]

- Avvio a freddo con il modulo DKMS (le prove sopra sono con il modulo caricato a mano, stesso codice).
- Bug noto 14,3 (davidjo #80, #134): dopo alcuni avvii il codec ha subsystem id `0x10138409` invece di `0x106b3900`
  e non esce audio. Rimedi riportati: reset NVRAM, avvio da Option, reinstallare il bootloader. Controllo:
  `grep Subsystem /proc/asound/card*/codec#0`.
- Audio dopo la sospensione s2idle (il fork ha la correzione per S3/ibernazione; in s2idle il codec dovrebbe restare alimentato).
- Filter-chain PipeWire `dnlbtz/mbp143-audio` (DSP per gli speaker, +35 dB al microfono cuffie): non ancora valutato.
- Volume del microfono basso (segnalato nel README davidjo).
