# Wi-Fi su MacBookPro14,3: risultati verificati

Data: 23 novembre 2026. Macchina: MacBookPro14,3, CachyOS, kernel `7.3.5-2-cachyos`, NetworkManager 1.58 con
wpa_supplicant, `linux-firmware-broadcom` 20261019. Router: iliadbox (2,4 GHz + 5 GHz con lo stesso nome, 5 GHz
sul canale DFS 128, annuncia VHT 80 / HE 160 MHz, paese IT). Tag come in [`README.md`](README.md).

## Prima [F]

- Chip BCM43602 (`14e4:43ba`, `03:00.0`), driver `brcmfmac`, firmware linux-firmware 7.35.177.61 (2015).
- Nessun file NVRAM per la scheda: MAC generico Broadcom `00:90:4c:0d:f4:3e`, `country 99` sul phy, **solo Band 1**
  (le reti a 5 GHz non si vedono), canale 11 a 20 MHz, segnale -70 dBm, bitrate 58/78 Mbit/s.
- Speed test dell'utente: ~21 Mbit/s, instabile (rete in fibra da 2 Gbit/s).

## Correzione: `scripts/install-wifi.sh`

- Base: `dnlbtz/mbp143-wifi` tag `v1.1.0` (`04741cb`, MIT), provato dall'autore su 14,3 + CachyOS + kernel 7.3.
  Codice letto prima dell'uso: legge la SROM del chip via BAR0 con `brcmfmac` scaricato (solo lettura,
  ripristina la finestra), genera il file NVRAM (155 valori dal chip, 36 fissi motivati nel template),
  applica 5 modifiche al firmware (tabella front-end Apple + setup Bluetooth) con controllo SHA-256 prima e dopo.
- [F] Il firmware di `linux-firmware-broadcom` installato è identico a quello per cui è scritta la patch
  (sha256 `bf4cfc23…`), e la patch dà l'hash atteso (`b34c409d…`): si usa il firmware del sistema, non la copia del repo.
- **Nella repo non c'è nessun file NVRAM**: i 4 file (setup, patch, template, tabella SROM) vengono scaricati
  sulla macchina all'installazione da un commit fissato, con SHA-256 in `config/sources.conf`.
  Nota: i 36 valori fissi del template vengono in parte dal file del MacBookPro13,3 (kernel bug 193121).
- NetworkManager (`config/networkmanager/`): niente MAC casuale durante la scansione (da mihneadevries: su
  brcmfmac la scansione dopo il cambio di MAC perde le reti a 5 GHz), MAC stabile per rete, dispatcher che passa
  a 5 GHz quando la stessa rete è lì (da dnlbtz, MIT).
- Il file `.Apple Inc.-MacBookPro14,3.txt` e il firmware patchato vanno in `/usr/lib/firmware/updates/brcm/`
  (hanno la precedenza su linux-firmware e i suoi aggiornamenti non li toccano). Valori letti in `/var/lib/mbp143-wifi/`.

## Dopo [F]

| | prima | dopo |
|---|---|---|
| Bande | solo 2,4 GHz | 2,4 + 5 GHz (Band 1 e Band 2) |
| Collegamento | canale 11, 20 MHz | canale 128 (5640 MHz), **40 MHz** |
| Segnale | -70 dBm | -45 / -42 dBm |
| Bitrate rx / tx | 58 / 78 Mbit/s | 200-400 / 162 Mbit/s |
| Download (`proof.ovh.net`, 1 GB, 20-25 s) | ~21 Mbit/s (speed test utente) | 293, 291, 146 Mbit/s |

`sromrev=12`, `boardtype=0x157`, `boardrev=0x1108` letti dal chip. Passaggio automatico a 5 GHz riuscito.
Il MAC dell'interfaccia è ora stabile per rete (`permaddr` resta `00:90:4c:…`).

## Aperto [NV]

- **Canale a 40 MHz invece di 80**: il router annuncia VHT80 (centro 122) e `iw phy` permette VHT80 sul
  canale 128, ma il collegamento resta a 40 MHz anche dopo una riconnessione. Ipotesi [I]: CachyOS imposta il
  paese IT dal fuso orario (`iw-set-regdomain`), brcmfmac passa il firmware dalla tabella DE rev 2 del file NVRAM
  a quella IT, che potrebbe non ammettere 80 MHz sui canali DFS.
  - [F] Test `iw reg set DE` + riconnessione (23/11/2026): **inconcludente**, la regione globale resta IT
    (mentre si è connessi prevale il paese annunciato dal router), larghezza sempre 40 MHz.
  - [F] Nelle tre misure il bitrate rx alterna 200 e 400 Mbit/s (1 o 2 flussi) e il download 139-281 Mbit/s:
    è questa l'instabilità percepita.
  - Ipotesi alternativa [I]: la iliadbox trasmette a 160 MHz (VHT operation: larghezza 1, CCFS0 122, CCFS1 114,
    formato 802.11-2016); il firmware del 2015 potrebbe non interpretarlo e ripiegare su 40 MHz.
    Prova da fare sul router: banda 5 GHz a 80 MHz (ed eventualmente un canale non DFS, 36-48).
- Wi-Fi dopo la sospensione (l'hook scarica e ricarica `brcmfmac`; il firmware viene da `updates/`).
- Upload non misurato; stabilità su tempi lunghi.
- Riavvio da macOS: secondo dnlbtz lascia il 5 GHz ~20 dB più debole finché Linux non riparte (meglio spegnere macOS).
